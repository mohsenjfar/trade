from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta
import numpy as np
from typing import Optional, Dict
from technical import qtpylib
import talib.abstract as ta
# import api
from functools import reduce

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter
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

    stoploss = -0.01

    timeframe = '5m'

    use_exit_signal = True

    use_custom_stoploss = True

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

    long_params = IntParameter(1, 50, default=30, space="buy", optimize=True)
    short_params = IntParameter(50, 100, default=70, space="buy", optimize=True)
    roi_profit = DecimalParameter(0.01, 0.1, default=0.05, decimals=2, space="buy", optimize=True)
    rsi_long = IntParameter(5, 100, default=14, space="buy", optimize=True)
    sma_long = IntParameter(50, 500, default=100, space="buy", optimize=True)
    rsi_short= IntParameter(5, 100, default=14, space="sell", optimize=True)
    sma_short = IntParameter(50, 500, default=100, space="sell", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        for value in self.rsi_long.range:
            dataframe[f'rsi_{value}_long'] = ta.RSI(dataframe['close'], value)

        for value in self.sma_long.range:
            dataframe[f'sma_{value}_long'] = ta.SMA(dataframe, value)

        for value in self.rsi_short.range:
            dataframe[f'rsi_{value}_short'] = ta.RSI(dataframe['close'], value)   

        for value in self.sma_short.range:
            dataframe[f'sma_{value}_short'] = ta.SMA(dataframe, value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        conditions = []

        conditions.append(qtpylib.crossed_above(dataframe[f'rsi_{self.rsi_long.value}_long'], self.long_params.value))
        conditions.append(dataframe['close'] > dataframe[f'sma_{self.sma_long.value}_long'])

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        conditions = []

        conditions.append(qtpylib.crossed_below(dataframe[f'rsi_{self.rsi_short.value}_short'], self.short_params.value))
        conditions.append(dataframe['close'] < dataframe[f'sma_{self.sma_short.value}_short'])
        
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> str:
        
    #     if current_profit > self.roi_profit.value:
    #         return 'Target Hit'


    # def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
    #                     current_rate: float, current_profit: float, after_fill: bool, 
    #                     **kwargs) -> Optional[float]:

    #     if self.dp.runmode.value in ('live'):
    #         api.update_task(trade, current_time)
        
    #     if current_profit > 0.03:
    #         return 0.02


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