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
from technical import qtpylib
from typing import Dict

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

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe["bb_lowerband-period"] = bollinger["lower"]
        dataframe["bb_middleband-period"] = bollinger["mid"]
        dataframe["bb_upperband-period"] = bollinger["upper"]

        dataframe["%-bb_width-period"] = (
            dataframe["bb_upperband-period"]
            - dataframe["bb_lowerband-period"]
        ) / dataframe["bb_middleband-period"]
        dataframe["%-close-bb_lower-period"] = (
            dataframe["close"] / dataframe["bb_lowerband-period"]
        )

        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(
            self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        return dataframe

    def feature_engineering_standard(
            self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-50) >
                                              dataframe["close"], 'up', 'down')

        return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.freqai.start(dataframe, metadata, self)

        self.custom_info['borders'] = self.cluster_borders(metadata['pair'])

        for c, border in enumerate(self.custom_info['borders']):
            dataframe.loc[(dataframe.close >= border),'cluster'] = c

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (
                    ((dataframe.cluster.shift(1) == 0) &
                    (dataframe.cluster == 1)) & 
                    (dataframe['do_predict'] == 1) &
                    (dataframe['&s-up_or_down'] == 'down')
                )
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (
                    ((dataframe.cluster.shift(1) == 5) &
                    (dataframe.cluster == 4)) &
                    (dataframe['do_predict'] == 1) &
                    (dataframe['&s-up_or_down'] == 'up')
                )
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def position_size(self, max_stake, risk, min_stake):
        return max(min(max_stake * abs(self.stoploss) / risk, max_stake), min_stake)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        borders = self.custom_info['borders']
        ob = self.dp.orderbook(pair, 1)
        best_bid = ob['bids'][0][0]
        best_ask = ob['asks'][0][0]
        if side == "short":
            borders = np.flip(borders)
            border = borders[borders > best_ask][-2]
            risk = border / best_ask - 1
        else:
            border = borders[borders < best_ask][-2]
            risk = best_bid / border - 1
        stake = self.position_size(max_stake, risk, min_stake)

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

        borders = self.custom_info['borders']
        stop = trade.get_custom_data(key='stop')
        if trade.is_short:
            borders = np.flip(borders)
            borders = borders[borders > current_rate]
            if borders[-2] < stop:
                trade.set_custom_data(key='stop', value=borders[-2])
        else:
            borders = borders[borders < current_rate]
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
                borders = np.flip(borders)
                stop = borders[borders > trade.open_rate][-2]
            else:
                stop = borders[borders < trade.open_rate][-2]
            trade.set_custom_data(key='stop', value=stop)
            
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