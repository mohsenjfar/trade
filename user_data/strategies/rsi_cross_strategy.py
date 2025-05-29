from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date,
    stoploss_from_absolute
)
import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from datetime import datetime, timedelta
from typing import Optional
from freqtrade.persistence import Trade

class RSICrossStrategy(IStrategy):
    
    INTERFACE_VERSION = 3
    
    stoploss = -1
    
    timeframe = '15m'

    use_exit_signal = False

    use_custom_stoploss = True
    
    can_short: bool = True
    
    process_only_new_candles = True


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['rsi'], 30)
            ), "enter_long"] = 1
    
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['rsi'], 70)
            ), "enter_short"] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        pre_candle = dataframe.iloc[-1].squeeze()

        conditions = (
            pre_candle.rsi < 30 and trade.is_short,
            pre_candle.rsi > 70 and not trade.is_short
        )

        if any(conditions):
            return current_profit * 0.3

        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        stop = pre_trade_candle.high if trade.is_short else pre_trade_candle.low
        
        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )




