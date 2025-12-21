import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from math import ceil
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    IntParameter,
    informative
)
from datetime import datetime
from typing import Optional


class RSICycleEngine(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '15m'
    can_short: bool = True
    process_only_new_candles = True

    use_exit_signal = True
    use_custom_stoploss = True

    position_adjustment_enable = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }

    max_rsi = IntParameter(low=51, high=100, default=70, space="sell", optimize=True, load=True)
    min_rsi = IntParameter(low=1, high=50, default=30, space="buy", optimize=True, load=True)

    def extract_features(self, dataframe, c1, c2, col, name, direction="forward"):

        df = dataframe.copy()

        starts = df.loc[c1].reset_index().rename(columns={"index": "start"})[['start']]
        ends   = df.loc[c2].reset_index().rename(columns={"index": "end"})[['end']]

        if starts.empty or ends.empty:
            dataframe[name] = np.nan
            return dataframe

        pairs = pd.merge_asof(
            starts.sort_values("start"),
            ends.sort_values("end"),
            left_on="start",
            right_on="end",
            direction=direction,
        ).dropna()[["start", "end"]]

        if pairs.empty:
            dataframe[name] = np.nan
            return dataframe

        intervals = pd.IntervalIndex.from_arrays(pairs["start"], pairs["end"], closed="both")
        df["range_id"] = pd.cut(df.index, intervals)

        e = 'max' if col == 'high' else 'min'
        df[name] = df.groupby("range_id", observed=True)[col].transform(e)
        df[name] = np.where(df[col] == df[name], df[col], np.nan)

        return dataframe.merge(df[[name]], left_index=True, right_index=True, how="left")

    def populate_features(self, dataframe: DataFrame) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)

        c1 = qtpylib.crossed_above(dataframe["rsi"], 70)
        c2 = qtpylib.crossed_below(dataframe["rsi"], 70)
        dataframe = self.extract_features(dataframe, c1, c2, "high", "max_high")
        dataframe = self.extract_features(dataframe, c2, c1, "low", "min_high")
        dataframe.loc[c2, 'short_trigger'] = dataframe.loc[c2, 'low'].shift(1)

        c1 = qtpylib.crossed_below(dataframe["rsi"], 30)
        c2 = qtpylib.crossed_above(dataframe["rsi"], 30)
        dataframe = self.extract_features(dataframe, c1, c2, "low", "min_low")
        dataframe = self.extract_features(dataframe, c2, c1, "high", "max_low")
        dataframe.loc[c2, 'long_trigger'] = dataframe.loc[c2, 'high'].shift(1)

        dataframe.loc[dataframe['max_high'].notna(),"cat"] = 'H'
        dataframe.loc[dataframe['min_low'].notna(),"cat"] = 'L'
        dataframe['cat'] = dataframe['cat'].ffill()

        return dataframe

    # @informative("1h")
    @informative("1h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['max_low_1h'].ffill()) &
                (qtpylib.crossed_above(dataframe["close"], dataframe["long_trigger"].ffill()))
            ),
            "enter_long"
        ] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['min_high_1h'].ffill()) &
                (qtpylib.crossed_below(dataframe["close"], dataframe["short_trigger"].ffill()))
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # def leverage(self, pair: str, current_time: datetime, current_rate: float,
    #              proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
    #              **kwargs) -> float:

    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
    #     last_candle = dataframe.iloc[-1].squeeze()

    #     stop = last_candle["max_high"] if side == "short" else last_candle["min_low"]
    #     if stop is None or np.isnan(stop): return 1.0
    #     risk = abs(stop / current_rate - 1)
    #     if risk == 0: return 1.0
    #     lev = self.trade_max_loss_allowed / risk
    #     return float(max(1, min(ceil(lev), max_leverage)))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe_, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        dataframe = dataframe_.copy()
        dataframe['max_high'] = dataframe['max_high'].ffill()
        dataframe['min_low'] = dataframe['min_low'].ffill()
        last_candle = dataframe.iloc[-1].squeeze()
        stop = last_candle["max_high"] if side == "short" else last_candle["min_low"]
        if stop is None or np.isnan(stop): return 0
        risk = abs(stop / current_rate - 1)
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.trade_max_loss_allowed / (risk * leverage)
        return float(min(stake, max_stake))

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        risk = trade.get_custom_data(key='risk')
        if (current_profit > risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:

        dataframe_, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        dataframe = dataframe_.copy()
        dataframe['max_high'] = dataframe['max_high'].ffill()
        dataframe['min_low'] = dataframe['min_low'].ffill()
        last_candle = dataframe.iloc[-1].squeeze()

        stop = trade.get_custom_data("stop")

        if stop is None:
            stop = last_candle["max_high"] if trade.is_short else last_candle["min_low"]
            trade.set_custom_data("stop", float(stop))

            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data("risk", risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        if trade.is_short and stop is not None and not np.isnan(stop):
            if (last_candle['max_low'] < stop) and last_candle['cat'] == 'L':
                trade.set_custom_data("stop", float(last_candle['max_low']))

        if not trade.is_short and stop is not None and not np.isnan(stop):
            if (last_candle['min_high'] > stop) and last_candle['cat'] == 'H':
                trade.set_custom_data("stop", float(last_candle['min_high']))

        return stoploss_from_absolute(
            trade.get_custom_data("stop"),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )

