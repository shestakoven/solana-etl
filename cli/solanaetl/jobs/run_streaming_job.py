# The MIT License (MIT)
# Copyright (c) 2022 Gamejam.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software
# and associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import logging
import os
import json
from typing import Optional, List, Dict, Any
from tempfile import TemporaryDirectory

from blockchainetl_common.jobs.exporters.composite_item_exporter import CompositeItemExporter
from blockchainetl_common.jobs.exporters.console_item_exporter import ConsoleItemExporter

from solanaetl.jobs.export_blocks_job import ExportBlocksJob
from solanaetl.jobs.extract_accounts_job import ExtractAccountsJob
from solanaetl.jobs.extract_dex_trades_job import ExtractDexTradesJob
from solanaetl.jobs.extract_token_transfers_job import ExtractTokenTransfersJob
from solanaetl.jobs.extract_tokens_job import ExtractTokensJob
from solanaetl.providers.auto import get_provider_from_uri
from solanaetl.providers.clickhouse import get_clickhouse_provider_from_uri
from solanaetl.schemas.clickhouse_schemas import create_all_tables
from solanaetl.thread_local_proxy import ThreadLocalProxy


logger = logging.getLogger(__name__)


class RunStreamingJob:
    """Streaming job that continuously exports all Solana entities on new blocks."""
    
    def __init__(
        self,
        provider_uri: str,
        clickhouse_uri: Optional[str] = None,
        output_dir: Optional[str] = None,
        start_block: Optional[int] = None,
        max_workers: int = 5,
        batch_size: int = 10,
        block_batch_size: int = 1,
        poll_interval: int = 10,
        lag: int = 0,
        entity_types: List[str] = None,
        clickhouse_batch_size: int = 1000,
        print_sql: bool = False
    ):
        self.provider_uri = provider_uri
        self.clickhouse_uri = clickhouse_uri
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.block_batch_size = block_batch_size
        self.poll_interval = poll_interval
        self.lag = lag
        self.entity_types: List[str] = entity_types if entity_types is not None else ['blocks', 'transactions', 'instructions']
        self.clickhouse_batch_size = clickhouse_batch_size
        self.print_sql = print_sql
        
        # Initialize provider
        self.provider = get_provider_from_uri(provider_uri, batch=True)
        self.solana_service = ThreadLocalProxy(lambda: self.provider)
        
        # Initialize storage
        self.clickhouse_provider = None
        if clickhouse_uri:
            self.clickhouse_provider = get_clickhouse_provider_from_uri(clickhouse_uri)
            # Create tables if needed
            database_name = getattr(self.clickhouse_provider, 'database', 'solana')
            create_all_tables(self.clickhouse_provider, database_name)
        
        # State tracking
        self.last_exported_block: int = start_block if start_block is not None else (self._get_latest_block() - lag - 1)
    
    def _get_latest_block(self) -> int:
        """Get the latest block number from the blockchain."""
        try:
            latest_slot = self.solana_service.get_slot()
            logger.debug(f"Latest slot from provider: {latest_slot}")
            return latest_slot
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            raise
    
    def run_single_iteration(self) -> None:
        """Run a single iteration of the streaming job."""
        try:
            # Get current latest block
            latest_block = self._get_latest_block() - self.lag
            
            if self.last_exported_block >= latest_block:
                logger.debug(f"No new blocks to process. Last exported: {self.last_exported_block}, Latest: {latest_block}")
                return
            
            # Calculate range to export
            start_block = self.last_exported_block + 1
            end_block = min(start_block + self.batch_size - 1, latest_block)
            
            logger.info(f"Processing blocks {start_block} to {end_block}")
            
            # Export the batch
            self._export_batch(start_block, end_block)
            
            # Update last exported block
            self.last_exported_block = end_block
            
            logger.info(f"Successfully processed blocks {start_block} to {end_block}")
            
        except Exception as e:
            logger.error(f"Error in streaming iteration: {e}")
            raise
    
    def _export_batch(self, start_block: int, end_block: int) -> None:
        """Export a batch of blocks and all related entities."""
        
        # Create item exporter
        item_exporter = self._create_item_exporter()
        
        try:
            item_exporter.open()
            
            # Step 1: Export blocks, transactions, and instructions
            if any(entity_type in self.entity_types for entity_type in ['blocks', 'transactions', 'instructions']):
                self._export_blocks_and_transactions(start_block, end_block, item_exporter)
            
            # Step 2: Extract token transfers from instructions
            if 'token_transfers' in self.entity_types:
                self._extract_token_transfers(start_block, end_block, item_exporter)
            
            # Step 3: Extract DEX trades from instructions  
            if 'dex_trades' in self.entity_types:
                self._extract_dex_trades(start_block, end_block, item_exporter)
            
            # Step 4: Extract accounts
            if 'accounts' in self.entity_types:
                self._extract_accounts(start_block, end_block, item_exporter)
            
            # Step 5: Extract tokens
            if 'tokens' in self.entity_types:
                self._extract_tokens(start_block, end_block, item_exporter)
                
        finally:
            item_exporter.close()
    
    def _create_item_exporter(self) -> CompositeItemExporter:
        """Create the appropriate item exporter (ClickHouse or CSV)."""
        
        if self.clickhouse_uri:
            # Use ClickHouse exporter
            from solanaetl.jobs.exporters.clickhouse_item_exporter import create_clickhouse_item_exporter
            
            database_name = getattr(self.clickhouse_provider, 'database', 'solana') if self.clickhouse_provider else 'solana'
            return create_clickhouse_item_exporter(
                clickhouse_uri=self.clickhouse_uri,
                database=database_name,
                batch_size=self.clickhouse_batch_size
            )
        
        elif self.output_dir:
            # Use CSV exporter
            os.makedirs(self.output_dir, exist_ok=True)
            
            filename_mapping = {}
            field_mapping = {}
            
            if 'blocks' in self.entity_types:
                filename_mapping['block'] = os.path.join(self.output_dir, 'blocks.csv')
                field_mapping['block'] = ['hash', 'slot', 'parent_hash', 'block_height', 'block_time', 
                                        'previous_blockhash', 'rewards', 'timestamp']
            
            if 'transactions' in self.entity_types:
                filename_mapping['transaction'] = os.path.join(self.output_dir, 'transactions.csv')
                field_mapping['transaction'] = ['signature', 'slot', 'error', 'fee', 'pre_balances', 
                                              'post_balances', 'pre_token_balances', 'post_token_balances',
                                              'account_keys', 'log_messages', 'instructions_count',
                                              'inner_instructions_count', 'block_time', 'block_hash', 'successful']
            
            if 'instructions' in self.entity_types:
                filename_mapping['instruction'] = os.path.join(self.output_dir, 'instructions.csv')
                field_mapping['instruction'] = ['tx_signature', 'slot', 'block_time', 'instruction_index',
                                              'program', 'program_id', 'accounts', 'data', 'instruction_type',
                                              'params', 'inner_instruction', 'parent_instruction_index']
            
            if 'token_transfers' in self.entity_types:
                filename_mapping['token_transfer'] = os.path.join(self.output_dir, 'token_transfers.csv')
                field_mapping['token_transfer'] = ['source', 'destination', 'authority', 'value', 'decimals',
                                                 'mint', 'mint_authority', 'transfer_type', 'tx_signature']
            
            if 'dex_trades' in self.entity_types:
                filename_mapping['dex_trade'] = os.path.join(self.output_dir, 'dex_trades.csv')
                field_mapping['dex_trade'] = ['pool_address', 'wallet_address', 'token_addresses', 
                                            'token_amounts', 'usd_amount', 'token_prices', 'dex_name',
                                            'tx_signature', 'block_time', 'instruction_index']
            
            if 'accounts' in self.entity_types:
                filename_mapping['account'] = os.path.join(self.output_dir, 'accounts.csv')
                field_mapping['account'] = ['address', 'lamports', 'owner', 'executable', 'rent_epoch', 'data']
            
            if 'tokens' in self.entity_types:
                filename_mapping['token'] = os.path.join(self.output_dir, 'tokens.csv')
                field_mapping['token'] = ['address', 'mint_authority', 'supply', 'decimals', 
                                        'is_initialized', 'freeze_authority']
            
            return CompositeItemExporter(
                filename_mapping=filename_mapping,
                field_mapping=field_mapping
            )
        
        else:
            # Console exporter for debugging
            return ConsoleItemExporter()
    
    def _export_blocks_and_transactions(self, start_block: int, end_block: int, item_exporter) -> None:
        """Export blocks, transactions, and instructions."""
        logger.debug(f"Exporting blocks and transactions for {start_block}-{end_block}")
        
        job = ExportBlocksJob(
            start_block=start_block,
            end_block=end_block,
            batch_size=self.block_batch_size,
            batch_web3_provider=self.provider,
            max_workers=self.max_workers,
            item_exporter=item_exporter,
            export_blocks='blocks' in self.entity_types,
            export_transactions='transactions' in self.entity_types,
            export_instructions='instructions' in self.entity_types
        )
        
        job.run()
    
    def _extract_token_transfers(self, start_block: int, end_block: int, item_exporter) -> None:
        """Extract token transfers from instructions."""
        logger.debug(f"Extracting token transfers for {start_block}-{end_block}")
        
        # Get instructions from previous export or query them
        instructions_iterable = self._get_instructions_for_blocks(start_block, end_block)
        
        job = ExtractTokenTransfersJob(
            instructions_iterable=instructions_iterable,
            batch_size=self.batch_size,
            max_workers=self.max_workers,
            item_exporter=item_exporter
        )
        
        job.run()
    
    def _extract_dex_trades(self, start_block: int, end_block: int, item_exporter) -> None:
        """Extract DEX trades from instructions."""
        logger.debug(f"Extracting DEX trades for {start_block}-{end_block}")
        
        # Get instructions from previous export or query them
        instructions_iterable = self._get_instructions_for_blocks(start_block, end_block)
        
        job = ExtractDexTradesJob(
            instructions_iterable=instructions_iterable,
            batch_size=self.batch_size,
            max_workers=self.max_workers,
            item_exporter=item_exporter
        )
        
        job.run()
    
    def _extract_accounts(self, start_block: int, end_block: int, item_exporter) -> None:
        """Extract accounts from instructions."""
        logger.debug(f"Extracting accounts for {start_block}-{end_block}")
        
        # Get instructions from previous export or query them
        instructions_iterable = self._get_instructions_for_blocks(start_block, end_block)
        
        job = ExtractAccountsJob(
            instructions_iterable=instructions_iterable,
            batch_size=self.batch_size,
            max_workers=self.max_workers,
            item_exporter=item_exporter,
            batch_web3_provider=self.provider
        )
        
        job.run()
    
    def _extract_tokens(self, start_block: int, end_block: int, item_exporter) -> None:
        """Extract tokens from accounts."""
        logger.debug(f"Extracting tokens for {start_block}-{end_block}")
        
        # Get accounts from previous extraction or query them
        accounts_iterable = self._get_accounts_for_blocks(start_block, end_block)
        
        job = ExtractTokensJob(
            accounts_iterable=accounts_iterable,
            batch_size=self.batch_size,
            max_workers=self.max_workers,
            item_exporter=item_exporter,
            batch_web3_provider=self.provider
        )
        
        job.run()
    
    def _get_instructions_for_blocks(self, start_block: int, end_block: int):
        """Get instructions for the given block range."""
        # This is a simplified implementation
        # In a real scenario, you might want to query from ClickHouse or use in-memory data
        logger.warning("Instructions retrieval not fully implemented - using empty iterable")
        return []
    
    def _get_accounts_for_blocks(self, start_block: int, end_block: int):
        """Get accounts for the given block range."""
        # This is a simplified implementation
        # In a real scenario, you might want to query from ClickHouse or use in-memory data
        logger.warning("Accounts retrieval not fully implemented - using empty iterable")
        return []
    
    def close(self) -> None:
        """Close all resources."""
        if self.clickhouse_provider:
            self.clickhouse_provider.close()
        
        logger.info("Streaming job resources closed.")