from pandas import DataFrame
from freqtrade.strategy import (
    IStrategy,
    informative,
    stoploss_from_open,
    IntParameter,
    stoploss_from_absolute
)
import talib.abstract as ta
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ScalpingStrategyV2(IStrategy):

    startup_candle_count: int = 30
    can_short: bool = True
    stoploss = -0.01
    timeframe = '1m'
    long_timeframe = "15m"
    use_exit_signal = False
    use_custom_stoploss = True

    rsi_15m_enter_long = IntParameter(10, 40, default=30, space='buy')
    rsi_15m_enter_short = IntParameter(60, 90, default=70, space='buy')
    rsi_1m_enter_short = IntParameter(10, 40, default=30, space='buy')
    rsi_1m_enter_long = IntParameter(60, 90, default=70, space='buy')


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
        dataframe['short_distance'] = dataframe['close'] + dataframe['atr']
        dataframe['long_distance'] = dataframe['close'] - dataframe['atr']
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

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle.short_risk if side == "short" else candle.long_risk

        return max(max_stake - max_stake * risk / (abs(self.stoploss) / 2), min_stake)


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

        if current_profit > 0.2:
            return -0.05

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        
        absolute_value = candle.short_distance if trade.is_short else candle.long_distance
        if (candle[f'rsi_{self.long_timeframe}'] < 30) or (candle[f'rsi_{self.long_timeframe}'] > 70):
            return stoploss_from_absolute(
                absolute_value,
                current_rate, 
                is_short=trade.is_short, 
                leverage=trade.leverage
            )

        risk = trade.get_custom_data(key='risk')

        return stoploss_from_open(
            0 if current_profit > 2 * risk else - risk,
            current_profit, 
            is_short=trade.is_short, 
            leverage=trade.leverage
        )
