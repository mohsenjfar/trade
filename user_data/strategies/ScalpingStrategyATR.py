import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
from freqtrade.strategy import (
    IStrategy, 
    stoploss_from_absolute,
    DecimalParameter,
    IntParameter
)
import talib.abstract as ta
from freqtrade.persistence import Trade

class ScalpingStrategyATR(IStrategy):
    timeframe = '1m'
    startup_candle_count: int = 30
    can_short: bool = True
    stoploss = -0.1

    ema_short_timeperiod = IntParameter(5, 15, default=10, space='buy')
    ema_long_timeperiod = IntParameter(20, 40, default=30, space='buy')
    atr_timeperiod = IntParameter(10, 20, default=14, space='buy')
    atr_multiplier_stoploss = DecimalParameter(1, 20, decimals=1, default=10, space="buy")
    atr_multiplier_exit = DecimalParameter(1, 10, decimals=1, default=5, space="sell")
    rsi_timeperiod = IntParameter(10, 20, default=14, space='buy')
    rsi_overbought = IntParameter(60, 80, default=70, space='buy')
    rsi_oversold = IntParameter(20, 40, default=30, space='buy')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_short'] = ta.EMA(dataframe, timeperiod=self.ema_short_timeperiod.value)
        dataframe['ema_long'] = ta.EMA(dataframe, timeperiod=self.ema_long_timeperiod.value)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_timeperiod.value)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_timeperiod.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['ema_short'], dataframe['ema_long']) &
                (dataframe['rsi'] < self.rsi_overbought.value)
            ),
            'enter_long'] = 1
        
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['ema_short'], dataframe['ema_long']) &
                (dataframe['rsi'] > self.rsi_oversold.value)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > self.rsi_overbought.value)
            ),
            'exit_long'] = 1
        
        dataframe.loc[
            (
                (dataframe['rsi'] < self.rsi_oversold.value)
            ),
            'exit_short'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time, current_rate, current_profit, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        atr = dataframe['atr'].iloc[-1]
        stoploss = current_rate + self.atr_multiplier_stoploss.value * atr if trade.is_short else current_rate - self.atr_multiplier_stoploss.value * atr
        return stoploss_from_absolute(stoploss, current_rate, is_short=trade.is_short, leverage=trade.leverage)
    
    def custom_exit(self, pair: str, trade: 'Trade', current_time, current_rate, current_profit, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        atr = dataframe['atr'].iloc[-1]
        if trade.is_short:
            take_profit = trade.open_rate - self.atr_multiplier_exit.value * atr
        else:
            take_profit = trade.open_rate + self.atr_multiplier_exit.value * atr

        if (trade.is_short and current_rate <= take_profit) or (not trade.is_short and current_rate >= take_profit):
            return 'Target Hit!'
        return None