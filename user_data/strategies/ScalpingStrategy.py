import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
from functools import reduce
from freqtrade.strategy import (
    IStrategy, 
    IntParameter
)
import talib.abstract as ta

class ScalpingStrategy(IStrategy):

    startup_candle_count: int = 30
    can_short: bool = True
    minimal_roi = {
        "0": 0.04
    }
    stoploss = -0.02
    timeframe = '15m'
    trailing_stop = False
    trailing_stop_positive = 0.01

    ema_short_timeperiod = IntParameter(5, 15, default=10, space='buy')
    ema_long_timeperiod = IntParameter(20, 40, default=30, space='buy')
    rsi_timeperiod = IntParameter(10, 20, default=14, space='buy')
    rsi_overbought = IntParameter(60, 80, default=70, space='buy')
    rsi_oversold = IntParameter(20, 40, default=30, space='buy')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        for val in self.ema_short_timeperiod.range:
            dataframe[f'ema_short_{val}'] = ta.EMA(dataframe, timeperiod=val)
        
        for val in self.ema_long_timeperiod.range:
            dataframe[f'ema_long_{val}'] = ta.EMA(dataframe, timeperiod=val)

        for val in self.rsi_timeperiod.range:
            dataframe[f'rsi_{val}'] = ta.RSI(dataframe, timeperiod=val)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        conditions = []
        conditions.append(
            qtpylib.crossed_above(
                    dataframe[f'ema_short_{self.ema_short_timeperiod.value}'], 
                    dataframe[f'ema_long_{self.ema_long_timeperiod.value}']
            )
        )
        conditions.append(
            (dataframe[f'rsi_{self.rsi_timeperiod.value}'] < self.rsi_overbought.value)
        )

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        conditions = []
        conditions.append(
            qtpylib.crossed_below(
                    dataframe[f'ema_short_{self.ema_short_timeperiod.value}'], 
                    dataframe[f'ema_long_{self.ema_long_timeperiod.value}']
            )
        )

        conditions.append(
            (dataframe[f'rsi_{self.rsi_timeperiod.value}'] > self.rsi_oversold.value)
        )

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_short'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe
