import numpy as np
from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from freqtrade.data.history import load_pair_history
from freqtrade.enums import CandleType
from datetime import datetime
from typing import Optional
from freqtrade.persistence import Trade
import numpy as np

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute
)

class ClusterStrategyV2(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    total_risk = 0.005

    process_only_new_candles = False

    use_exit_signal = False

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    position_adjustment_enable = False

    startup_candle_count: int = 240

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
                "lookback_period_candles": 30,
                "trade_limit": 2,
                "stop_duration_candles": 15,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False
            }
        ]

    def cluster_borders(self):
        dataframe = self.dp.get_pair_dataframe(pair="WIF/USDT:USDT", timeframe="15m")
        dataframe = dataframe[-16:]
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=6, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        return [
            ("WIF/USDT:USDT", "15m", "futures"),
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        borders = self.cluster_borders()

        for c, border in enumerate(borders):
            dataframe.loc[(dataframe.close >= border),'cluster'] = c

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) < dataframe.cluster)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) > dataframe.cluster)
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

        borders = self.cluster_borders()
        
        if side == 'long':
            risk = 1 - borders[borders < current_rate][-1] / current_rate
        else:
            risk = borders[borders > current_rate][0] / current_rate - 1
        
        stake = self.position_size(max_stake, risk)

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        borders = self.cluster_borders()
        stop = trade.get_custom_data(key='stop')
        adjusted_stop = trade.get_custom_data(key='adjusted_stop')

        if (current_rate - trade.open_rate) * 3 >= stop:
            return stoploss_from_absolute(
                stop * 2,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

        if adjusted_stop:
            return None

        if current_profit > 0 and ((current_rate - trade.open_rate) / 2 >= stop):
            adjusted_stop = (current_rate - trade.open_rate) / 2
            trade.set_custom_data(key='adjusted_stop', value = adjusted_stop)
            return stoploss_from_absolute(
                adjusted_stop,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

        if trade.is_short:
            return stoploss_from_absolute(
                borders[borders > current_rate][0],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        return stoploss_from_absolute(
                borders[borders < current_rate][-1],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
    
    def order_filled(self, pair: str, trade: Trade, order: 'Order', current_time: datetime, **kwargs) -> None:

        borders = self.cluster_borders()

        if trade.nr_of_successful_entries == 1:
            if trade.is_short:
                trade.set_custom_data(key='stop', value=borders[borders > trade.open_rate][0])
            else:
                trade.set_custom_data(key='stop', value=borders[borders < trade.open_rate][-1])
            trade.set_custom_data(key='OB', value=self.dp.orderbook(trade.pair, maximum=200))

        return None

    # def bot_loop_start(self, current_time: datetime, **kwargs) -> None:

    #     pairs = self.dp.current_whitelist()
    #     for pair in pairs:
    #         if self.is_pair_locked(pair):
    #             self.unlock_pair(pair)