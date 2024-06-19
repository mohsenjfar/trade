from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta
import numpy as np
from typing import Optional, Dict
from technical import qtpylib
import talib.abstract as ta
# import api

from freqtrade.strategy import (
    IStrategy,
    IntParameter
)

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

    stoploss = -0.02

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 2000

    cluster_timeframe = '1d'

    cluster_size = IntParameter(20, 40, default=30, space="buy")

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
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=self.cluster_timeframe)
        dataframe = dataframe[dataframe.date >= '2024-03-13'].reset_index()
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [
            (pair, self.cluster_timeframe, "futures")
            for pair in pairs
        ]

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

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]

        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-12) > dataframe["close"], 'up', 'down')

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # dataframe = self.freqai.start(dataframe, metadata, self)

        for val in self.cluster_size.range:
            borders = self.cluster_borders(metadata['pair'], n_clusters=val)
            for c, border in enumerate(borders):
                dataframe.loc[(dataframe.close >= border),f'cluster_{val}'] = c

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe[f'cluster_{self.cluster_size.value}'].shift(1) < dataframe[f'cluster_{self.cluster_size.value}'])
                # (dataframe['do_predict'] == 1) &
                # (dataframe['&s-up_or_down'] == 'up')
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe[f'cluster_{self.cluster_size.value}'].shift(1) > dataframe[f'cluster_{self.cluster_size.value}'])
                # (dataframe['do_predict'] == 1) &
                # (dataframe['&s-up_or_down'] == 'down')
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
    #                 current_profit: float, **kwargs):
        
    #     if (current_time > trade.open_date + timedelta(hours=3)) and current_profit < 0:
    #         return "Trade expired!"

    #     return None


    # def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
    #                     current_rate: float, current_profit: float, after_fill: bool, 
    #                     **kwargs) -> Optional[float]:

    #     if self.dp.runmode.value in ('live'):
    #         api.update_task(trade, current_time)


    # def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

    #     if trade.nr_of_successful_entries == 1:
    #         trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
    #         if self.dp.runmode.value in ('live'):
    #             task = api.create_task(trade, __class__.__name__)
    #             trade.set_custom_data(key='task_id', value=task.get('id'))
    #             self.dp.send_msg(f"Task {task.get('summary')} created")

    #     if trade.nr_of_successful_entries == 2 and self.dp.runmode.value in ('live'):
    #         task = api.complete(trade)
    #         self.dp.send_msg(f"Task {task.get('summary')} completed")

    #     return None
    
    # def bot_start(self, **kwargs) -> None:
    #     if self.dp.runmode.value in ('live'):
    #         res = api.create_parent(__class__.__name__)
    #         self.dp.send_msg(f"Parent {res.get('title')} created")