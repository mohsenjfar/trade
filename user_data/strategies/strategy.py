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

class MultiframeRSIStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

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
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-1:]

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()

        dataframe['slr'] = dataframe.loc[last_min_index:].low.min()
        dataframe['ssr'] = dataframe.loc[last_max_index:].high.max()
        
        dataframe['slb'] = dataframe.loc[last_max_index:].low.min()
        dataframe['ssb'] = dataframe.loc[last_min_index:].high.max()

        return dataframe

    @informative("1h")
    @informative("15m")
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['max_high'])
            ), ["enter_long" , "enter_tag"]] = (1, "break")

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['max_high']))
            ), ["enter_short" , "enter_tag"]] = (1, "reaction")

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['min_low'])
            ), ["enter_short" , "enter_tag"]] = (1, "break")
        
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['min_low']))
            ), ["enter_long" , "enter_tag"]] = (1, "reaction")

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
        if entry_tag == "reaction":
            stop = last_candle.ssr if side == "short" else last_candle.slr
        elif entry_tag == "break":
            stop = last_candle.ssb if side == "short" else last_candle.slb
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
            if trade.enter_tag == "reaction":
                stop = last_candle.ssr if trade.is_short else last_candle.slr
            else:
                stop = last_candle.ssb if trade.is_short else last_candle.slb
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle.close - 1)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        conditions = (
            all(
                last_candle.slb < stop,
                trade.is_short,
                last_candle.rsi > 30,
                last_candle.rsi_15m < 30
            ),
            all(
                last_candle.ssb > stop,
                not trade.is_short,
                last_candle.rsi < 70,
                last_candle.rsi_15m > 70
            )
        )
        if any(conditions) and not trade.get_custom_data(key='5m_break'):
            stop = last_candle.slb if trade.is_short else last_candle.ssb
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='5m_break', value=True)
            self.dp.send_msg("5m RSI break, new stop was set")
        
        conditions = (
            all(
                last_candle.slb_15m < stop,
                trade.is_short,
                last_candle.rsi_15m > 30,
                last_candle.rsi_1h < 30
            ),
            all(
                last_candle.ssb_15m > stop,
                not trade.is_short,
                last_candle.rsi_15m < 70,
                last_candle.rsi_1h > 70
            )
        )
        if any(conditions) and not trade.get_custom_data(key='15m_break'):
            stop = last_candle.slb_15m if trade.is_short else last_candle.ssb_15m
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='15m_break', value=True)
            self.dp.send_msg("15m RSI break, new stop was set")

        return stoploss_from_absolute(
            trade.get_custom_data(key='stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 60) and (current_profit < 0),
            (trade_duration > 1440) and (current_profit < 2 * risk)
        )
        if any(conditions): return "Trade expired!"
