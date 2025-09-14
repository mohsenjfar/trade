import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative
)
from datetime import datetime
from typing import Optional

class ReactionStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '1m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    def analyze_extrema(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        dataframe.loc[dataframe['max_high'] == dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low'] == dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-3:]

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()

        dataframe['sl'] = dataframe.loc[last_max_index:].low.min()
        dataframe['ss'] = dataframe.loc[last_min_index:].high.max()

        return dataframe

    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['max_high']))
            ), ["enter_long" , "enter_tag"]] = (1, "break")

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['min_low']))
            ), ["enter_short" , "enter_tag"]] = (1, "break")

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

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
        stop = last_candle.ss if trade.is_short else last_candle.sl

        if trade.get_custom_data(key='stop') is None:
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle.close - 1)
            trade.set_custom_data(key='risk', value=risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %") 

        if stop != trade.get_custom_data(key='stop'):
            self.dp.send_msg(f"New stop set for ({pair}): {stop:.4f}")

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
            (trade_duration > 60) and (current_profit < 2 * risk),
        )
        if any(conditions): return "Trade expired!"

