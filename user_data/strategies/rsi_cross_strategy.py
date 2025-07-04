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
from datetime import datetime, timedelta
from typing import Optional

class RSICrossStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'
    inf_timeframe = '1h'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    position_adjustment_enable = True

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 16,
                "trade_limit": 2,
                "stop_duration_candles": 4,
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": False
            }
        ]

    @informative(inf_timeframe)
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe['rsi_max_index'] = dataframe[dataframe['rsi'] > 60].index.max()
        dataframe['rsi_min_index'] = dataframe[dataframe['rsi'] < 40].index.max()

        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_70_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_30_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high_above_70'] = dataframe.groupby('above_70_group')['high'].transform('max')
        dataframe['min_low_below_30'] = dataframe.groupby('below_30_group')['low'].transform('min')
        dataframe.loc[dataframe['above_70_group'] == 0, 'max_high_above_70'] = None
        dataframe.loc[dataframe['below_30_group'] == 0, 'min_low_below_30'] = None
        dataframe = dataframe.ffill()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['close'], dataframe['max_high_above_70']) &
                (dataframe[f'rsi_{self.inf_timeframe}'] < 50) &
                (dataframe[f'rsi_{self.inf_timeframe}'] > dataframe[f'rsi_{self.inf_timeframe}'].shift(1)) &
                (dataframe['rsi_min_index_4h'] > dataframe['rsi_max_index_4h'])
            ), ["enter_long" , "enter_tag"]] = (1, "break") # type: ignore

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['close'], dataframe['min_low_below_30']) &
                (dataframe[f'rsi_{self.inf_timeframe}'] > 50) &
                (dataframe[f'rsi_{self.inf_timeframe}'] < dataframe[f'rsi_{self.inf_timeframe}'].shift(1)) &
                (dataframe['rsi_max_index_4h'] > dataframe['rsi_min_index_4h'])
            ), ["enter_short" , "enter_tag"]] = (1, "break") # type: ignore

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        prev_candle = dataframe.iloc[-1].squeeze()
        stop = prev_candle['low'] if side == "long" else prev_candle['high']
        risk = abs(1 - current_rate / stop) # type: ignore

        return max(min(max_stake * self.trade_max_loss_allowed / risk, max_stake), min_stake) # type: ignore


    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        stop = pre_trade_candle.high if trade.is_short else pre_trade_candle.low
        risk = abs(1 - trade.open_rate / stop)

        if (current_profit > 2 * risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str: # type: ignore

        if ((current_time - trade.open_date_utc).seconds / 3600 > 24) and current_profit < 0.05:
            return 'Trade expired'


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        stop = pre_trade_candle.high if trade.is_short else pre_trade_candle.low
        prev_candle = dataframe.iloc[-1].squeeze()

        conditions = (
            (prev_candle[f'rsi_{self.inf_timeframe}'] < 35 and trade.is_short),
            (prev_candle[f'rsi_{self.inf_timeframe}'] > 65 and not trade.is_short),
        )

        if any(conditions) and current_profit > 0.1:
            return current_profit * 0.3

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )