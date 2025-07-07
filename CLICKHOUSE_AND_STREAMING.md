# ClickHouse Storage and Streaming Implementation

## Overview

This implementation adds comprehensive ClickHouse storage support and a continuous streaming mode for the Solana ETL project. The streaming mode continuously monitors the blockchain for new blocks and exports all entities infinitely.

## Features Added

### 1. ClickHouse Storage Support
- **Full ClickHouse integration** with optimized table schemas
- **Batch insertion** for high-performance data loading
- **Connection management** with URI-based configuration
- **Automatic table creation** with proper schemas
- **Type conversion** and data preprocessing for ClickHouse compatibility

### 2. Streaming Mode (Run Command)
- **Continuous export** of all entities on new blocks
- **Graceful shutdown** handling with signal management
- **Configurable entity types** (blocks, transactions, instructions, token transfers, DEX trades, accounts, tokens)
- **Dual output support** (ClickHouse or CSV files)
- **Error recovery** with automatic retry logic
- **State tracking** to resume from last processed block

## Implementation Components

### ClickHouse Components

#### 1. ClickHouse Provider (`cli/solanaetl/providers/clickhouse.py`)
- **Connection management**: URI-based connection with support for secure connections
- **Query execution**: Methods for executing SQL queries and bulk insertions
- **Database management**: Automatic database and table creation
- **Error handling**: Robust error handling with logging

```python
# Example usage
provider = ClickHouseProvider.from_uri('clickhouse://user:password@localhost:9000/solana')
provider.create_database_if_not_exists()
provider.insert('blocks', data, columns)
```

#### 2. Table Schemas (`cli/solanaetl/schemas/clickhouse_schemas.py`)
Optimized ClickHouse table schemas for all entity types:

- **Blocks**: MergeTree engine with slot/time ordering and monthly partitioning
- **Transactions**: Indexed by slot, time, and signature
- **Instructions**: Optimized for instruction-level queries
- **Token Transfers**: Efficient storage for token movement tracking
- **DEX Trades**: Specialized schema for DEX trade analysis
- **Accounts**: ReplacingMergeTree for account state tracking
- **Tokens**: Token metadata storage with versioning

#### 3. ClickHouse Item Exporter (`cli/solanaetl/jobs/exporters/clickhouse_item_exporter.py`)
- **Batch processing**: Configurable batch sizes for optimal performance
- **Type conversion**: Automatic conversion of timestamps and arrays
- **Multi-table support**: Routes different entity types to appropriate tables
- **Buffer management**: Intelligent buffering and flushing

### Streaming Components

#### 1. Run Command (`cli/solanaetl/cli/run.py`)
CLI interface for continuous streaming:

```bash
# Export to ClickHouse
solanaetl run --clickhouse-uri clickhouse://localhost:9000/solana

# Export to CSV files  
solanaetl run --output-dir ./output

# Configure entity types
solanaetl run --clickhouse-uri clickhouse://localhost:9000/solana \
  --enable-dex-trades=true \
  --enable-token-transfers=true \
  --start-block 250000000
```

#### 2. Streaming Job (`cli/solanaetl/jobs/run_streaming_job.py`)
Core streaming engine:
- **Block monitoring**: Continuously polls for new blocks
- **Batch processing**: Processes blocks in configurable batches
- **Entity extraction**: Coordinates extraction of all entity types
- **State management**: Tracks last processed block for resumption

### Updated Dependencies (`cli/setup.py`)
Added ClickHouse driver dependency:
```python
install_requires=[
    # ... existing dependencies ...
    "clickhouse-driver>=0.2.0",
]
```

## Table Schemas

### Optimized for Analytics

All tables use appropriate ClickHouse engines and are optimized for analytics workloads:

```sql
-- Blocks table (MergeTree with time partitioning)
CREATE TABLE blocks (
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

-- DEX Trades table (optimized for trade analysis)
CREATE TABLE dex_trades (
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
```

## Usage Examples

### Basic Streaming to ClickHouse

```bash
# Start streaming all entities to ClickHouse
solanaetl run \
  --clickhouse-uri clickhouse://localhost:9000/solana \
  --provider-uri https://api.mainnet-beta.solana.com \
  --max-workers 5 \
  --batch-size 10 \
  --poll-interval 10
```

### Streaming Specific Entities

```bash
# Stream only DEX trades and token transfers
solanaetl run \
  --clickhouse-uri clickhouse://localhost:9000/solana \
  --enable-blocks=false \
  --enable-transactions=false \
  --enable-instructions=false \
  --enable-accounts=false \
  --enable-tokens=false \
  --enable-dex-trades=true \
  --enable-token-transfers=true
```

### CSV Export Mode

```bash
# Export to CSV files
solanaetl run \
  --output-dir ./solana_data \
  --start-block 250000000 \
  --batch-size 50 \
  --max-workers 10
```

### Production Configuration

```bash
# Production streaming with optimized settings
solanaetl run \
  --clickhouse-uri clickhouse://user:password@clickhouse.example.com:9000/solana \
  --provider-uri https://your-solana-rpc.com \
  --max-workers 10 \
  --batch-size 20 \
  --block-batch-size 1 \
  --poll-interval 5 \
  --lag 2 \
  --clickhouse-batch-size 2000 \
  --log-level INFO
```

## Configuration Options

### ClickHouse Connection
- **URI format**: `clickhouse://[user[:password]@]host[:port]/database`
- **Secure connection**: `clickhouses://` for TLS connections
- **Database**: Automatically created if not exists

### Streaming Parameters
- **Provider URI**: Solana RPC endpoint
- **Start block**: Block number to start from (default: latest)
- **Batch size**: Number of blocks per iteration
- **Poll interval**: Seconds between blockchain polling
- **Lag**: Blocks to stay behind latest (for stability)
- **Max workers**: Concurrent processing threads

### Entity Types
All entity types can be individually enabled/disabled:
- `blocks` - Blockchain blocks
- `transactions` - Transaction data
- `instructions` - Program instructions
- `token_transfers` - SPL token movements
- `dex_trades` - DEX trades from 5 major DEXes
- `accounts` - Account states
- `tokens` - Token metadata

## Performance Optimizations

### ClickHouse Optimizations
- **Batch insertions**: Configurable batch sizes (default: 1000)
- **Partitioning**: Monthly partitions for time-based queries
- **Compression**: Automatic compression for storage efficiency
- **Indexing**: Optimized sort keys for common query patterns

### Streaming Optimizations
- **Parallel processing**: Multi-threaded entity extraction
- **Memory management**: Efficient buffering and batch processing
- **Error recovery**: Automatic retry with exponential backoff
- **State persistence**: Resume from last processed block

## Monitoring and Debugging

### Logging
Comprehensive logging with configurable levels:
```bash
--log-level DEBUG  # Detailed debugging information
--log-level INFO   # General operational information  
--log-level WARNING # Warnings and errors only
--log-level ERROR  # Errors only
```

### SQL Debugging
```bash
--print-sql=true  # Print SQL statements for debugging
```

### Graceful Shutdown
The streaming process handles shutdown signals gracefully:
- **SIGINT** (Ctrl+C): Graceful shutdown
- **SIGTERM**: Graceful shutdown with cleanup

## Installation and Setup

### 1. Install Dependencies
```bash
cd cli
pip install -e .  # This will install clickhouse-driver
```

### 2. Setup ClickHouse
```bash
# Using Docker
docker run -d \
  --name clickhouse-server \
  -p 9000:9000 \
  -p 8123:8123 \
  clickhouse/clickhouse-server

# Using native installation
# See ClickHouse documentation for OS-specific instructions
```

### 3. Start Streaming
```bash
solanaetl run --clickhouse-uri clickhouse://localhost:9000/solana
```

## Integration with Existing Workflows

### Airflow Integration
The streaming mode complements the existing Airflow DAGs:
- **Batch mode**: Use Airflow for historical data processing
- **Streaming mode**: Use `run` command for real-time processing
- **Hybrid approach**: Combine both for comprehensive coverage

### Data Analysis
ClickHouse enables powerful analytics:
```sql
-- Top DEX trading volumes by day
SELECT 
    toDate(block_time) as date,
    dex_name,
    sum(usd_amount) as volume
FROM dex_trades 
WHERE block_time >= yesterday()
GROUP BY date, dex_name
ORDER BY volume DESC;

-- Token transfer patterns
SELECT 
    mint,
    count() as transfer_count,
    sum(value) as total_volume
FROM token_transfers
WHERE block_time >= today() - INTERVAL 7 DAY
GROUP BY mint
ORDER BY transfer_count DESC
LIMIT 10;
```

## Future Enhancements

### Planned Features
- **Real-time price integration** with Pyth/Switchboard oracles
- **Advanced MEV detection** in DEX trades
- **Cross-chain bridge tracking** for wrapped tokens
- **DeFi protocol-specific extractors** (lending, staking, etc.)
- **Materialized views** for common analytics queries

### Performance Improvements
- **Parallel entity processing** within single blocks
- **Compressed data formats** for inter-service communication
- **Incremental processing** for dependent entities
- **Caching layers** for frequently accessed data

This implementation provides a solid foundation for real-time Solana blockchain analytics with ClickHouse as the high-performance storage backend.