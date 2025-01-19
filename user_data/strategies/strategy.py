# importing freqtrade modules
from freqtrade.persistence import Trade, Order
from freqtrade.strategy import IStrategy, stoploss_from_open

# importing calculation modules
import pandas as pd
from pandas import DataFrame
import numpy as np
from technical import qtpylib
import talib.abstract as ta
from scipy.signal import argrelextrema

# importing other modules
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '1m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 48

    process_only_new_candles = False

    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    
    def bot_loop_start(self, **kwargs) -> None:
        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'], is_open=False)
        if trades:
            if trades[-1].is_short:
                dataframe['enter_long'] = 1
            else:
                dataframe['enter_short'] = 1
            return dataframe
        
        dataframe['enter_long'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:


        if current_profit > 0.1:
            return 0.03

        if current_profit > 0.005:
            return stoploss_from_open(
                0,
                current_profit, 
                is_short=trade.is_short, 
                leverage=trade.leverage
            )

        return -1
