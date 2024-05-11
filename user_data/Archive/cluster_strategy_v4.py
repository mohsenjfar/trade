from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta, date
from typing import Optional
from freqtrade.persistence import Trade
import numpy as np

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute
)

class ClusterStrategyV4(IStrategy):
    
    ''' Specs:
    - Use 4h timeframe as cluster timeframe
    - Use 1m timeframe as main timeframe
    - Split cluster timeframe into 6 clusters
    - When price crosses above one cluster border open long position and put stop second border below
    - When price crosses below one cluster border open short position and put stop second border above
    - Trail trade as 2th reward is reached
    '''

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.1

    timeframe = '1m'

    max_risk = 0.02

    process_only_new_candles = False

    use_exit_signal = True

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

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

    def cluster_borders(self, pair):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe="5m")
        dataframe = dataframe[-48:]
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=6, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [
            (pair, "5m", "futures")
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

        if risk > self.max_risk:
            return (max_stake * self.max_risk) / (risk * self.config['max_open_trades'])
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
        today_loss = sum(trade.close_profit for trade in today_trades)

        week_day = date.weekday(date.today())
        this_week_trades = Trade.get_trades_proxy(open_date = date.today() - timedelta(days=week_day))
        this_week_loss = sum(trade.close_profit for trade in this_week_trades)

        if (today_loss <= -0.02):
            if self.custom_info.get('max_day_not_notified'):
                self.dp.send_msg(f"Max day's loss ({today_loss}) is reached, stop trade entry ...")
                self.custom_info['max_day_not_notified'] = False
            return False
        
        if this_week_loss <= -0.06:
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

        stop = trade.get_custom_data(key='stop')
        if stop:
            risk_ratio = abs(1 - stop / trade.open_rate)
            borders = self.cluster_borders(pair)
            
            if trade.is_short:
                border = borders[borders > current_rate][0]
                condition = border <= (trade.open_rate - risk_ratio * 2)
            else:
                border = borders[borders < current_rate][-1]
                condition = border >= (trade.open_rate + risk_ratio * 2)
            if condition:
                return stoploss_from_absolute(
                    border,
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )

            return stoploss_from_absolute(
                stop,
                trade.open_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        
        return None
        

    def order_filled(self, pair: str, trade: Trade, order: 'Order', current_time: datetime, **kwargs) -> None:

        borders = self.cluster_borders(pair)
        if trade.is_short:
            border = borders[borders > trade.open_rate]
            stop = border[0] if len(border) > 1 else trade.open_rate
        else:
            border = borders[borders < trade.open_rate]
            stop = border[-1] if len(border) > 1 else trade.open_rate

        if trade.nr_of_successful_entries == 1:
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            trade.set_custom_data(key='borders', value=list(self.cluster_borders(pair)))
            trade.set_custom_data(key='stop', value=stop)

        return None
    
    def bot_loop_start(self, **kwargs) -> None:
        
        for trade in Trade.get_open_trades():
            current_borders = self.cluster_borders(trade.pair)
            borders = trade.get_custom_data(key='borders')
            if borders and borders[-1] != list(current_borders):
                borders.append(list(current_borders))
        
        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)