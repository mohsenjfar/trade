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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe_ = dataframe.copy()
        for c in range(1,4):
            X = dataframe_['close'].values.reshape(-1,1)
            kmeans = KMeans(n_clusters=3, random_state=42).fit(X)
            dataframe_[f'label_{c}'] = kmeans.predict(X)
            dataframe[f'label_{c}'] = dataframe_[f'label_{c}'].astype(str)
            labels_sorted = dataframe[[f'label_{c}','close']].groupby(f'label_{c}').min()
            labels_sorted = labels_sorted.sort_values(by=['close']).reset_index().to_dict('index')
            labels_sorted = {value[f'label_{c}']:f'cluster_{key}' for key, value in labels_sorted.items()}
            dataframe = dataframe.replace({f'label_{c}':labels_sorted})
            X = dataframe_.index.values.reshape(-1,1)
            y = dataframe_.close.values
            model = LinearRegression()
            model.fit(X, y)
            dataframe[f'label_{c}_coef'] = model.coef_[0]
            dataframe_ = dataframe_[dataframe_[f'label_{c}']==dataframe_[f'label_{c}'].iat[-1]]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe.label_3.shift(1) == 'cluster_0') &
                (dataframe.label_3 == 'cluster_1')
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
        c_min = dataframe.groupby(['label_3']).min().at['cluster_0','close']
        risk = 1 - c_min / current_rate
        stake = self.position_size(max_stake, risk)

        self.custom_info[pair] = {'init_c_min':c_min, 'init_risk':risk}

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        



        return stoploss_from_absolute(
            c_min,
            trade.open_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )