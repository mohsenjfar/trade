from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone
from typing import Optional
from technical import qtpylib
import pandas as pd
import math
import os
from typing import Dict
import numpy as np
import talib.abstract as ta
from scipy.signal import argrelextrema
from freqtrade.strategy import (
    IStrategy,
    informative,
    stoploss_from_open,
    timeframe_to_prev_date
)
import logging

logger = logging.getLogger(__name__)


class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 48

    process_only_new_candles = True

    kernel = 1

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }


    @informative('1w')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        min_peaks = argrelextrema(dataframe["low"].values, np.less_equal, order=self.kernel)
        max_peaks = argrelextrema(dataframe["high"].values, np.greater_equal, order=self.kernel)
        dataframe.loc[(dataframe.index.isin(min_peaks[0])),'extrema'] = dataframe.low
        dataframe.loc[(dataframe.index.isin(max_peaks[0])),'extrema'] = dataframe.high
        return dataframe.ffill()


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.to_csv(f'user_data/notebooks/{metadata["pair"][:-10]}.csv', index=False)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                dataframe['change_1w'] != dataframe['change_1w'].shift(1) &
                dataframe['change_1w'] < 0
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                dataframe['change_1w'] != dataframe['change_1w'].shift(1) &
                dataframe['change_1w'] > 0
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                dataframe['change_1w'] != dataframe['change_1w'].shift(1) &
                dataframe['change_1w'] > 0
            ),
            'exit_long'
        ] = 1

        dataframe.loc[
            (
                dataframe['change_1w'] != dataframe['change_1w'].shift(1) &
                dataframe['change_1w'] < 0
            ),
            'exit_short'
        ] = 1

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        try:
            risk = 0.005
            today = datetime.now(timezone.utc).date()
            closed_trades = Trade.get_trades_proxy(close_date=today)
            today_loss = sum(trade.close_profit_abs for trade in closed_trades if trade.close_profit_abs < 0)
            stake_in_use = Trade.total_open_trades_stakes()
            total_stake = stake_in_use + max_stake
            today_loss_ratio = today_loss / total_stake

            if today_loss_ratio < self.stoploss:
                logger.info(f"Max day loss ({today_loss_ratio * 100:.2f}%), stop entering {side} position for {pair}")
                return None
            
            return min((proposed_stake * (abs(self.stoploss)) / 2) / (risk * leverage), proposed_stake)
        
        except Exception as e:
            logger.info(e)
            return None
    

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)

        return dataframe["close_1w"].iat[-1]