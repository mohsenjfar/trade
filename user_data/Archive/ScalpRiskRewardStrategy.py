import pandas as pd
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class ScalpRiskRewardStrategy(IStrategy):
    # تنظیمات استراتژی
    minimal_roi = {
        "0": 0.05,
        "10": 0.03,
        "30": 0.02,
        "60": 0.01
    }
    stoploss = -0.01
    timeframe = '5m'
    trailing_stop = True
    trailing_stop_positive = 0.02


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        bollinger = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['lower_bb'] = bollinger['lowerband']
        dataframe['middle_bb'] = bollinger['middleband']
        dataframe['upper_bb'] = bollinger['upperband']
        
        return dataframe

    # قوانین خرید
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema200']) &
                (dataframe['rsi'] < 30) &
                (dataframe['close'] < dataframe['lower_bb']) &
                qtpylib.crossed_above(
                    dataframe[f'ema_short_{self.ema_short_timeperiod.value}'], 
                    dataframe[f'ema_long_{self.ema_long_timeperiod.value}']
            )
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['ema200']) &
                (dataframe['rsi'] > 70) &
                (dataframe['close'] > dataframe['upper_bb'])
            ),
            'enter_short'] = 1
        
        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        return dataframe

