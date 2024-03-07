import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from typing import Optional
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
import talib.abstract as ta

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    timeframe_to_prev_date
)

class HoldStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = False

    stoploss = -0.1

    timeframe = '15m'

    total_risk = 0.01

    process_only_new_candles = True

    use_exit_signal = False

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    startup_candle_count: int = 200

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': True
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 4,
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": False
            }
        ]


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['atr'] = ta.ATR(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['open'] < dataframe['close'])
            ),
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def position_size(self, total_asset, risk):

        size = total_asset * self.total_risk / risk if risk > self.total_risk else total_asset

        return size

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        previous_candle = dataframe.iloc[-2].squeeze()
        risk = previous_candle['atr'] / current_rate * 2
        stake = self.position_size(max_stake, risk)

        return stake

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        if current_candle['date'] + timedelta(seconds=910) > current_time:
            return True

        return False

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        trade_dataframe = dataframe.loc[dataframe['date'] <= trade_date]
        prev_trade_candle = trade_dataframe.iloc[-2].squeeze()

        return stoploss_from_absolute(
            trade.open_rate - prev_trade_candle['atr'] * 2,
            trade.open_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )