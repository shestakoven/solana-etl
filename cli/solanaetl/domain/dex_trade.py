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


from typing import List, Optional

class DexTrade(object):
    def __init__(self) -> None:
        self.pool_address: Optional[str] = None
        self.wallet_address: Optional[str] = None
        self.token_addresses: List[str] = []  # List of token addresses involved in the trade
        self.token_amounts: List[float] = []    # List of float amounts (positive for sell, negative for buy)
        self.usd_amount: Optional[float] = None     # Total USD value of the trade
        self.token_prices: List[float] = []     # List of token prices at time of trade
        self.dex_name: Optional[str] = None       # Name of the DEX (raydium, orca, jupiter, meteora, openbook)
        self.tx_signature: Optional[str] = None   # Transaction signature
        self.block_time: Optional[int] = None     # Block timestamp
        self.instruction_index: Optional[int] = None  # Index of the instruction within the transaction