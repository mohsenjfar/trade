import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union
from functools import reduce

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy, merge_informative_pair)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class LS(IStrategy):


    INTERFACE_VERSION = 3

    timeframe = '5m'

    stoploss = -0.5

    can_short: bool = False

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    buy_rsi = IntParameter(low=1, high=100, default=30, space='buy', optimize=True)
    buy_ema_short = IntParameter(3, 50, default=5, space='buy', optimize=True)
    buy_ema_long = IntParameter(15, 200, default=50, space='buy', optimize=True)

    sell_rsi = IntParameter(low=1, high=100, default=70, space='sell', optimize=True)

    # Buy hyperspace params:
    buy_params = {
        "buy_ema_long": 30,
        "buy_ema_short": 40,
        "buy_rsi": 62,
    }

    # Sell hyperspace params:
    sell_params = {
        "sell_rsi": 53,
    }
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
 
        for val in self.buy_ema_short.range:
            dataframe[f'ema_short_{val}'] = ta.EMA(dataframe, timeperiod=val)

        for val in self.buy_ema_long.range:
            dataframe[f'ema_long_{val}'] = ta.EMA(dataframe, timeperiod=val)

        dataframe['rsi'] = ta.RSI(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        conditions = []
        conditions.append(qtpylib.crossed_above(
                dataframe[f'ema_short_{self.buy_ema_short.value}'], dataframe[f'ema_long_{self.buy_ema_long.value}']
            ))
        
        conditions.append(dataframe['rsi'] < self.buy_rsi.value)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        conditions = []
        conditions.append(qtpylib.crossed_above(
                dataframe[f'ema_long_{self.buy_ema_long.value}'], dataframe[f'ema_short_{self.buy_ema_short.value}']
            ))
        
        conditions.append(dataframe['rsi'] > self.sell_rsi.value)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'] = 1
        
        return dataframe