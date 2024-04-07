import numpy as np
from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from freqtrade.data.history import load_pair_history
from freqtrade.enums import CandleType
from datetime import datetime
from typing import Optional

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute
)

class ClusterStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.1

    timeframe = '1m'

    total_risk = 0.01

    process_only_new_candles = True

    use_exit_signal = False

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    position_adjustment_enable = False

    startup_candle_count: int = 300

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
                "trade_limit": 2,
                "stop_duration_candles": 4,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False
            }
        ]

    def cluster(self, dataframe):
        X = dataframe['close'].values.reshape(-1,1)
        kmeans = KMeans(n_clusters=5, random_state=42).fit(X)
        return kmeans.predict(X)

    def pair_levels(self, pair):
        dataframe = load_pair_history(
            datadir = self.config["datadir"],
            timeframe = self.timeframe,
            pair = pair,
            data_format = "feather",
            candle_type=CandleType.FUTURES,
        )
        dataframe = dataframe[dataframe.date>='2024-04-05 02:00']
        dataframe['cluster'] = self.cluster(dataframe)
        levels = dataframe.groupby(['cluster']).min().close.sort_values().values
        levels = np.append(levels, dataframe.close.max())
        return levels

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        levels = self.pair_levels(metadata['pair'])
        for c, level in enumerate(levels):
            dataframe.loc[(dataframe.close >= level),'cluster'] = c

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) == 0) &
                (dataframe.cluster == 1)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) == 4) &
                (dataframe.cluster == 3)
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
        prev_close = dataframe.close.iat[-2]
        levels = self.pair_levels(pair)
        
        if side == 'long':
            risk = 1 - levels[levels < prev_close][-2] / prev_close
        else:
            risk = levels[levels > prev_close][1] / prev_close - 1
        
        stake = self.position_size(max_stake, risk)

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        prev_close = dataframe.close.iat[-2]
        levels = self.pair_levels(pair)

        if current_rate > levels[-1]:
            self.dp.send_msg('Price crossed above cluster')
        
        if current_rate < levels[0]:
            self.dp.send_msg('Price crossed below cluster')
        
        if trade.is_short:
            return stoploss_from_absolute(
                levels[levels > prev_close][1],
                prev_close,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        
        return stoploss_from_absolute(
                levels[levels < prev_close][-2],
                prev_close,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

    # def bot_loop_start(self, current_time: datetime, **kwargs) -> None:

    #     # if self.config['runmode'].value in ('live'):
    #     #     if self.wallets:
    #     #         self.dp.send_msg(self.wallets.get_total('USDT'))
        
    #     levels = self.pair_levels(self.config['exchange']["pair_whitelist"][0])
    #     self.dp.send_msg(str(levels))