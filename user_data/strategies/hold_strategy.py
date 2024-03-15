import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from typing import Optional, Union, Tuple
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

    position_adjustment_enable = False

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
                "lookback_period_candles": 96,
                "trade_limit": 2,
                "stop_duration_candles": 96,
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
                (dataframe['close'] > dataframe['close'].shift(1)) &
                (dataframe['close'].shift(1) < dataframe['close'].shift(2)) &
                (dataframe['close'].shift(2) < dataframe['close'].shift(3)) &
                (dataframe['close'].shift(3) < dataframe['close'].shift(4))
            ),
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['close'].shift(1)) &
                (dataframe['close'].shift(1) > dataframe['close'].shift(2)) &
                (dataframe['close'].shift(2) > dataframe['close'].shift(3)) &
                (dataframe['close'].shift(3) > dataframe['close'].shift(4))
            ),
            'exit_long'
        ] = 1

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
    
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> Union[Optional[float], Tuple[Optional[float], Optional[str]]]:

        last_order_date = timeframe_to_prev_date(self.timeframe, trade.date_last_filled_utc)
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe.iloc[-2].squeeze()

        if (current_time > last_order_date + timedelta(minutes=15)) and last_candle['enter_long'] == 1:
            risk = last_candle['atr'] / current_rate * 2
            return self.position_size(max_stake, risk)
        
        return None

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