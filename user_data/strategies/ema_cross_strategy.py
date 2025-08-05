import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
from scipy.signal import argrelextrema
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open
)
from datetime import datetime
from typing import Optional

class EMACrossStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '15m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = False

    # @property
    # def protections(self):
    #     return [
    #         {
    #             "method": "StoplossGuard",
    #             "lookback_period_candles": 1,
    #             "trade_limit": 1,
    #             "stop_duration_candles": 48,
    #             "required_profit": 0.0,
    #             "only_per_pair": True,
    #             "only_per_side": True
    #         }
    #     ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["ema_short"] = ta.EMA(dataframe, timeperiod=7)
        dataframe["ema_medium"] = ta.EMA(dataframe, timeperiod=24)
        dataframe["ema_long"] = ta.EMA(dataframe, timeperiod=100)
        
        min_peaks = argrelextrema(dataframe["ema_medium"].values, np.less_equal, order=1)
        dataframe.loc[(dataframe.index.isin(min_peaks[0])),'sl'] = dataframe.ema_medium

        max_peaks = argrelextrema(dataframe["ema_medium"].values, np.greater_equal, order=1)
        dataframe.loc[(dataframe.index.isin(max_peaks[0])),'ss'] = dataframe.ema_medium

        dataframe[['ss','sl']] = dataframe[['ss','sl']].ffill()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['ema_short'] > dataframe['ema_long']) &
                (dataframe['sl'] < dataframe['ema_long']) &
                (dataframe['sl'].index.max() > dataframe['ss'].index.max())
            ), ["enter_long"]] = 1

        dataframe.loc[
            (
                (dataframe['ema_short'] < dataframe['ema_long']) &
                (dataframe['ss'] > dataframe['ema_long']) &
                (dataframe['ss'].index.max() > dataframe['sl'].index.max())
            ), ["enter_short"]] = 1


        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['ema_medium'] < dataframe['ema_long'])
            ), ["exit_long"]] = 1

        dataframe.loc[
            (
                (dataframe['ema_medium'] > dataframe['ema_long'])
            ), ["exit_short"]] = 1

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        stop = dataframe['ss'].iat[-1] if side == 'short' else dataframe['sl'].iat[-1]
        risk = abs(stop / dataframe['close'].iat[-1] - 1)
        return max(min(max_stake * self.trade_max_loss_allowed / risk, max_stake), min_stake)


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
            stop = dataframe['ss'].iat[-1] if trade.is_short else dataframe['sl'].iat[-1]
            risk = abs(stop / dataframe['close'].iat[-1] - 1)
            self.dp.send_msg(f"Trade risk: {risk * 100:.2f} %")
            trade.set_custom_data(key='risk', value=risk)
        
        return stoploss_from_open(
            -risk,
            current_profit,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    # def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
    #                 current_rate: float, current_profit: float, **kwargs) -> str:

    #     risk = trade.get_custom_data(key='risk', default=None)
    #     conditions = (
    #         (current_profit > risk * 4) and (risk <= 0.005),
    #         (current_profit > risk * 2) and (risk > 0.005)
    #     )
    #     if any(conditions):
    #         return "Target Hit!"
