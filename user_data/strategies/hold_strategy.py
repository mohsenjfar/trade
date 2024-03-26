import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from typing import Optional, Union, Tuple
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
import talib.abstract as ta
from technical import qtpylib
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression

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

    total_risk = 0.005

    process_only_new_candles = True

    use_exit_signal = False

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    position_adjustment_enable = False

    startup_candle_count: int = 5936

    custom_info = {}

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
                "stop_duration_candles": 8,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False
            }
        ]

    def cluster(self, dataframe):
        X = dataframe['close'].values.reshape(-1,1)
        kmeans = KMeans(n_clusters=3, random_state=42).fit(X)
        return kmeans.predict(X)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['label_1'] = self.cluster(dataframe)

        grouped = dataframe.groupby(['label_1']).apply(self.cluster).to_dict()
        for c, values in grouped.items():
            condition_1 = dataframe['label_1'] == c
            dataframe.loc[condition_1, 'label_2'] = values

        grouped = dataframe.groupby(['label_1','label_2']).apply(self.cluster).to_dict()
        for c, values in grouped.items():
            condition_1 = dataframe['label_1'] == c[0]
            condition_2 = dataframe['label_2'] == c[1]
            dataframe.loc[(condition_1 & condition_2), 'label_3'] = values

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe.label_3.shift(1) == 0) &
                (dataframe.label_3 == 1)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe.label_3.shift(1) == 2) &
                (dataframe.label_3 == 1)
            ),
            'enter_short'
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
        mins = dataframe.groupby([f'label_{i}' for i in [1,2,3]]).min().close.sort_values().values
        risk = 1 - mins[mins < current_rate][-1] / current_rate
        stake = self.position_size(max_stake, risk)

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        mins = dataframe.groupby([f'label_{i}' for i in [1,2,3]]).min().close.sort_values().values
        prev_close = dataframe.close.iat[-2]

        return stoploss_from_absolute(
            mins[mins < prev_close][-1],
            prev_close,
            is_short=trade.is_short,
            leverage=trade.leverage
        )