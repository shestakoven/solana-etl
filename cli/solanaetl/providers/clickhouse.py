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
from urllib.parse import urlparse
from typing import Optional, Dict, Any

from clickhouse_driver import Client


logger = logging.getLogger(__name__)


class ClickHouseProvider:
    """ClickHouse connection provider for Solana ETL."""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 9000,
        database: str = 'solana',
        user: str = 'default',
        password: str = '',
        secure: bool = False,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.secure = secure
        self.kwargs = kwargs
        self._client = None
        
    @classmethod
    def from_uri(cls, uri: str) -> 'ClickHouseProvider':
        """Create ClickHouse provider from connection URI.
        
        Example URIs:
        - clickhouse://localhost:9000/solana
        - clickhouse://user:password@localhost:9000/solana
        - clickhouses://user:password@localhost:9440/solana (secure)
        """
        parsed = urlparse(uri)
        
        if parsed.scheme not in ('clickhouse', 'clickhouses'):
            raise ValueError(f"Invalid ClickHouse URI scheme: {parsed.scheme}")
            
        return cls(
            host=parsed.hostname or 'localhost',
            port=parsed.port or (9440 if parsed.scheme == 'clickhouses' else 9000),
            database=parsed.path.lstrip('/') or 'solana',
            user=parsed.username or 'default',
            password=parsed.password or '',
            secure=parsed.scheme == 'clickhouses'
        )
    
    @property
    def client(self) -> Client:
        """Get or create ClickHouse client."""
        if self._client is None:
            self._client = Client(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                secure=self.secure,
                **self.kwargs
            )
        return self._client
    
    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute SQL query."""
        logger.debug(f"Executing ClickHouse query: {query}")
        return self.client.execute(query, params or {})
    
    def execute_with_progress(self, query: str, params: Optional[Dict[str, Any]] = None):
        """Execute SQL query with progress tracking."""
        logger.debug(f"Executing ClickHouse query with progress: {query}")
        return self.client.execute_with_progress(query, params or {})
    
    def insert(self, table: str, data: list, columns: Optional[list] = None) -> None:
        """Insert data into table."""
        logger.debug(f"Inserting {len(data)} rows into {table}")
        if columns:
            self.client.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES", data)
        else:
            self.client.execute(f"INSERT INTO {table} VALUES", data)
    
    def create_database_if_not_exists(self) -> None:
        """Create database if it doesn't exist."""
        query = f"CREATE DATABASE IF NOT EXISTS {self.database}"
        logger.info(f"Creating database: {self.database}")
        self.execute(query)
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        query = """
        SELECT count() 
        FROM system.tables 
        WHERE database = %(database)s AND name = %(table)s
        """
        result = self.execute(query, {'database': self.database, 'table': table_name})
        return result[0][0] > 0
    
    def create_table_if_not_exists(self, table_name: str, schema: str) -> None:
        """Create table if it doesn't exist."""
        if not self.table_exists(table_name):
            query = f"CREATE TABLE IF NOT EXISTS {table_name} {schema}"
            logger.info(f"Creating table: {table_name}")
            self.execute(query)
    
    def close(self) -> None:
        """Close ClickHouse connection."""
        if self._client:
            self._client.disconnect()
            self._client = None


def get_clickhouse_provider_from_uri(uri: str) -> ClickHouseProvider:
    """Get ClickHouse provider from URI."""
    return ClickHouseProvider.from_uri(uri)