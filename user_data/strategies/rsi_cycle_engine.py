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
from datetime import datetime, timedelta
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

    def extract_features(self, df, c1, c2, e, col, name, direction="forward"):

        highs = df.loc[c1].reset_index().rename(columns={"index": "up_index"})
        crosses = df.loc[c2].reset_index().rename(columns={"index": "down_index"})

        if highs.empty or crosses.empty:
            df[name] = np.nan
            return df

        pairs = pd.merge_asof(
            highs.sort_values("up_index"),
            crosses.sort_values("down_index"),
            left_on="up_index",
            right_on="down_index",
            direction=direction,
        )

        pairs = (
            pairs[["up_index", "down_index"]]
            .drop_duplicates("down_index", keep="last")
            .dropna()
            .reset_index(drop=True)
        )

        intervals = pd.IntervalIndex.from_arrays(
            pairs["up_index"], pairs["down_index"], closed="both"
        )
        df["range_id"] = pd.cut(df.index, intervals)

        groups = df.groupby("range_id", observed=True)[col]
        values = groups.max() if e == "max" else groups.min()
        values = values.reset_index().rename(columns={col: name})
        values["index"] = intervals.left

        df = df.merge(values, left_on=df.index, right_on="index", how="left")

        return df.drop(["range_id_x", "range_id_y", "index"], axis=1)

    def populate_features(self, dataframe: DataFrame) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)

        c1_over = qtpylib.crossed_above(dataframe["rsi"], 70)
        c2_over = qtpylib.crossed_below(dataframe["rsi"], 70)

        dataframe = self.extract_features(
            dataframe, c1_over, c2_over, "max", "high", "max_high"
        )
        dataframe = self.extract_features(
            dataframe, c1_over, c2_over, "max", "rsi", "max_rsi"
        )
        dataframe = self.extract_features(
            dataframe, c2_over, c1_over, "min", "low", "sl"
        )
        dataframe = self.extract_features(
            dataframe, c2_over, c1_over, "min", "rsi", "sl_rsi"
        )

        c1_under = qtpylib.crossed_below(dataframe["rsi"], 30)
        c2_under = qtpylib.crossed_above(dataframe["rsi"], 30)

        dataframe = self.extract_features(
            dataframe, c1_under, c2_under, "min", "low", "min_low"
        )
        dataframe = self.extract_features(
            dataframe, c1_under, c2_under, "min", "rsi", "min_rsi"
        )
        dataframe = self.extract_features(
            dataframe, c2_under, c1_under, "max", "high", "ss"
        )
        dataframe = self.extract_features(
            dataframe, c2_under, c1_under, "max", "rsi", "ss_rsi"
        )

        dataframe.loc[dataframe["max_high"].notna(), "cat"] = "H"
        dataframe.loc[dataframe["min_low"].notna(), "cat"] = "L"

        return dataframe

    @informative("4h")
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        mask = qtpylib.crossed_above(dataframe["rsi"], self.min_rsi.value)
        dataframe["long_trigger"] = np.where(mask, dataframe["high"].shift(1), np.nan)

        mask = qtpylib.crossed_below(dataframe["rsi"], self.max_rsi.value)
        dataframe["short_trigger"] = np.where(mask, dataframe["low"].shift(1), np.nan)

        index = dataframe[dataframe['min_low'].notna()].index.max()
        dataframe['sl'] = dataframe.iloc[index:].low.min()

        index = dataframe[dataframe['max_high'].notna()].index.max()
        dataframe['ss'] = dataframe.iloc[index:].high.max()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:


        dataframe.loc[
            (
                # (dataframe["close"] > dataframe["max_high_4h"]) &
                (qtpylib.crossed_above(dataframe["close"], dataframe["long_trigger"].ffill()))
            ),
            "enter_long"] = 1

        dataframe.loc[
            (
                # (dataframe["close"] < dataframe["min_low_4h"]) &
                (qtpylib.crossed_below(dataframe["close"], dataframe["short_trigger"].ffill()))
            ),
            "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["rsi"], self.max_rsi.value))
            ),
            "exit_long"] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["rsi"], self.min_rsi.value))
            ),
            "exit_short"] = 1

        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stop = last_candle["ss"] if side == "short" else last_candle["sl"]
        risk = abs(stop / current_rate - 1)
        return ceil(self.trade_max_loss_allowed / risk)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stop = last_candle["ss"] if side == "short" else last_candle["sl"]
        risk = abs(stop / current_rate - 1)
        if risk < 0.002: return 0
        return min(total_stake * self.trade_max_loss_allowed / (risk * leverage), max_stake)

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if current_profit > 1:
            return 0.3

        if trade.get_custom_data("stop") is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            stop = last_candle["ss"] if trade.is_short else last_candle["sl"]
            trade.set_custom_data(key="stop", value=stop)

            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data(key="risk", value=risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        return stoploss_from_absolute(
            trade.get_custom_data("stop"),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):

        risk = trade.get_custom_data(key="risk")
        conditions_1 = (current_time - timedelta(hours=4) > trade.open_date_utc) and (current_profit < 0)
        conditions_2 = (current_time - timedelta(hours=24) > trade.open_date_utc) and (current_profit < risk * 2 * trade.leverage)
        if conditions_1 or conditions_2: return "Trade expired!"
