from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, date, time
# import api
from typing import Optional
from technical import qtpylib
import talib.abstract as ta
import pandas as pd
import math
import numpy as np
from typing import Dict
from freqtrade.exchange import timeframe_to_prev_date
from scipy.signal import argrelextrema

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    stoploss_from_absolute,
    stoploss_from_open
)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '5m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 240

    process_only_new_candles = False

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
                "lookback_period": 1440,
                "required_profit": -0.005,
                "only_per_pair": False,
                "only_per_side": False,
                "unlock_at":"00:00"
            }
        ]

    def ob_dataframe(self, pair):
        ob = self.dp.orderbook(pair, maximum=200)
        bid_values = {
            'price': np.array(ob['bids'])[:,0],
            'volume': np.array(ob['bids'])[:,1],
            'side':'bid'
        }
        ask_values = {
            'price': np.array(ob['asks'])[:,0],
            'volume': np.array(ob['asks'])[:,1],
            'side':'ask'
        }
        bid_dataframe = pd.DataFrame(bid_values)
        ask_dataframe = pd.DataFrame(ask_values)
        return pd.concat((bid_dataframe,ask_dataframe))


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        kernel = 24
        dataframe["extrema"] = 0
        min_peaks = argrelextrema(dataframe["low"].values, np.less_equal, order=kernel)
        max_peaks = argrelextrema(dataframe["high"].values, np.greater_equal, order=kernel)
        for mp in min_peaks[0]:
            dataframe.at[mp, "extrema"] = -1
        for mp in max_peaks[0]:
            dataframe.at[mp, "extrema"] = 1

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        max_peak = dataframe[dataframe['extrema']==1].iloc[-1].squeeze()['high']
        min_peak = dataframe[dataframe['extrema']==-1].iloc[-1].squeeze()['low']

        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        
        ob_dataframe = self.ob_dataframe(metadata['pair'])
        ob_max_price = ob_dataframe.price.max()
        ob_min_price = ob_dataframe.price.min()

        if (ob_min_price < min_peak < ob_max_price):
            dataframe['enter_long'] = 1
        
        if (ob_min_price < max_peak < ob_max_price):
            dataframe['enter_short'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        max_peak = dataframe[dataframe['extrema']==1].iloc[-1].squeeze()['high']
        min_peak = dataframe[dataframe['extrema']==-1].iloc[-1].squeeze()['low']

        dataframe['exit_short'] = 0
        dataframe['exit_long'] = 0
        
        ob_dataframe = self.ob_dataframe(metadata['pair'])
        ob_max_price = ob_dataframe.price.max()
        ob_min_price = ob_dataframe.price.min()

        if (ob_min_price < min_peak < ob_max_price):
            dataframe['exit_short'] = 1
        
        if (ob_min_price < max_peak < ob_max_price):
            dataframe['exit_long'] = 1

        return dataframe


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        return 1


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            ob = self.ob_dataframe(pair)
            if trade.is_short:
                ob = ob[ob.side == 'ask']
                max_volume_row = ob[ob.volume == ob.volume.max()].squeeze()
                stop = (max_volume_row['price'] + 0.1) 
            else:
                ob = ob[ob.side == 'bid']
                max_volume_row = ob[ob.volume == ob.volume.max()].squeeze()
                stop = (max_volume_row['price'] - 0.1) 
            trade.set_custom_data(key='stop', value=stop)

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        return stoploss_from_absolute(
            trade.get_custom_data(key='stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )



