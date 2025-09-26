import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative
)
from datetime import datetime
from typing import Optional

class SMACross(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '1m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['sma_low'] = ta.SMA(dataframe, timeperiod=5)
        dataframe['sma_medium'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_high'] = ta.SMA(dataframe, timeperiod=100)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['sl'] = dataframe['close'] - dataframe['atr'] * 1.5
        dataframe['ss'] = dataframe['close'] + dataframe['atr'] * 1.5

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['sma_medium'] > dataframe['sma_high']) & # Guard
                (qtpylib.crossed_above(dataframe['sma_low'], dataframe['sma_medium'])) # Trigger
            ), "enter_long"] = 1

        dataframe.loc[
            (
                (dataframe['sma_medium'] < dataframe['sma_high']) & # Guard
                (qtpylib.crossed_below(dataframe['sma_low'], dataframe['sma_medium'])) # Trigger
            ), "enter_long"] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stop = last_candle.ss if side == "short" else last_candle.sl
        risk = abs(stop / last_candle.close - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        return stoploss_from_absolute(
            last_candle.ss if trade.is_short else last_candle.sl,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )
