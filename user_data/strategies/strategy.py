from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime
from typing import Optional
from technical import qtpylib
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
from scipy.signal import argrelextrema

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.02

    timeframe = '1m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 1440

    process_only_new_candles = True

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


    def caculate_regression(self, dataframe, kernel=1440):
        dataframe_ = dataframe.copy()[-kernel:]
        x = dataframe_.index.values.reshape(-1, 1)
        y = dataframe_.close.values
        model = LinearRegression()
        model.fit(x, y)
        x = dataframe.index.values.reshape(-1, 1)
        dataframe['y'] = model.predict(x)
        dataframe['coef'] = float(model.coef_[0])
        dataframe['upper_band'] = dataframe['y'] + dataframe.high.std()
        dataframe['lower_band'] = dataframe['y'] - dataframe.low.std()
        dataframe['band_dist'] = dataframe['upper_band'] - dataframe['lower_band']
        return dataframe
    

    def calculate_extrema(self, dataframe, kernel=6):
        dataframe["extrema"] = 0
        min_peaks = argrelextrema(dataframe["low"].values, np.less_equal, order=kernel)
        max_peaks = argrelextrema(dataframe["high"].values, np.greater_equal, order=kernel)
        for mp in min_peaks[0]:
            dataframe.at[mp, "extrema"] = -1
        for mp in max_peaks[0]:
            dataframe.at[mp, "extrema"] = 1
        dataframe['last_min_peak'] = dataframe.at[min_peaks[0][-1], "low"]
        dataframe['last_max_peak'] = dataframe.at[max_peaks[0][-1], "high"]
        dataframe['h_dist'] = np.where(dataframe.extrema == 1, (dataframe.high - dataframe.upper_band), 0)
        dataframe['l_dist'] = np.where(dataframe.extrema == -1, (dataframe.lower_band - dataframe.low), 0)
        dataframe['h_ratio'] = dataframe['h_dist'] / dataframe['band_dist']
        dataframe['l_ratio'] = dataframe['l_dist'] / dataframe['band_dist']
        dataframe['l_h_ratio'] = dataframe.at[max_peaks[0][-1], "h_ratio"]
        dataframe['l_l_ratio'] = dataframe.at[min_peaks[0][-1], "l_ratio"]
        dataframe['last_max'] = dataframe.at[max_peaks[0][-1], "close"]
        dataframe['last_min'] = dataframe.at[min_peaks[0][-1], "close"]
        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.caculate_regression(dataframe)
        dataframe = self.calculate_extrema(dataframe)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['last_min']) & # Guard
                qtpylib.crossed_above(dataframe['close'], dataframe['lower_band']) # Trigger
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['last_max']) & # Guard
                qtpylib.crossed_below(dataframe['close'], dataframe['upper_band']) # Trigger
            ),
            'enter_short'
        ] = 1

        dataframe.to_csv('user_data/notebooks/df.csv', index=False)

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:


        return dataframe


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        return 1


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            self.ob_dataframe(pair).to_csv(f'user_data/notebooks/{trade.id}_ob.csv', index=False)

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()

        if trade.is_short:
            if current_candle['last_max'] > current_candle['upper_band']:
                stop = current_candle['last_max']
            elif current_candle['close'] < current_candle['lower_band']:
                stop = current_candle['last_max']
        else:
            if current_candle['last_min'] < current_candle['lower_band']:
                stop = current_candle['last_min']
            elif current_candle['close'] > current_candle['upper_band']:
                stop = current_candle['last_min']
        
        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )