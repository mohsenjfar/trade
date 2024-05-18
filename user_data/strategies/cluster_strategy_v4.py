from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta, date
from typing import Optional
from freqtrade.persistence import Trade
import api
from freqtrade_client import FtRestClient
import pandas as pd
import numpy as np

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute
)

server_url = 'http://127.0.0.1:8080'
username = ''
password = "a88923695f80935a17b99e51df8275bc3440b92defa52106c0cea26ca1bf1ce1"
client = FtRestClient(server_url, username, password)

class ClusterStrategyV4(IStrategy):
    
    ''' Specs:
    - Use 4h timeframe as cluster timeframe using 3m candles
    - Use 1m timeframe as main timeframe
    - Split cluster timeframe into 6 clusters
    - Enter long when price crosses above max price (the highest cluster border)
    - Enter short when price crosses below min price (the lowest cluster border)
    - Trail from second custer border 
    '''

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '1m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 240

    custom_info = {
        'max_day_not_notified': True,
        'max_week_not_notified': True,
        'total_risk': -0.02,
        'borders': [],
    }

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

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 60,
                "trade_limit": 2,
                "stop_duration_candles": 240,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False
            }
        ]

    def cluster_borders(self, pair, timeframe='3m', lookback_period=23, n_clusters=6):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=timeframe)
        end = pd.Timestamp('now').floor('H')
        start = end - pd.Timedelta(hours=lookback_period)
        condition_1 = dataframe.date >= start.ctime()
        condition_2 = dataframe.date < end.ctime()
        dataframe_ = dataframe[condition_1 & condition_2].reset_index()
        X = dataframe_.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(X)
        dataframe_['cluster'] = kmeans.predict(X)
        return dataframe_.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [
            (pair, "3m", "futures")
            for pair in pairs
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        borders = self.cluster_borders(metadata['pair'])

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

    def position_size(self, max_stake, risk, min_stake):
        return max(max_stake - max_stake * risk * 100 / abs(self.custom_info["total_risk"] * 100), min_stake)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        stake = self.position_size(max_stake, abs(self.stoploss), min_stake)

        return stake
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        
        trades = Trade.get_trades_proxy(pair=pair, is_open=False)
        if trades and trades[-1].is_short == (side == 'short'):
            return False
    
        today_profit = client.daily(1).get('data')[0].get('rel_profit')
        this_week_profit = client.weekly(1).get('data')[0].get('rel_profit')

        if (today_profit <= self.custom_info["total_risk"]):
            if self.custom_info.get('max_day_not_notified'):
                self.dp.send_msg(f"Max day's loss ({today_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_day_not_notified'] = False
            return False
        
        if this_week_profit <= (self.custom_info["total_risk"] * 3):
            if self.custom_info.get('max_week_not_notified'):
                self.dp.send_msg(f"Max week's loss ({this_week_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_week_not_notified'] = False
            return False
        
        self.custom_info['max_week_not_notified'] = True
        self.custom_info['max_day_not_notified'] = True

        return True

    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if self.dp.runmode.value in ('live'):
            api.update_task(trade, current_time)

        borders = self.cluster_borders(pair)
        stop = trade.get_custom_data(key='stop')
        reward = trade.get_custom_data(key='reward')
        if trade.is_short:
            borders = np.flip(np.sort(np.append(borders, (stop, trade.open_rate, reward))))
            border = borders[(borders > current_rate) & (borders <= stop)][-2]
            if border < stop:
                trade.set_custom_data(key='stop', value=border)
        else:
            borders = np.sort(np.append(borders, (stop, trade.open_rate, reward)))
            border = borders[(borders < current_rate) & (borders >= stop)][-2]
            if border > stop:
                trade.set_custom_data(key='stop', value=border)
        
        if str(borders) != self.custom_info['borders']:
            self.dp.send_msg(str(borders))
            self.custom_info['borders'] = borders
        
        return stoploss_from_absolute(
            trade.get_custom_data(key='stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if trade.nr_of_successful_entries == 1:
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
            if trade.is_short:
                stop = trade.open_rate / (1 - abs(self.stoploss))
                reward = trade.open_rate / (1 + 2 * abs(self.stoploss))
            else:
                stop = trade.open_rate * (1 - abs(self.stoploss))
                reward = trade.open_rate * (1 + 2 * abs(self.stoploss))
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='reward', value=reward)
            
            if self.dp.runmode.value in ('live'):
                task = api.create_task(trade, __class__.__name__)
                trade.set_custom_data(key='task_id', value=task.get('id'))
                self.dp.send_msg(f"Task {task.get('summary')} created")

        if trade.nr_of_successful_entries == 2 and self.dp.runmode.value in ('live'):
            task = api.complete(trade)
            self.dp.send_msg(f"Task {task.get('summary')} completed")

        return None
    
    def bot_start(self, **kwargs) -> None:
        if self.dp.runmode.value in ('live'):
            res = api.create_parent(__class__.__name__)
            self.dp.send_msg(f"Parent {res.get('title')} created")    