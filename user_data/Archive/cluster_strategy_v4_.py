from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta, date
from typing import Optional
from freqtrade.persistence import Trade
import numpy as np
import requests

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute
)

class ClusterStrategyV4(IStrategy):
    
    ''' Specs:
    - Use 4h timeframe as cluster timeframe
    - Use 3m timeframe as main timeframe
    - Split cluster timeframe into 6 clusters
    - When price crosses above one cluster border open long position and put stop second border below
    - When price crosses below one cluster border open short position and put stop second border above
    - Trail trade as 2th reward is reached
    '''

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.02

    timeframe = '3m'
    cluster_timeframe = '15m'

    process_only_new_candles = False

    use_exit_signal = True

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    startup_candle_count: int = 240

    api_sync = False

    base_url = "http://localhost:8000"

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

    def cluster_borders(self, pair):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=self.cluster_timeframe)
        dataframe = dataframe[-16:]
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=4, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values.tolist()

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [
            (pair, self.cluster_timeframe, "futures")
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
                (dataframe.cluster.shift(1) > dataframe.cluster)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) < dataframe.cluster)
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def position_size(self, max_stake, risk):

        if risk > abs(self.stoploss):
            return (max_stake * abs(self.stoploss)) / (risk * self.config['max_open_trades'])
        else:
            return max_stake / self.config['max_open_trades']

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        borders = self.cluster_borders(pair)
        if side == 'long':
            risk = 1 - borders[-1] / current_rate
        else:
            risk = borders[0] / current_rate - 1
        stake = self.position_size(max_stake, risk)
        return stake

    custom_info = {
        'max_day_not_notified': True,
        'max_week_not_notified': True
    }
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        today_trades = Trade.get_trades_proxy(open_date = date.today())
        today_loss = sum(trade.close_profit for trade in today_trades) / self.config['max_open_trades']

        week_day = date.weekday(date.today())
        this_week_trades = Trade.get_trades_proxy(open_date = date.today() - timedelta(days=week_day))
        this_week_loss = sum(trade.close_profit for trade in this_week_trades) / self.config['max_open_trades']

        if (today_loss <= self.stoploss):
            if self.custom_info.get('max_day_not_notified'):
                self.dp.send_msg(f"Max day's loss ({today_loss}) is reached, stop trade entry ...")
                self.custom_info['max_day_not_notified'] = False
            return False
        
        if this_week_loss <= (self.stoploss * 3):
            if self.custom_info.get('max_week_not_notified'):
                self.dp.send_msg(f"Max week's loss ({this_week_loss}) is reached, stop trade entry ...")
                self.custom_info['max_week_not_notified'] = False
            return False
        
        self.custom_info['max_week_not_notified'] = True
        self.custom_info['max_day_not_notified'] = True

        return True
    
        
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if self.api_sync:
            api_url = f'{self.url}{__class__.__name__}/{trade.get_custom_data(key="task_id")}'
            params = {
                "due": current_time,
            }
            requests.put(api_url, params=params)
            api_url = f'{self.url}{__class__.__name__}/{trade.get_custom_data(key="task_id")}/quantity'
            params = {
                "quantity": trade.total_profit
            }
            requests.put(api_url, params=params)

        open_borders = np.array(trade.get_custom_data(key='borders'))
        if trade.is_short:
            higher_open_borders = open_borders[open_borders > trade.open_rate]
            risk_ratio = higher_open_borders[0] / trade.open_rate - 1
            higher_current_borders = open_borders[open_borders > current_rate]
            if higher_current_borders[0] <= (trade.open_rate - risk_ratio * 2):
                return stoploss_from_absolute(
                    higher_current_borders[0],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            return stoploss_from_absolute(
                higher_open_borders[0],
                trade.open_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        lower_open_borders = open_borders[open_borders < trade.open_rate]
        risk_ratio = 1 - lower_open_borders[-1] / trade.open_rate
        lower_current_borders = open_borders[open_borders < current_rate]
        if lower_current_borders[-1] >= (trade.open_rate + risk_ratio * 2):
            return stoploss_from_absolute(
                lower_current_borders[-1],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        return stoploss_from_absolute(
            lower_open_borders[-1],
            trade.open_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )
        

    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        borders = self.cluster_borders(pair)
        if trade.nr_of_successful_entries == 1:
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            trade.set_custom_data(key='borders', value=borders)
            if self.api_sync:
                url = "http://localhost:8000/parent/"
                data = {
                    'title':'ClusterStrategyV4'
                }
                results = requests.post(url=url + 'filter/',data=data).json()
                parent = results[0]
                parent
                
                api_url = f'{self.url}{__class__.__name__}'
                parent = requests.get(api_url)
                params = {
                    "parent": parent.get('id'),
                    "summary": f"Trade no: {trade.id}",
                    "start": trade.open_date,
                    "description": __class__.__name__
                }
                res = requests.post(api_url, params=params)
                trade.set_custom_data(key='task_id', value=res.get('id'))
        
        if (trade.nr_of_successful_entries == 2) and self.api_sync:
            api_url = f'{self.base_url}{__class__.__name__}/{trade.get_custom_data(key="task_id")}/'
            data = {
                "due": trade.close_date,
                "tag": "completed"
            }
            requests.put(api_url, data=data)

        return None

    def bot_start(self, **kwargs) -> None:

        if self.api_sync:
            url = f"{self.base_url}/parent"
            data = {
                'title': __class__.__name__
            }
            res = requests.post(url=f"{url}/filter/", data=data)
            if res.status_code == 400:
                res = requests.post(url=url, data=data)
                self.dp.send_msg(f"Parent {data.get('title')} created")