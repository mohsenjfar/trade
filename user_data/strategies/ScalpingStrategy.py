import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
from freqtrade.strategy.interface import IStrategy
import talib.abstract as ta

class ScalpingStrategy(IStrategy):
    timeframe = '1m'  # تایم‌فریم 1 دقیقه‌ای برای اسکالپینگ
    stoploss = -0.01  # حد ضرر 1%
    take_profit = 0.02  # حد سود 2%
    minimal_roi = {
        "0": 0.02
    }
    use_custom_stoploss = False
    startup_candle_count: int = 30

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_short'] = ta.EMA(dataframe, timeperiod=10)
        dataframe['ema_long'] = ta.EMA(dataframe, timeperiod=30)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ema_short'] > dataframe['ema_long']) &  # سیگنال خرید زمانی که EMA کوتاه‌تر بالای EMA بلندتر باشد
                (dataframe['rsi'] < 70)  # RSI کمتر از 70 برای جلوگیری از خرید در حالت اشباع خرید
            ),
            'enter_long'] = 1
        
        dataframe.loc[
            (
                (dataframe['ema_short'] < dataframe['ema_long']) &  # سیگنال فروش زمانی که EMA کوتاه‌تر پایین EMA بلندتر باشد
                (dataframe['rsi'] > 30)  # RSI بیشتر از 30 برای جلوگیری از فروش در حالت اشباع فروش
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > 70)  # خروج از پوزیشن خرید زمانی که RSI بالای 70 است
            ),
            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['rsi'] < 30)  # خروج از پوزیشن فروش زمانی که RSI زیر 30 است
            ),
            'exit_short'] = 1

        return dataframe
