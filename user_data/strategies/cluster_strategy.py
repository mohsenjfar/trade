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

class ClusterStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.1

    timeframe = '1m'

    total_risk = 0.01

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

    custom_info = None

    def cluster_borders(self):
        dataframe = self.dp.get_pair_dataframe(pair="WIF/USDT:USDT", timeframe="1h")
        dataframe = dataframe[dataframe.date>='2024-04-02']
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=9, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        borders = dataframe.groupby(['cluster']).min().close.sort_values().values
        return np.append(borders, dataframe.close.max())

    def informative_pairs(self):
        return [
            ("WIF/USDT:USDT", "1h", "futures"),
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        borders = self.cluster_borders()

        if str(borders) != self.custom_info:
            self.dp.send_msg(f"{borders}")
            self.custom_info = str(borders)

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

        # dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        borders = self.cluster_borders()
        
        if side == 'long':
            # borders = np.append(borders, dataframe.low.iat[-2])
            # borders = np.sort(borders)
            risk = 1 - borders[borders < current_rate][-2] / current_rate
        else:
            # borders = np.append(borders, dataframe.high.iat[-2])
            # borders = np.sort(borders)
            risk = borders[borders > current_rate][1] / current_rate - 1
        
        stake = self.position_size(max_stake, risk)

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        borders = self.cluster_borders()
        stop = trade.get_custom_data(key='stop')

        if stop:
            if trade.is_short:
                borders = np.append(borders, stop)
                borders = np.sort(borders)
                return stoploss_from_absolute(
                    borders[borders > current_rate][1],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            borders = np.append(borders, stop)
            borders = np.sort(borders)
            return stoploss_from_absolute(
                    borders[borders < current_rate][-2],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
        
        return -1
    
    def order_filled(self, pair: str, trade: Trade, order: 'Order', current_time: datetime, **kwargs) -> None:

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.nr_of_successful_entries == 1:
            if trade.is_short:
                trade.set_custom_data(key='stop', value=prev_candle['high'])
            else:
                trade.set_custom_data(key='stop', value=prev_candle['low'])
            trade.set_custom_data(key='OB', value=self.dp.orderbook(trade.pair, maximum=200))

        return None

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:

        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)