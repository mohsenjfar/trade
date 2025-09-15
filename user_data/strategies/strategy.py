import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from typing import Dict
from statsmodels.nonparametric.smoothers_lowess import lowess
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative,
    IntParameter
)
from datetime import datetime, timedelta, date
from typing import Optional

class HybridStrategyV2(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True
    
    long_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()

        dataframe['sl'] = dataframe.loc[last_min_index:].low.min()
        dataframe['ss'] = dataframe.loc[last_max_index:].high.max()

        # fractions = {"low":0.01, "medium":0.05, "high":0.1}
        fractions = {"medium":0.05}
        for level, frac in fractions.items():
            dataframe[f'smoothed_{level}'] = lowess(dataframe['close'], np.arange(len(dataframe)), frac=frac, return_sorted=False)
            dataframe[f'first_derivative_{level}'] = np.gradient(dataframe[f'smoothed_{level}'])
            dataframe[f'second_derivative_{level}'] = np.gradient(dataframe[f'first_derivative_{level}'])

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                # (dataframe['first_derivative_high'] > 0) & # Guard
                # (dataframe['second_derivative_high'] > 0) & # Guard
                (dataframe['first_derivative_medium'] > 0) & # Guard
                # (dataframe['first_derivative_low'] > 0) & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], self.long_rsi.value)) # Trigger
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                # (dataframe['first_derivative_high'] < 0) & # Guard
                # (dataframe['second_derivative_high'] < 0) & # Guard
                (dataframe['first_derivative_medium'] < 0) & # Guard
                # (dataframe['first_derivative_low'] < 0) & # Guard
                (qtpylib.crossed_below(dataframe['rsi'], self.short_rsi.value)) # Trigger
            ),
            'enter_short'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                # (dataframe['first_derivative_high'] < 0) &
                (dataframe['first_derivative_medium'] == 0)
            ),
            'exit_long'] = 1

        dataframe.loc[
            (
                # (dataframe['first_derivative_high'] > 0) &
                (dataframe['first_derivative_medium'] == 0)
            ),
            'exit_short'] = 1

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stop = last_candle.ss if side == "short" else last_candle.sl
        risk = abs(stop / last_candle.close - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stop = trade.get_custom_data(key='stop')
        
        if stop is None:
            stop = last_candle['ss'] if trade.is_short else last_candle['sl']
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle['close'] - 1)
            trade.set_custom_data(key='risk', value=risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 1440) and (current_profit < 2 * risk),
        )
        if any(conditions): return "Trade expired!"
