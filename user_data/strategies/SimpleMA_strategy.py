# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy, merge_informative_pair)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class SimpleMA_strategy(IStrategy):

    minimal_roi = {
        "0": 100
    }

    stoploss = -1.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        fast_period = 5
        slow_period = 50
        dataframe['fast_MA'] = ta.SMA(dataframe, timeperiod=fast_period)
        dataframe['slow_MA'] = ta.SMA(dataframe, timeperiod=slow_period)
        
        return dataframe


    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
          (
            qtpylib.crossed_above(dataframe['fast_MA'], dataframe['slow_MA'])
          ),
          'buy'] = 1
        
        return dataframe


    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
          (
            qtpylib.crossed_below(dataframe['fast_MA'], dataframe['slow_MA'])
          ),
          'sell'
        ] = 1
        
        return dataframe