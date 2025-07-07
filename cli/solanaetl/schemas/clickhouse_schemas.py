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


"""ClickHouse table schemas for Solana ETL entities."""

# Blocks table schema
BLOCKS_TABLE_SCHEMA = """
(
    hash String,
    slot UInt64,
    parent_hash String,
    block_height Nullable(UInt64),
    block_time Nullable(DateTime64(3)),
    previous_blockhash String,
    rewards Array(String),
    timestamp UInt64
) ENGINE = MergeTree()
ORDER BY (slot, block_time)
PARTITION BY toYYYYMM(block_time)
"""

# Transactions table schema
TRANSACTIONS_TABLE_SCHEMA = """
(
    signature String,
    slot UInt64,
    error Nullable(String),
    fee UInt64,
    pre_balances Array(UInt64),
    post_balances Array(UInt64),
    pre_token_balances Array(String),
    post_token_balances Array(String),
    account_keys Array(String),
    log_messages Array(String),
    instructions_count UInt32,
    inner_instructions_count UInt32,
    block_time Nullable(DateTime64(3)),
    block_hash String,
    successful UInt8
) ENGINE = MergeTree()
ORDER BY (slot, block_time, signature)
PARTITION BY toYYYYMM(block_time)
"""

# Instructions table schema
INSTRUCTIONS_TABLE_SCHEMA = """
(
    tx_signature String,
    slot UInt64,
    block_time Nullable(DateTime64(3)),
    instruction_index UInt32,
    program String,
    program_id String,
    accounts Array(String),
    data String,
    instruction_type Nullable(String),
    params String,
    inner_instruction UInt8,
    parent_instruction_index Nullable(UInt32)
) ENGINE = MergeTree()
ORDER BY (slot, block_time, tx_signature, instruction_index)
PARTITION BY toYYYYMM(block_time)
"""

# Token transfers table schema
TOKEN_TRANSFERS_TABLE_SCHEMA = """
(
    source Nullable(String),
    destination Nullable(String),
    authority Nullable(String),
    value Nullable(Float64),
    decimals Nullable(UInt32),
    mint Nullable(String),
    mint_authority Nullable(String),
    transfer_type Nullable(String),
    tx_signature String,
    slot UInt64,
    block_time Nullable(DateTime64(3))
) ENGINE = MergeTree()
ORDER BY (slot, block_time, tx_signature)
PARTITION BY toYYYYMM(block_time)
"""

# DEX trades table schema
DEX_TRADES_TABLE_SCHEMA = """
(
    pool_address Nullable(String),
    wallet_address Nullable(String),
    token_addresses Array(String),
    token_amounts Array(Float64),
    usd_amount Nullable(Float64),
    token_prices Array(Float64),
    dex_name Nullable(String),
    tx_signature Nullable(String),
    block_time Nullable(DateTime64(3)),
    instruction_index Nullable(UInt32),
    slot UInt64
) ENGINE = MergeTree()
ORDER BY (slot, block_time, tx_signature, instruction_index)
PARTITION BY toYYYYMM(block_time)
"""

# Accounts table schema
ACCOUNTS_TABLE_SCHEMA = """
(
    address String,
    lamports UInt64,
    owner String,
    executable UInt8,
    rent_epoch UInt64,
    data String,
    slot UInt64,
    block_time Nullable(DateTime64(3))
) ENGINE = ReplacingMergeTree(slot)
ORDER BY (address, slot)
PARTITION BY toYYYYMM(block_time)
"""

# Tokens table schema
TOKENS_TABLE_SCHEMA = """
(
    address String,
    mint_authority Nullable(String),
    supply UInt64,
    decimals UInt32,
    is_initialized UInt8,
    freeze_authority Nullable(String),
    slot UInt64,
    block_time Nullable(DateTime64(3))
) ENGINE = ReplacingMergeTree(slot)
ORDER BY (address, slot)
PARTITION BY toYYYYMM(block_time)
"""

# Mapping of table names to schemas
TABLE_SCHEMAS = {
    'blocks': BLOCKS_TABLE_SCHEMA,
    'transactions': TRANSACTIONS_TABLE_SCHEMA,
    'instructions': INSTRUCTIONS_TABLE_SCHEMA,
    'token_transfers': TOKEN_TRANSFERS_TABLE_SCHEMA,
    'dex_trades': DEX_TRADES_TABLE_SCHEMA,
    'accounts': ACCOUNTS_TABLE_SCHEMA,
    'tokens': TOKENS_TABLE_SCHEMA,
}

# Table creation order (some tables depend on others)
TABLE_CREATION_ORDER = [
    'blocks',
    'transactions', 
    'instructions',
    'token_transfers',
    'dex_trades',
    'accounts',
    'tokens',
]


def get_create_table_sql(table_name: str, database: str = None) -> str:
    """Get CREATE TABLE SQL for a specific table."""
    if table_name not in TABLE_SCHEMAS:
        raise ValueError(f"Unknown table: {table_name}")
    
    full_table_name = f"{database}.{table_name}" if database else table_name
    return f"CREATE TABLE IF NOT EXISTS {full_table_name} {TABLE_SCHEMAS[table_name]}"


def create_all_tables(clickhouse_provider, database: str = None):
    """Create all tables in the correct order."""
    from solanaetl.providers.clickhouse import ClickHouseProvider
    
    if database:
        clickhouse_provider.create_database_if_not_exists()
    
    for table_name in TABLE_CREATION_ORDER:
        schema = TABLE_SCHEMAS[table_name]
        full_table_name = f"{database}.{table_name}" if database else table_name
        clickhouse_provider.create_table_if_not_exists(table_name if not database else full_table_name, schema)