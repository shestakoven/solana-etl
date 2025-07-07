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


import json
import logging
from typing import Optional, List, Dict, Any

from solanaetl.domain.instruction import Instruction
from solanaetl.domain.dex_trade import DexTrade

# DEX Program IDs
RAYDIUM_PROGRAMS = {
    'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C': 'raydium',  # Standard AMM (CP-Swap)
    '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8': 'raydium',  # Legacy AMM v4
    'CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK': 'raydium',  # Concentrated Liquidity
    '5quBtoiQqxF9Jv6KYKctB59NT3gtJD2Y65kdnB1Uev3h': 'raydium',  # Stable Swap AMM
}

ORCA_PROGRAMS = {
    'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc': 'orca',     # Main Orca program
    'DjVE6JNiYqPL2QXyCUUh8rNjHrbz9hXHNYt99MQ59qw1': 'orca',    # Token Swap
    '9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP': 'orca',    # Token Swap V2
}

JUPITER_PROGRAMS = {
    'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4': 'jupiter',  # Jupiter v6
    'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB': 'jupiter',  # Jupiter v4
    'JUP3c2Uh3WA4Ng34tw6kPd2G4C5BB21Xo36Je1s32Ph': 'jupiter',  # Jupiter v3
}

METEORA_PROGRAMS = {
    'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo': 'meteora',  # DLMM Program
    'Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB': 'meteora',  # Dynamic AMM Pools
    '24Uqj9JCLxUeoC3hGfh5W3s9FM9uCHDS2SG3LYwBpyTi': 'meteora',  # Vault Program
}

OPENBOOK_PROGRAMS = {
    'srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX': 'openbook',  # OpenBook
    '9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin': 'openbook',  # Serum DEX V3
    'EUqojwWA2rd19FZrzeBncJsm38Jm1hEhE3zsmX3bRc2o': 'openbook',  # Serum DEX V2
}

# All supported DEX programs
ALL_DEX_PROGRAMS = {**RAYDIUM_PROGRAMS, **ORCA_PROGRAMS, **JUPITER_PROGRAMS, **METEORA_PROGRAMS, **OPENBOOK_PROGRAMS}

# Common swap instruction types
SWAP_INSTRUCTIONS = [
    'swap', 'swapV2', 'swapBaseIn', 'swapBaseOut',
    'route', 'routeWithTokenLedger', 'exactOutRoute', 'sharedAccountsRoute',
    'twoHopSwap', 'multiHopSwap', 'clmmSwap',
    'newOrder', 'settleFunds', 'cancelOrder'
]

logger = logging.getLogger(__name__)


def extract_dex_trade_from_instruction(instruction: Instruction) -> Optional[DexTrade]:
    """
    Extract DEX trade information from a blockchain instruction.
    
    Args:
        instruction: The blockchain instruction to parse
        
    Returns:
        DexTrade object if the instruction represents a DEX trade, None otherwise
    """
    try:
        # Check if this instruction is from a supported DEX
        if not instruction.program:
            return None
            
        dex_name = ALL_DEX_PROGRAMS.get(instruction.program)
        if not dex_name:
            return None
            
        # Check if this is a trading instruction
        if not _is_trade_instruction(instruction):
            return None
            
        dex_trade = DexTrade()
        dex_trade.dex_name = dex_name
        dex_trade.tx_signature = instruction.tx_signature
        dex_trade.instruction_index = getattr(instruction, 'instruction_index', None)
        
        # Extract trade data based on DEX type
        if dex_name == 'raydium':
            _extract_raydium_trade(instruction, dex_trade)
        elif dex_name == 'orca':
            _extract_orca_trade(instruction, dex_trade)
        elif dex_name == 'jupiter':
            _extract_jupiter_trade(instruction, dex_trade)
        elif dex_name == 'meteora':
            _extract_meteora_trade(instruction, dex_trade)
        elif dex_name == 'openbook':
            _extract_openbook_trade(instruction, dex_trade)
        else:
            return None
            
        # Only return if we have minimum required data
        if dex_trade.wallet_address and dex_trade.token_addresses:
            return dex_trade
            
    except Exception as e:
        logger.warning(f"Error extracting DEX trade from instruction: {e}")
        
    return None


def _is_trade_instruction(instruction: Instruction) -> bool:
    """Check if the instruction represents a trading operation."""
    if not instruction.instruction_type:
        return False
        
    instruction_type_lower = instruction.instruction_type.lower()
    return any(swap_type in instruction_type_lower for swap_type in SWAP_INSTRUCTIONS)


def _extract_raydium_trade(instruction: Instruction, dex_trade: DexTrade) -> None:
    """Extract trade data from Raydium instructions."""
    params = instruction.params or {}
    
    # Extract wallet address (authority or user)
    dex_trade.wallet_address = params.get('authority') or params.get('userTokenAccountOwner') or params.get('userSourceOwner')
    
    # Extract pool information
    dex_trade.pool_address = params.get('ammId') or params.get('poolId') or params.get('market')
    
    # Extract token information
    token_addresses = []
    token_amounts = []
    
    # Handle different Raydium instruction formats
    if 'tokenAccountIn' in params and 'tokenAccountOut' in params:
        token_addresses.append(params.get('mintIn'))
        token_addresses.append(params.get('mintOut'))
        
        amount_in = _safe_float(params.get('amountIn', 0))
        amount_out = _safe_float(params.get('amountOut', 0))
        
        token_amounts.append(amount_in)   # Positive for sell
        token_amounts.append(-amount_out) # Negative for buy
        
    elif 'baseTokenAccount' in params and 'quoteTokenAccount' in params:
        token_addresses.append(params.get('baseMint'))
        token_addresses.append(params.get('quoteMint'))
        
        base_amount = _safe_float(params.get('baseAmount', 0))
        quote_amount = _safe_float(params.get('quoteAmount', 0))
        
        token_amounts.append(base_amount)
        token_amounts.append(-quote_amount)
    
    dex_trade.token_addresses = [addr for addr in token_addresses if addr]
    dex_trade.token_amounts = token_amounts


def _extract_orca_trade(instruction: Instruction, dex_trade: DexTrade) -> None:
    """Extract trade data from Orca instructions."""
    params = instruction.params or {}
    
    dex_trade.wallet_address = params.get('authority') or params.get('userTransferAuthority')
    dex_trade.pool_address = params.get('whirlpool') or params.get('swapProgram')
    
    token_addresses = []
    token_amounts = []
    
    if 'tokenMintA' in params and 'tokenMintB' in params:
        token_addresses.append(params.get('tokenMintA'))
        token_addresses.append(params.get('tokenMintB'))
        
        amount_a = _safe_float(params.get('amountA', 0))
        amount_b = _safe_float(params.get('amountB', 0))
        
        # Determine direction based on amounts
        if amount_a > 0 and amount_b < 0:
            token_amounts.append(amount_a)
            token_amounts.append(amount_b)
        else:
            token_amounts.append(-amount_a)
            token_amounts.append(amount_b)
    
    dex_trade.token_addresses = [addr for addr in token_addresses if addr]
    dex_trade.token_amounts = token_amounts


def _extract_jupiter_trade(instruction: Instruction, dex_trade: DexTrade) -> None:
    """Extract trade data from Jupiter instructions."""
    params = instruction.params or {}
    
    dex_trade.wallet_address = params.get('userSourceOwner') or params.get('authority')
    
    # Jupiter often aggregates across multiple pools
    dex_trade.pool_address = params.get('destinationPool') or 'jupiter_aggregated'
    
    token_addresses = []
    token_amounts = []
    
    if 'sourceMint' in params and 'destinationMint' in params:
        token_addresses.append(params.get('sourceMint'))
        token_addresses.append(params.get('destinationMint'))
        
        source_amount = _safe_float(params.get('sourceAmount', 0))
        destination_amount = _safe_float(params.get('destinationAmount', 0))
        
        token_amounts.append(source_amount)      # Positive for sell
        token_amounts.append(-destination_amount) # Negative for buy
    
    dex_trade.token_addresses = [addr for addr in token_addresses if addr]
    dex_trade.token_amounts = token_amounts


def _extract_meteora_trade(instruction: Instruction, dex_trade: DexTrade) -> None:
    """Extract trade data from Meteora instructions."""
    params = instruction.params or {}
    
    dex_trade.wallet_address = params.get('user') or params.get('authority')
    dex_trade.pool_address = params.get('lbPair') or params.get('pool')
    
    token_addresses = []
    token_amounts = []
    
    if 'tokenXMint' in params and 'tokenYMint' in params:
        token_addresses.append(params.get('tokenXMint'))
        token_addresses.append(params.get('tokenYMint'))
        
        amount_x = _safe_float(params.get('amountX', 0))
        amount_y = _safe_float(params.get('amountY', 0))
        
        token_amounts.append(amount_x)
        token_amounts.append(-amount_y)
    
    dex_trade.token_addresses = [addr for addr in token_addresses if addr]
    dex_trade.token_amounts = token_amounts


def _extract_openbook_trade(instruction: Instruction, dex_trade: DexTrade) -> None:
    """Extract trade data from OpenBook/Serum instructions."""
    params = instruction.params or {}
    
    dex_trade.wallet_address = params.get('owner') or params.get('orderPayer')
    dex_trade.pool_address = params.get('market')
    
    token_addresses = []
    token_amounts = []
    
    if 'baseMint' in params and 'quoteMint' in params:
        token_addresses.append(params.get('baseMint'))
        token_addresses.append(params.get('quoteMint'))
        
        base_quantity = _safe_float(params.get('baseQuantity', 0))
        quote_quantity = _safe_float(params.get('quoteQuantity', 0))
        
        # Determine buy/sell based on instruction type or side
        side = params.get('side', '').lower()
        if side == 'buy':
            token_amounts.append(-base_quantity)  # Buying base
            token_amounts.append(quote_quantity)  # Selling quote
        else:  # sell or default
            token_amounts.append(base_quantity)   # Selling base
            token_amounts.append(-quote_quantity) # Buying quote
    
    dex_trade.token_addresses = [addr for addr in token_addresses if addr]
    dex_trade.token_amounts = token_amounts


def _safe_float(value: Any) -> float:
    """Safely convert a value to float."""
    try:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
        return 0.0
    except (ValueError, TypeError):
        return 0.0


def _extract_token_prices(token_addresses: List[str], block_time: int) -> List[float]:
    """
    Extract token prices at the time of the trade.
    This is a placeholder - in a real implementation, you would query price oracles or APIs.
    """
    # TODO: Implement price fetching from Pyth, Switchboard, or other price oracles
    # For now, return empty list - prices would need to be populated by external service
    return [0.0] * len(token_addresses)


def _calculate_usd_amount(token_amounts: List[float], token_prices: List[float]) -> float:
    """Calculate the total USD amount of the trade."""
    if len(token_amounts) != len(token_prices):
        return 0.0
        
    total_usd = 0.0
    for amount, price in zip(token_amounts, token_prices):
        total_usd += abs(amount) * price
        
    return total_usd / 2  # Divide by 2 to avoid double counting