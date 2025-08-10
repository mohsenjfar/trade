import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
from scipy.signal import argrelextrema
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    informative
)
from datetime import datetime
from typing import Optional

class DubleSideStrategyV1(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    multiplexer = 4

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        open_trades = Trade.get_trades_proxy(is_open=True)
        if open_trades:
            last_trade = open_trades[0]
            conditions = (
                len(open_trades) == 1,
                not last_trade.is_short,
                last_trade.pair != metadata['pair']
            )
            if all(conditions):
                dataframe["enter_short"] = 1
                return dataframe

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        open_trades = Trade.get_trades_proxy(is_open=True)
        if open_trades:
            last_trade = open_trades[0]
            if last_trade.is_short != (side=='short'):
                return True
        return False

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        allowed_stake = (Trade.total_open_trades_stakes() + max_stake) / 2
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        risk = (dataframe['atr'].iat[-1] * self.multiplexer) / dataframe['close'].iat[-1]
        return max(min(allowed_stake * self.trade_max_loss_allowed / risk, allowed_stake), min_stake)

    
    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk', default=None)
        if risk is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            risk = (dataframe['atr'].iat[-1] * self.multiplexer) / dataframe['close'].iat[-1]
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")
            trade.set_custom_data(key='risk', value=risk)
        
        return stoploss_from_open(
            -risk,
            current_profit,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk', default=None)
        if current_profit > risk * 2:
            return "Target Hit"
