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

    timeframe = '1h'
    can_short: bool = True
    process_only_new_candles = True

    use_exit_signal = True
    use_custom_stoploss = True

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

        c1_over = qtpylib.crossed_above(dataframe["rsi"], 70)
        c2_over = qtpylib.crossed_below(dataframe["rsi"], 70)
        dataframe = self.extract_features(dataframe, c1_over, c2_over, "high", "max_high")

        c1_under = qtpylib.crossed_below(dataframe["rsi"], 30)
        c2_under = qtpylib.crossed_above(dataframe["rsi"], 30)
        dataframe = self.extract_features(dataframe, c1_under, c2_under, "low", "min_low")

        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.populate_features(dataframe)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        mask_long = qtpylib.crossed_above(dataframe["rsi"], self.min_rsi.value)
        dataframe["long_trigger"] = np.where(mask_long, dataframe["high"].shift(1), np.nan)

        mask_short = qtpylib.crossed_below(dataframe["rsi"], self.max_rsi.value)
        dataframe["short_trigger"] = np.where(mask_short, dataframe["low"].shift(1), np.nan)

        dataframe["long_trigger"] = dataframe["long_trigger"].ffill()
        dataframe["short_trigger"] = dataframe["short_trigger"].ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['rsi_4h'] < 40) &
                (qtpylib.crossed_above(dataframe["close"], dataframe["long_trigger"]))
            ),
            "enter_long"
        ] = 1

        dataframe.loc[
            (
                (dataframe['rsi_4h'] > 60) &
                (qtpylib.crossed_below(dataframe["close"], dataframe["short_trigger"]))
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["rsi"], 70))
            ),
            "exit_long"
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], 30))
            ),
            "exit_short"
        ] = 1

        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        stop = last_candle["high"] if side == "short" else last_candle["low"]
        if stop is None or np.isnan(stop): return 1.0
        risk = abs(stop / current_rate - 1)
        if risk == 0: return 1.0
        lev = self.trade_max_loss_allowed / risk
        return float(max(1, min(ceil(lev), max_leverage)))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stop = last_candle["high"] if side == "short" else last_candle["low"]
        if stop is None or np.isnan(stop): return 0
        risk = abs(stop / current_rate - 1)
        if risk == 0 or risk < 0.002: return 0
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.trade_max_loss_allowed / (risk * leverage)
        return float(min(stake, max_stake))

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        stop = trade.get_custom_data("stop")

        if stop is None:
            base_stop = last_candle["high"] if trade.is_short else last_candle["low"]
            if base_stop is None or np.isnan(base_stop):
                return None

            stop = base_stop
            trade.set_custom_data("stop", stop)

            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data("risk", risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
    
    # def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime,
    #                 current_rate: float, current_profit: float, **kwargs):

    #     dataframe_, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    #     dataframe = dataframe_.copy()
    #     last = dataframe.iloc[-1].squeeze()

    #     last_extreme = trade.get_custom_data("last_extreme")

    #     if trade.is_short:
    #         new_extreme = float(last["min_low"])
    #         if new_extreme is not None and not np.isnan(new_extreme):
    #             if last_extreme is None:
    #                 trade.set_custom_data("last_extreme", new_extreme)
    #             elif new_extreme < last_extreme:
    #                 trade.set_custom_data("last_extreme", new_extreme)
    #             else:
    #                 return "exit_cycle_reversal"
    #     else:
    #         new_extreme = float(last["max_high"])
    #         if new_extreme is not None and not np.isnan(new_extreme):
    #             if last_extreme is None:
    #                 trade.set_custom_data("last_extreme", new_extreme)
    #             elif new_extreme > last_extreme:
    #                 trade.set_custom_data("last_extreme", new_extreme)
    #             else:
    #                 return "exit_cycle_reversal"

    #     return None

