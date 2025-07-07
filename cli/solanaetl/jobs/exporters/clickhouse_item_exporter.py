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
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from blockchainetl_common.jobs.exporters.in_memory_item_exporter import InMemoryItemExporter
from solanaetl.providers.clickhouse import ClickHouseProvider


logger = logging.getLogger(__name__)


class ClickHouseItemExporter(InMemoryItemExporter):
    """ClickHouse item exporter for Solana ETL entities."""
    
    def __init__(
        self,
        clickhouse_provider: ClickHouseProvider,
        item_type_to_table_mapping: Dict[str, str],
        batch_size: int = 1000,
        enable_batch_insert: bool = True
    ):
        super().__init__()
        self.clickhouse_provider = clickhouse_provider
        self.item_type_to_table_mapping = item_type_to_table_mapping
        self.batch_size = batch_size
        self.enable_batch_insert = enable_batch_insert
        self.items_buffer: Dict[str, List[Dict]] = {}
        
    def export_item(self, item: Dict[str, Any]) -> None:
        """Export a single item."""
        item_type = item.get('type')
        if not item_type:
            logger.warning(f"Item missing type field: {item}")
            return
            
        table_name = self.item_type_to_table_mapping.get(item_type)
        if not table_name:
            logger.warning(f"No table mapping for item type: {item_type}")
            return
            
        if self.enable_batch_insert:
            # Add to buffer for batch processing
            if table_name not in self.items_buffer:
                self.items_buffer[table_name] = []
            
            processed_item = self._process_item(item)
            self.items_buffer[table_name].append(processed_item)
            
            # Flush if batch size reached
            if len(self.items_buffer[table_name]) >= self.batch_size:
                self._flush_table(table_name)
        else:
            # Insert immediately
            processed_item = self._process_item(item)
            self._insert_items(table_name, [processed_item])
    
    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process item for ClickHouse insertion."""
        processed = item.copy()
        
        # Remove type field as it's not part of the table schema
        processed.pop('type', None)
        
        # Convert timestamps
        for key, value in processed.items():
            if key.endswith('_time') and value is not None:
                if isinstance(value, (int, float)):
                    # Convert Unix timestamp to datetime
                    processed[key] = datetime.fromtimestamp(value)
                elif isinstance(value, str):
                    try:
                        # Try to parse ISO format
                        processed[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        # Keep as string if parsing fails
                        pass
            
            # Convert JSON strings to actual objects for arrays
            elif isinstance(value, str) and (key.endswith('_balances') or key.endswith('_keys') or 
                                           key.endswith('_messages') or key == 'accounts' or
                                           key == 'token_addresses' or key == 'token_amounts' or key == 'token_prices'):
                try:
                    processed[key] = json.loads(value) if value else []
                except (json.JSONDecodeError, TypeError):
                    processed[key] = []
            
            # Handle None values for required fields
            elif value is None and key in ['slot', 'instruction_index', 'fee']:
                processed[key] = 0
        
        return processed
    
    def _insert_items(self, table_name: str, items: List[Dict[str, Any]]) -> None:
        """Insert items into ClickHouse table."""
        if not items:
            return
            
        try:
            # Convert items to list of tuples for ClickHouse insertion
            if items:
                # Get column names from first item
                columns = list(items[0].keys())
                rows = []
                
                for item in items:
                    # Ensure all items have the same columns in the same order
                    row = tuple(item.get(col) for col in columns)
                    rows.append(row)
                
                self.clickhouse_provider.insert(table_name, rows, columns)
                logger.info(f"Inserted {len(rows)} items into {table_name}")
                
        except Exception as e:
            logger.error(f"Error inserting items into {table_name}: {e}")
            raise
    
    def _flush_table(self, table_name: str) -> None:
        """Flush buffer for a specific table."""
        if table_name in self.items_buffer and self.items_buffer[table_name]:
            items = self.items_buffer[table_name]
            self._insert_items(table_name, items)
            self.items_buffer[table_name] = []
    
    def close(self) -> None:
        """Close exporter and flush all remaining items."""
        # Flush all remaining items
        for table_name in list(self.items_buffer.keys()):
            self._flush_table(table_name)
        
        # Close ClickHouse connection
        self.clickhouse_provider.close()
        super().close()


def create_clickhouse_item_exporter(
    clickhouse_uri: str,
    database: str = 'solana',
    batch_size: int = 1000,
    enable_batch_insert: bool = True
) -> ClickHouseItemExporter:
    """Create ClickHouse item exporter with default configuration."""
    
    # Create ClickHouse provider
    clickhouse_provider = ClickHouseProvider.from_uri(clickhouse_uri)
    clickhouse_provider.database = database
    
    # Default item type to table mapping
    item_type_to_table_mapping = {
        'block': 'blocks',
        'transaction': 'transactions',
        'instruction': 'instructions',
        'token_transfer': 'token_transfers',
        'dex_trade': 'dex_trades',
        'account': 'accounts',
        'token': 'tokens',
    }
    
    return ClickHouseItemExporter(
        clickhouse_provider=clickhouse_provider,
        item_type_to_table_mapping=item_type_to_table_mapping,
        batch_size=batch_size,
        enable_batch_insert=enable_batch_insert
    )