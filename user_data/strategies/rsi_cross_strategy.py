from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date,
    stoploss_from_absolute,
    informative
)
import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from datetime import datetime, timedelta
from typing import Optional
from freqtrade.persistence import Trade
from base import Base

class RSICrossStrategy(Base):

    # @informative('4h')
    # def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
    #     dataframe['rsi'] = ta.RSI(dataframe, 14)
    #     dataframe['rsi_max_index'] = dataframe[dataframe['rsi'] > 70].index.max()
    #     dataframe['rsi_min_index'] = dataframe[dataframe['rsi'] < 30].index.max()

    #     return dataframe

    # @informative('1d')
    # def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
    #     dataframe['rsi'] = ta.RSI(dataframe, 14)
    #     dataframe['rsi_max_index'] = dataframe[dataframe['rsi'] > 70].index.max()
    #     dataframe['rsi_min_index'] = dataframe[dataframe['rsi'] < 30].index.max()

    #     return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['rsi'], 30) #&
                # (dataframe['rsi_min_index_4h'] > dataframe['rsi_max_index_4h'] ) &
                # (dataframe['rsi_min_index_1d'] > dataframe['rsi_max_index_1d'] ) &
                # (dataframe['rsi_4h'] > 30 ) & 
                # (dataframe['rsi_4h'] < 50 ) &
                # (dataframe['rsi_1d'] > 30 ) & 
                # (dataframe['rsi_1d'] < 50 )
            ), "enter_long"] = 1
    
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['rsi'], 70) #&
                # (dataframe['rsi_max_index_4h'] > dataframe['rsi_min_index_4h'] ) &
                # (dataframe['rsi_max_index_1d'] > dataframe['rsi_min_index_1d'] ) &
                # (dataframe['rsi_4h'] < 70 ) &
                # (dataframe['rsi_4h'] > 50 ) &
                # (dataframe['rsi_1d'] < 70 ) &
                # (dataframe['rsi_1d'] > 50 )
            ), "enter_short"] = 1

        return dataframe


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        pre_candle = dataframe.iloc[-1].squeeze()

        conditions = (
            pre_candle['rsi'] < 30 and trade.is_short,
            pre_candle['rsi'] > 70 and not trade.is_short
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




