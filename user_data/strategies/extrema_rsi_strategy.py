import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, stoploss_from_absolute
import talib
from scipy.signal import argrelextrema
from datetime import datetime
from typing import Optional
from freqtrade.persistence import Trade

class ExtremaRSIStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.02

    window = 1

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    process_only_new_candles = False

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:

        dataframe['rsi'] = talib.RSI(dataframe['close'], timeperiod=14)
        max_idx = argrelextrema(dataframe['rsi'].values, np.greater, order=self.window)[0]
        min_idx = argrelextrema(dataframe['rsi'].values, np.less, order=self.window)[0]
        first_derivative = np.gradient(dataframe['rsi'])
        second_derivative = np.gradient(first_derivative)
        threshold_sd = np.mean(second_derivative) + np.std(second_derivative)
        sharp_change_idx = np.where(np.abs(second_derivative) > threshold_sd)[0]
        critical_max_idx = np.intersect1d(max_idx, sharp_change_idx)
        critical_min_idx = np.intersect1d(min_idx, sharp_change_idx)
        dataframe.loc[critical_max_idx, 'critical_max_rsi'] = dataframe.loc[critical_max_idx, 'rsi']
        dataframe.loc[critical_min_idx, 'critical_min_rsi'] = dataframe.loc[critical_min_idx, 'rsi']
        dataframe.loc[critical_max_idx, 'critical_max_close'] = dataframe.loc[critical_max_idx, 'close']
        dataframe.loc[critical_min_idx, 'critical_min_close'] = dataframe.loc[critical_min_idx, 'close']
        dataframe.fillna(method='ffill', inplace=True)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe['critical_min_rsi'] > dataframe['critical_min_rsi'].shift(1)) &
            (dataframe['critical_min_close'] > dataframe['critical_min_close'].shift(1)) &
            (dataframe['critical_min_rsi'] < 50) &
            (dataframe['critical_min_rsi'].shift(1) < 50),
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe['critical_max_rsi'] < dataframe['critical_max_rsi'].shift(1)) &
            (dataframe['critical_max_close'] < dataframe['critical_max_close'].shift(1)) &
            (dataframe['critical_max_rsi'] > 50) &
            (dataframe['critical_max_rsi'].shift(1) > 50),
            'enter_short'
        ] = 1

        return dataframe


    def order_filled(self, pair: str, trade: Trade, order: 'Order', current_time: datetime, **kwargs) -> None:

        if trade.nr_of_successful_entries == 1:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            prev_candle = dataframe.iloc[-1].squeeze()
            stop_price = prev_candle.high if trade.is_short else prev_candle.low
            risk = abs(stop_price / trade.open_rate - 1)
            trade.set_custom_data(key='risk', value=risk)

        return None


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:
        
        return trade.get_custom_data(key='risk', default=self.stoploss)
    

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        
        risk = trade.get_custom_data(key='risk')

        if current_profit > 2 * risk:
            return 'Target Hit'