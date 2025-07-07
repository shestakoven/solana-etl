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


import click
import logging
import time
import signal
import sys
from typing import Optional

from solanaetl.jobs.run_streaming_job import RunStreamingJob
from solanaetl.providers.auto import get_provider_from_uri
from solanaetl.thread_local_proxy import ThreadLocalProxy


logger = logging.getLogger(__name__)


# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-p', '--provider-uri', default='https://api.mainnet-beta.solana.com', 
              show_default=True, type=str, help='The URI of the Solana node provider.')
@click.option('--clickhouse-uri', type=str, 
              help='ClickHouse connection URI (e.g. clickhouse://user:password@localhost:9000/solana)')
@click.option('-o', '--output-dir', type=str, 
              help='Output directory for CSV files (alternative to ClickHouse)')
@click.option('-s', '--start-block', type=int, help='Start block number (default: latest)')
@click.option('-w', '--max-workers', default=5, show_default=True, type=int,
              help='The maximum number of workers.')
@click.option('-b', '--batch-size', default=10, show_default=True, type=int,
              help='The number of blocks to process in each batch.')
@click.option('--block-batch-size', default=1, show_default=True, type=int,
              help='The number of blocks to export in each block batch.')
@click.option('--poll-interval', default=10, show_default=True, type=int,
              help='Interval in seconds between polling for new blocks.')
@click.option('--lag', default=0, show_default=True, type=int,
              help='Number of blocks to lag behind the latest block.')
@click.option('--enable-blocks', default=True, show_default=True, type=bool,
              help='Enable blocks export.')
@click.option('--enable-transactions', default=True, show_default=True, type=bool,
              help='Enable transactions export.')
@click.option('--enable-instructions', default=True, show_default=True, type=bool,
              help='Enable instructions export.')
@click.option('--enable-token-transfers', default=True, show_default=True, type=bool,
              help='Enable token transfers extraction.')
@click.option('--enable-dex-trades', default=True, show_default=True, type=bool,
              help='Enable DEX trades extraction.')
@click.option('--enable-accounts', default=True, show_default=True, type=bool,
              help='Enable accounts extraction.')
@click.option('--enable-tokens', default=True, show_default=True, type=bool,
              help='Enable tokens extraction.')
@click.option('--clickhouse-batch-size', default=1000, show_default=True, type=int,
              help='Batch size for ClickHouse insertions.')
@click.option('--log-level', default='INFO', show_default=True, 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Logging level.')
@click.option('--print-sql', default=False, show_default=True, type=bool,
              help='Print SQL statements (for debugging).')
def run(provider_uri, clickhouse_uri, output_dir, start_block, max_workers, batch_size, 
        block_batch_size, poll_interval, lag, enable_blocks, enable_transactions, 
        enable_instructions, enable_token_transfers, enable_dex_trades, enable_accounts, 
        enable_tokens, clickhouse_batch_size, log_level, print_sql):
    """
    Run continuous export of all Solana entities on new blocks.
    
    This command will continuously monitor the Solana blockchain for new blocks
    and export all enabled entity types (blocks, transactions, instructions, 
    token transfers, DEX trades, accounts, tokens) to either ClickHouse or CSV files.
    
    Examples:
    
    # Export to ClickHouse
    solanaetl run --clickhouse-uri clickhouse://localhost:9000/solana
    
    # Export to CSV files
    solanaetl run --output-dir ./output
    
    # Start from specific block
    solanaetl run --clickhouse-uri clickhouse://localhost:9000/solana --start-block 250000000
    """
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Validate parameters
    if not clickhouse_uri and not output_dir:
        raise click.BadParameter("Either --clickhouse-uri or --output-dir must be specified")
    
    if clickhouse_uri and output_dir:
        raise click.BadParameter("Cannot specify both --clickhouse-uri and --output-dir")
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Solana ETL streaming job...")
    logger.info(f"Provider URI: {provider_uri}")
    logger.info(f"ClickHouse URI: {clickhouse_uri if clickhouse_uri else 'None'}")
    logger.info(f"Output directory: {output_dir if output_dir else 'None'}")
    logger.info(f"Start block: {start_block if start_block else 'latest'}")
    logger.info(f"Max workers: {max_workers}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Poll interval: {poll_interval}s")
    
    # Entity toggles
    entity_types = []
    if enable_blocks:
        entity_types.append('blocks')
    if enable_transactions:
        entity_types.append('transactions')
    if enable_instructions:
        entity_types.append('instructions')
    if enable_token_transfers:
        entity_types.append('token_transfers')
    if enable_dex_trades:
        entity_types.append('dex_trades')
    if enable_accounts:
        entity_types.append('accounts')
    if enable_tokens:
        entity_types.append('tokens')
    
    logger.info(f"Enabled entity types: {', '.join(entity_types)}")
    
    try:
        # Create and run streaming job
        job = RunStreamingJob(
            provider_uri=provider_uri,
            clickhouse_uri=clickhouse_uri,
            output_dir=output_dir,
            start_block=start_block,
            max_workers=max_workers,
            batch_size=batch_size,
            block_batch_size=block_batch_size,
            poll_interval=poll_interval,
            lag=lag,
            entity_types=entity_types,
            clickhouse_batch_size=clickhouse_batch_size,
            print_sql=print_sql
        )
        
        # Run until shutdown requested
        global shutdown_requested
        while not shutdown_requested:
            try:
                job.run_single_iteration()
                
                if not shutdown_requested:
                    logger.debug(f"Sleeping for {poll_interval} seconds...")
                    time.sleep(poll_interval)
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in streaming job iteration: {e}")
                if not shutdown_requested:
                    logger.info(f"Retrying in {poll_interval} seconds...")
                    time.sleep(poll_interval)
        
        logger.info("Shutting down streaming job...")
        job.close()
        
    except Exception as e:
        logger.error(f"Fatal error in streaming job: {e}")
        sys.exit(1)
    
    logger.info("Solana ETL streaming job stopped.")