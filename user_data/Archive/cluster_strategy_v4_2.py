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
import talib.abstract as ta

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
    - Use 1d timeframe as cluster timeframe using 3m candles
    - Use 3m timeframe as main timeframe
    - Split cluster timeframe into 6 clusters
    - Enter long when price crosses above max price (the highest cluster border)
    - Enter short when price crosses below min price (the lowest cluster border)
    - Trail from second custer border 
    '''

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '3m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 240

    custom_info = {
        'max_day_not_notified': True,
        'max_week_not_notified': True,
        'borders': None,
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

    def cluster_borders(self, pair, lookback_period=23, n_clusters=6):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)
        end = pd.Timestamp('now').floor('H')
        start = end - pd.Timedelta(hours=lookback_period)
        condition_1 = dataframe.date >= start.ctime()
        condition_2 = dataframe.date < end.ctime()
        dataframe_ = dataframe[condition_1 & condition_2].reset_index()
        X = dataframe_.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(X)
        dataframe_['cluster'] = kmeans.predict(X)
        return dataframe_.groupby(['cluster']).min().close.sort_values().values


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        self.custom_info['borders'] = self.cluster_borders(metadata['pair'])

        for c, border in enumerate(self.custom_info['borders']):
            dataframe.loc[(dataframe.close >= border),'cluster'] = c

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (
                    ((dataframe.cluster.shift(1) == 0) &
                    (dataframe.cluster == 1))
                )
            ),
            ['enter_long', 'enter_tag']] = (1, 'lc')

        dataframe.loc[
            (
                (
                    ((dataframe.cluster.shift(1) == 4) &
                    (dataframe.cluster == 5))
                )
            ),
            ['enter_long', 'enter_tag']] = (1, 'hc')

        dataframe.loc[
            (
                (
                    ((dataframe.cluster.shift(1) == 5) &
                    (dataframe.cluster == 4))
                )
            ),
            ['enter_short', 'enter_tag']] = (1, 'hc')

        dataframe.loc[
            (
                (
                    ((dataframe.cluster.shift(1) == 1) &
                    (dataframe.cluster == 0))
                )
            ),
            ['enter_short', 'enter_tag']] = (1, 'lc')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def position_size(self, max_stake, risk, min_stake):
        return max(min(max_stake * abs(self.stoploss) / risk, max_stake), min_stake)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        ob = self.dp.orderbook(pair, 1)
        best_bid = ob['bids'][0][0]
        best_ask = ob['asks'][0][0]
        if side == "short":
            self.custom_info['risk'] = (last_candle.close + last_candle.atr - best_ask) / best_ask
        else:
            self.custom_info['risk'] = (best_bid - last_candle.close - last_candle.atr) / best_bid
        
        stake = self.position_size(max_stake, self.custom_info['risk'], min_stake)

        return stake
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
    

        this_week_profit = client.weekly(1).get('data')[0].get('rel_profit')

        starting_balance = client.daily(1).get('data')[0].get('starting_balance')
        dataframe = pd.DataFrame(client.trades().get('trades'))
        dataframe['rel_stake'] = dataframe['stake_amount'] / starting_balance
        dataframe['rel_profit'] = dataframe['close_profit_pct'] * dataframe['rel_stake'] / 100
        today_rel_profit = dataframe[
            (dataframe.close_date > date.today().strftime('%Y-%m-%d')) &
            (dataframe.close_profit_pct < 0)
        ].rel_profit.sum()

        if today_rel_profit <= self.stoploss * 4: # ~2%
            if self.custom_info.get('max_day_not_notified'):
                self.dp.send_msg(f"Max day's loss ({today_rel_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_day_not_notified'] = False
            return False
        
        if this_week_profit <= self.stoploss * 12: # ~6%
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

        if trade.is_short:
            if trade.enter_tag == 'lc':
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                candle = dataframe.iloc[-1].squeeze()
                trade.set_custom_data(key='stop', value=current_rate + candle['atr'])
            else:
                borders = self.custom_info['borders']
                stop = trade.get_custom_data(key='stop')
                reward = trade.get_custom_data(key='reward')
                borders = np.sort(np.append(borders, (stop, trade.open_rate, reward)))
                borders = np.flip(borders)
                borders = borders[borders > current_rate]
                if borders.size > 1:
                    if borders[-2] < stop:
                        trade.set_custom_data(key='stop', value=borders[-2])
        else:
            if trade.enter_tag == 'hc':
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                candle = dataframe.iloc[-1].squeeze()
                trade.set_custom_data(key='stop', value=current_rate - candle['atr'])
            else:
                borders = self.custom_info['borders']
                stop = trade.get_custom_data(key='stop')
                reward = trade.get_custom_data(key='reward')
                borders = np.sort(np.append(borders, (stop, trade.open_rate, reward)))
                borders = borders[borders < current_rate]
                if borders.size > 1:
                    if borders[-2] > stop:
                        trade.set_custom_data(key='stop', value=borders[-2])

        if str(borders) != str(self.custom_info['borders']):
            self.dp.send_msg(str(borders))
            self.custom_info['borders'] = str(borders)

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
                stop = trade.open_rate * (1 + self.custom_info['risk'])
                reward = trade.open_rate * (1 - 2 * self.custom_info['risk'])
            else:
                stop = trade.open_rate * (1 - self.custom_info['risk'])
                reward = trade.open_rate * (1 + 2 * self.custom_info['risk'])
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='reward', value=reward)
            self.dp.send_msg(
                f"Stop: {stop:.4f}\nReward: {reward:.4f}\nOpen rate: {trade.open_rate:4f}"
            )
            
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