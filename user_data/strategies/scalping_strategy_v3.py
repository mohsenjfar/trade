from pandas import DataFrame
from freqtrade.strategy import (
    IStrategy,
    informative,
    stoploss_from_open,
    IntParameter
)
import talib.abstract as ta
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ScalpingStrategyV3(IStrategy):

    startup_candle_count: int = 30
    can_short: bool = True
    stoploss = -0.1
    timeframe = '15m'
    long_timeframe = "4h"
    use_exit_signal = True
    use_custom_stoploss = True

    rsi_15m_enter_long = IntParameter(10, 40, default=30, space='buy')
    rsi_15m_enter_short = IntParameter(60, 90, default=70, space='buy')
    rsi_1m_enter_short = IntParameter(10, 40, default=30, space='buy')
    rsi_1m_enter_long = IntParameter(60, 90, default=70, space='buy')
    rsi_15m_exit_short = IntParameter(10, 40, default=30, space='sell')
    rsi_15m_exit_long = IntParameter(60, 90, default=70, space='sell')


    @informative(long_timeframe)
    def populate_indicators_inf1(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe['max'] = dataframe['high'].rolling(14).max()
        dataframe['min'] = dataframe['low'].rolling(14).min()

        return dataframe

    def calculate_risk(self, p1, p2):
        return abs(1 - (p1 / p2))


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['short_distance'] = dataframe['close'] + (dataframe['atr'] * 4)
        dataframe['long_distance'] = dataframe['close'] - (dataframe['atr'] * 4)
        dataframe['short_risk'] = self.calculate_risk(dataframe.close, dataframe.short_distance)
        dataframe['long_risk'] = self.calculate_risk(dataframe.close, dataframe.long_distance)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:


        dataframe.loc[
            (
                (dataframe[f'rsi_{self.long_timeframe}'] < self.rsi_15m_enter_long.value) &
                (dataframe[f'rsi'] > self.rsi_1m_enter_short.value)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe[f'rsi_{self.long_timeframe}'] > self.rsi_15m_enter_short.value) &
                (dataframe[f'rsi'] < self.rsi_1m_enter_short.value)
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe[f'rsi_{self.long_timeframe}'] > self.rsi_15m_exit_long.value)
            ),
            'exit_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe[f'rsi_{self.long_timeframe}'] < self.rsi_15m_exit_short.value)
            ),
            'exit_short'
        ] = 1

        return dataframe


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle.short_risk if side == "short" else candle.long_risk
        self.dp.send_msg(f"Risk: {risk:.2f}")

        return True


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if trade.nr_of_successful_entries == 1:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            candle = dataframe.iloc[-1].squeeze()
            risk = candle.short_risk if trade.is_short else candle.long_risk
            trade.set_custom_data(key='risk', value=risk)

        return None


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk')

        stop = - risk

        return stoploss_from_open(
            stop,
            current_profit,
            is_short=trade.is_short,
            leverage=trade.leverage
        )
