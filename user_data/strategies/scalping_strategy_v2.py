from pandas import DataFrame
from freqtrade.strategy import (
    IStrategy,
    informative,
    stoploss_from_open
)
import talib.abstract as ta
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional

class ScalpingStrategyV2(IStrategy):

    startup_candle_count: int = 30
    can_short: bool = True
    stoploss = -0.01
    timeframe = '1m'
    use_exit_signal = True
    use_custom_stoploss = True
    position_adjustment_enable = True


    @informative('15m')
    def populate_indicators_inf1(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe['max'] = dataframe['high'].rolling(14).max()
        dataframe['min'] = dataframe['low'].rolling(14).min()

        return dataframe

    def calculate_risk(self, p1, p2):
        return abs(1 - (p1 / p2))
    

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe['short_risk'] = self.calculate_risk(dataframe.close, dataframe.max_15m)
        dataframe['long_risk'] = self.calculate_risk(dataframe.close, dataframe.min_15m)

        if (dataframe.max_15m > 70) or (dataframe.min_15m < 30):
            self.dp.send_msg(f"{metadata['pair']} just got hot!")

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:


        dataframe.loc[
            (
                (dataframe[f'rsi_15m'] < 30) &
                (dataframe[f'rsi'] > 70)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe[f'rsi_15m'] > 70) &
                (dataframe[f'rsi'] < 30)
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe[f'rsi_15m'] > 70)
            ),
            'exit_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe[f'rsi_15m'] < 30)
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


    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        risk = trade.get_custom_data(key='risk')
        if (current_profit > risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        return stoploss_from_open(
            - trade.get_custom_data(key='risk'),
            current_profit, 
            is_short=trade.is_short, 
            leverage=trade.leverage
        )
