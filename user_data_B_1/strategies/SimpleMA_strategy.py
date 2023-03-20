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
    """
    This is a strategy template to get you started.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_entry_trend, populate_exit_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = '5m'

    # Can this strategy go short?
    # can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    # minimal_roi = {
    #     "60": 0.01,
    #     "30": 0.02,
    #     "0": 0.04
    # }
    # minimal_roi = {
    #     "0": 100
    # }
    
    # stoploss = -0.05
    # trailing_stop = True
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.011
    # trailing_only_offset_is_reached = True

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    # stoploss = -0.10

    # # Trailing stoploss
    # trailing_stop = False
    # # trailing_only_offset_is_reached = False
    # # trailing_stop_positive = 0.01
    # # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # # Run "populate_indicators()" only for new candle.
    # process_only_new_candles = True

    # # These values can be overridden in the config.
    # use_exit_signal = True
    # exit_profit_only = False
    # ignore_roi_if_entry_signal = False

    # # Number of candles the strategy requires before producing valid signals
    # startup_candle_count: int = 30

    # # Strategy parameters
    # buy_rsi = IntParameter(10, 40, default=30, space="buy")
    # sell_rsi = IntParameter(60, 90, default=70, space="sell")

    # # Optional order type mapping.
    # order_types = {
    #     'entry': 'limit',
    #     'exit': 'limit',
    #     'stoploss': 'market',
    #     'stoploss_on_exchange': False
    # }

    # # Optional order time in force.
    # order_time_in_force = {
    #     'entry': 'GTC',
    #     'exit': 'GTC'
    # }
    

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

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