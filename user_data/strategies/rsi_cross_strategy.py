import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date,
    stoploss_from_absolute,
    informative
)
from datetime import datetime
from typing import Optional

class RSICrossStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005
    
    multiplexer = 1.5

    timeframe = '5m'
    inf_timeframe = '1h'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    position_adjustment_enable = True

    @informative(inf_timeframe)
    def populate_indicators_inf_timeframe(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe[f'rsi_max_index'] = dataframe[dataframe['rsi'] > 60].index.max()
        dataframe[f'rsi_min_index'] = dataframe[dataframe['rsi'] < 40].index.max()

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_group'] = (dataframe['rsi'] >= 60).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 60)
        dataframe['below_group'] = (dataframe['rsi'] <= 40).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 40)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['close'], dataframe['max_high'])
            ), ["enter_long" , "enter_tag"]] = (1, "break") # type: ignore

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['rsi'], 40)
            ), ["enter_long" , "enter_tag"]] = (1, "reaction") # type: ignore

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['close'], dataframe['min_low'])
            ), ["enter_short" , "enter_tag"]] = (1, "break") # type: ignore

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['rsi'], 60)
            ), ["enter_short" , "enter_tag"]] = (1, "reaction") # type: ignore

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        prev_candle = dataframe.iloc[-1].squeeze()

        if entry_tag == 'break':
            trade_side = -1 if side == "short" else 1
            stop = prev_candle.close + (trade_side * prev_candle.atr * self.multiplexer)

        if entry_tag == 'reaction':
            stop = prev_candle['max_high'] if side == 'short' else prev_candle['min_low']

        risk = abs(1 - current_rate / stop) # type: ignore

        return max(min(max_stake * self.trade_max_loss_allowed / risk, max_stake), min_stake) # type: ignore


    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        stop = trade.get_custom_data(key='stop', default=None)
        if stop:
            risk = abs(1 - trade.open_rate / stop)
            if (current_profit > 2 * risk) and (trade.nr_of_successful_exits == 0):
                return - trade.stake_amount / 2


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        stop = trade.get_custom_data(key='stop', default=None)
        if stop is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
            trade_candle = dataframe.loc[dataframe['date'] == trade_date].squeeze()
            if trade.enter_tag == "break":
                side = -1 if trade.is_short else 1
                stop = trade_candle.close + (side * trade_candle.atr * self.multiplexer)
            else:
                stop = trade_candle.max_high if trade.is_short else trade_candle.min_low
            trade.set_custom_data(key='stop', value=stop)

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str: # type: ignore

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        prev_candle = dataframe.iloc[-1].squeeze()

        conditions = (
            prev_candle['rsi'] > 70 and trade.enter_tag == "reaction" and not trade.is_short,
            prev_candle['rsi'] < 30 and trade.enter_tag == "reaction" and trade.is_short
        )
        if any(conditions):
            return 'Reaction target hit'


        conditions = (
            prev_candle[f'rsi_{self.inf_timeframe}'] < 30 and trade.enter_tag == "break" and trade.is_short,
            prev_candle[f'rsi_{self.inf_timeframe}'] > 70 and trade.enter_tag == "break" and not trade.is_short
        )
        if any(conditions):
            return 'Break target hit'