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


class CT(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = '5m'

    stoploss = -0.5

    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe)
        dataframe[f'ema5'] = ta.EMA(dataframe, timeperiod=5)
        dataframe[f'ema10'] = ta.EMA(dataframe, timeperiod=10)
        dataframe[f'ema30'] = ta.EMA(dataframe, timeperiod=30)
        dataframe[f'sma5'] = ta.SMA(dataframe, timeperiod=5)
        dataframe[f'sma10'] = ta.SMA(dataframe, timeperiod=10)
        dataframe[f'sma30'] = ta.SMA(dataframe, timeperiod=30)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
            ),
            'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
            ),
            'exit_long'] = 0
        return dataframe