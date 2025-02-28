import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
from freqtrade.strategy.interface import IStrategy
import talib.abstract as ta

class ScalpingStrategy(IStrategy):
    timeframe = '1m'
    stoploss = -0.01
    minimal_roi = {
        "0": 0.03
    }
    use_custom_stoploss = False
    startup_candle_count: int = 30
    can_short: bool = True
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_short'] = ta.EMA(dataframe, timeperiod=10)
        dataframe['ema_long'] = ta.EMA(dataframe, timeperiod=30)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['ema_short'], dataframe['ema_long']) &
                (dataframe['rsi'] < 70)
            ),
            'enter_long'] = 1
        
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['ema_short'], dataframe['ema_long']) &
                (dataframe['rsi'] > 30)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe
