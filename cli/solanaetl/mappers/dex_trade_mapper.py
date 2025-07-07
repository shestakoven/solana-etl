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


from typing import Dict

from solanaetl.domain.dex_trade import DexTrade


class DexTradeMapper(object):

    def to_dict(self, dex_trade: DexTrade) -> Dict:
        return {
            'type': 'dex_trade',
            'pool_address': dex_trade.pool_address,
            'wallet_address': dex_trade.wallet_address,
            'token_addresses': dex_trade.token_addresses,
            'token_amounts': dex_trade.token_amounts,
            'usd_amount': dex_trade.usd_amount,
            'token_prices': dex_trade.token_prices,
            'dex_name': dex_trade.dex_name,
            'tx_signature': dex_trade.tx_signature,
            'block_time': dex_trade.block_time,
            'instruction_index': dex_trade.instruction_index,
        }