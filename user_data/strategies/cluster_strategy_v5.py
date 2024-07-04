from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta, date
import numpy as np
from typing import Optional, Dict
from technical import qtpylib
import talib.abstract as ta
# import api

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    stoploss_from_absolute
)

class ClusterStrategyV5(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.02

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 2000

    cluster_size = IntParameter(20, 40, default=30, space="buy")

    custom_info = {
        'max_day_not_notified': True,
        'max_week_not_notified': True,
        'total_daily_risk': -0.02
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

    def cluster_borders(self, pair, n_clusters):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe='1d')
        dataframe = dataframe[dataframe.date >= '2024-03-13'].reset_index()
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [
            (pair, '1d', "futures")
            for pair in pairs
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        for val in self.cluster_size.range:
            borders = self.cluster_borders(metadata['pair'], n_clusters=val)
            for border in borders:
                dataframe.loc[(dataframe.close > border),f'cluster_{val}'] = border
        dataframe['sma_300'] = ta.SMA(dataframe, 300)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                dataframe['close'] > dataframe['sma_300'] & #Guard
                qtpylib.crossed_above(dataframe.close, dataframe[f'cluster_{self.cluster_size.value}']) #Trigger
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                dataframe['close'] < dataframe['sma_300'] & #Guard
                qtpylib.crossed_below(dataframe.close, dataframe[f'cluster_{self.cluster_size.value}']) #Trigger
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        return max(min(max_stake * abs(self.custom_info['total_daily_risk'] / abs(self.stoploss)), max_stake), min_stake)
    

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        total_stack = self.wallets.get_total_stake_amount()

        today_trades = Trade.get_trades_proxy(open_date = date.today())
        if today_trades:
            today_profit = sum(trade.close_profit_abs / total_stack  for trade in today_trades)
            if (today_profit <= self.custom_info['total_daily_risk']):
                if self.custom_info.get('max_day_not_notified'):
                    self.dp.send_msg(f"Max day's loss ({today_profit:.2f}) is reached, stop trade entry ...")
                    self.custom_info['max_day_not_notified'] = False
                return False

        week_day = date.weekday(date.today())
        this_week_trades = Trade.get_trades_proxy(open_date = date.today() - timedelta(days=week_day))
        if this_week_trades:
            this_week_profit = sum(trade.close_profit_abs / total_stack  for trade in this_week_trades)
            if this_week_profit <= self.custom_info['total_daily_risk'] * 3:
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
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        side = -1 if trade.is_short else 1
        stop = trade.get_custom_data(key='stop', default= trade.open_rate * (1 + side * self.stoploss))
        if trade.is_short:
            borders = dataframe.groupby([f'cluster_{self.cluster_size.value}']).close.max()
            borders = np.flip(np.sort(np.append(borders, trade.open_rate)))
            if borders.size > 1:
                border = borders[borders > current_rate][-2]
                if border < stop:
                    trade.set_custom_data(key='stop', value=border)
        else:
            borders = dataframe.groupby([f'cluster_{self.cluster_size.value}']).close.min()
            borders = np.sort(np.append(borders, trade.open_rate))
            if borders.size > 1:
                border = borders[borders < current_rate][-2]
                if border > stop:
                    trade.set_custom_data(key='stop', value=border)
        
        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if trade.nr_of_successful_entries == 1:
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
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