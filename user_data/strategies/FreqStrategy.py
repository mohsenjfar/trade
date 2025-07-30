import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
from scipy.fft import fft, ifft, fftfreq
from scipy.signal import argrelextrema
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date,
    stoploss_from_absolute,
    stoploss_from_open,
    informative
)
from datetime import datetime, timedelta, date
from typing import Optional

class FreqStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        n = 3
        dataframe['fft_vals'] = fft(dataframe['close'])
        dataframe['freqs'] = fftfreq(len(dataframe), d=1)
        keep = np.abs(dataframe['freqs']) <= 0.1
        filtered_fft = np.zeros_like(dataframe['fft_vals'], dtype=complex)
        filtered_fft[keep] = dataframe['fft_vals'][keep]
        dataframe['smoothed'] = ifft(filtered_fft).real
        min_peaks = argrelextrema(dataframe["smoothed"].values, np.less_equal, order=1)
        max_peaks = argrelextrema(dataframe["smoothed"].values, np.greater_equal, order=1)
        dataframe.loc[(dataframe.index.isin(min_peaks[0])),'min_peaks'] = dataframe.smoothed
        dataframe.loc[(dataframe.index.isin(min_peaks[0]- n)),'long_trigger'] = dataframe.smoothed
        dataframe['long_stop'] = dataframe.low.rolling(window = n * 2).min()
        dataframe.loc[(dataframe.index.isin(max_peaks[0])),'max_peaks'] = dataframe.smoothed
        dataframe.loc[(dataframe.index.isin(max_peaks[0] - n)),'short_trigger'] = dataframe.smoothed
        dataframe['short_stop'] = dataframe.high.rolling(window = n * 2).max()
        columns = ['min_peaks','long_trigger','long_stop','max_peaks','short_trigger','short_stop']
        dataframe[columns] = dataframe[columns].ffill()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['long_trigger'])) &
                (dataframe['close'] > dataframe['min_peaks'])
            ), ["enter_long"]] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['short_trigger'])) &
                (dataframe['close'] < dataframe['max_peaks'])
            ), ["enter_short"]] = 1


        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        stop = dataframe['short_stop'].iat[-1] if side == 'short' else dataframe['long_stop'].iat[-1]
        risk = abs(stop / dataframe['close'].iat[-1] - 1)
        return max(min(max_stake * self.trade_max_loss_allowed / risk, max_stake), min_stake)


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk', default=None)
        if risk is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            stop = dataframe['short_stop'].iat[-1] if trade.is_short else dataframe['long_stop'].iat[-1]
            risk = abs(stop / dataframe['close'].iat[-1] - 1)
            self.dp.send_msg(f"Trade risk: {risk * 100:.2f} %")
            trade.set_custom_data(key='risk', value=risk)
        
        return stoploss_from_open(
            -risk,
            current_profit,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk', default=None)
        if current_profit > risk * 2:
            return "Target Hit!"
