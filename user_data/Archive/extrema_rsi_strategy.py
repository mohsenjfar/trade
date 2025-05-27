import numpy as np
import pandas as pd
from freqtrade.strategy import (
    IStrategy, 
    stoploss_from_absolute,
    stoploss_from_open,
    timeframe_to_prev_date
)
import talib.abstract as ta
from scipy.signal import argrelextrema
from datetime import datetime, timedelta
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

    startup_candle_count: int = 240


    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        max_idx = argrelextrema(dataframe['rsi'].values, np.greater, order=self.window)[0]
        min_idx = argrelextrema(dataframe['rsi'].values, np.less, order=self.window)[0]
        first_derivative = np.gradient(dataframe['rsi'].dropna())
        second_derivative = np.gradient(first_derivative)
        threshold_sd = np.mean(second_derivative) + np.std(second_derivative)
        sharp_change_idx = np.where(np.abs(second_derivative) > threshold_sd)[0]
        critical_max_idx = np.intersect1d(max_idx, sharp_change_idx)
        dataframe['first_max_rsi'] = dataframe.rsi.iat[critical_max_idx[-1]]
        dataframe['second_max_rsi'] = dataframe.rsi.iat[critical_max_idx[-2]]
        dataframe['first_max_price'] = dataframe.high.iat[critical_max_idx[-1]]
        dataframe['second_max_price'] = dataframe.high.iat[critical_max_idx[-2]]
        critical_min_idx = np.intersect1d(min_idx, sharp_change_idx)
        dataframe['first_min_rsi'] = dataframe.rsi.iat[critical_min_idx[-1]]
        dataframe['second_min_rsi'] = dataframe.rsi.iat[critical_min_idx[-2]]
        dataframe['first_min_price'] = dataframe.low.iat[critical_min_idx[-1]]
        dataframe['second_min_price'] = dataframe.low.iat[critical_min_idx[-2]]

        return dataframe


    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe['first_min_rsi'] > dataframe['second_min_rsi']) &
            (dataframe['first_min_price'] > dataframe['second_min_price']) &
            (dataframe['first_min_rsi'] < 50) &
            (dataframe['second_min_rsi'] < 50),
            'enter_long'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe['first_max_rsi'] < dataframe['second_max_rsi']) &
            (dataframe['first_max_price'] < dataframe['second_max_price']) &
            (dataframe['first_max_rsi'] > 50) &
            (dataframe['second_max_rsi'] > 50),
            'enter_short'
        ] = 1

        return dataframe


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        pre_trade_candle = dataframe.loc[-1].squeeze()
        stop_price = pre_trade_candle.high if side == 'short' else pre_trade_candle.low
        risk = abs(stop_price / rate - 1)
        if risk > 0.02:
            return False
        
        return True
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        stop_price = pre_trade_candle.high if trade.is_short else pre_trade_candle.low

        return stoploss_from_absolute(
            stop_price,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):

        if current_profit > 0.04:
            return 'Target Hit'