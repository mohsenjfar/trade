import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
from freqtrade.persistence import Trade
from statsmodels.nonparametric.smoothers_lowess import lowess
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    DecimalParameter
)
from datetime import datetime
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
    
    low = DecimalParameter(0.01, 0.03, decimals=2, default=0.01, space="buy")
    medium = DecimalParameter(0.03, 0.1, decimals=2, default=0.03, space="buy")
    high = DecimalParameter(0.1, 0.5, decimals=2, default=0.1, space="buy")
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        fractions = {"low":self.low.value, "medium":self.medium.value, "high":self.high.value}
        for level, frac in fractions.items():
            dataframe[f'smoothed_{level}'] = lowess(dataframe['close'], np.arange(len(dataframe)), frac=frac, return_sorted=False)
            dataframe[f'derivative_{level}'] = np.gradient(dataframe[f'smoothed_{level}'])

        dataframe['distance'] = np.abs(dataframe['smoothed_high'] - dataframe['smoothed_medium'])

        dataframe['sl'] = dataframe['low'].rolling(10).min()
        dataframe['ss'] = dataframe['high'].rolling(10).max()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['smoothed_medium'] < dataframe['smoothed_high']) & # Guard
                (dataframe['distance'] > dataframe['distance'].mean()) & # Guard
                (qtpylib.crossed_above(dataframe['derivative_low'], dataframe['derivative_medium'])) # Trigger
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['smoothed_medium'] > dataframe['smoothed_high']) & # Guard
                (dataframe['distance'] > dataframe['distance'].mean()) & # Guard
                (qtpylib.crossed_below(dataframe['derivative_low'], dataframe['derivative_medium'])) # Trigger
            ),
            'enter_short'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['derivative_high'], 0))
            ),
            'exit_long'] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['derivative_high'], 0))
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
        stop = last_candle['ss'] if side == "short" else last_candle['sl']
        risk = abs(stop / last_candle['close'] - 1)
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
            risk = abs(stop / last_candle['close'] - 1)

            trade.set_custom_data(key='stop', value=stop)
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
