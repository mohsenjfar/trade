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

    # We use custom_stoploss
    stoploss = -1

    trade_max_loss_allowed = 0.005  # 0.5% of equity per trade

    timeframe = '15m'
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

    # ------------------------------------------------------------------
    # Feature extraction for RSI cycles
    # ------------------------------------------------------------------
    def extract_features(self, df, c1, c2, col, name, direction="forward"):

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
        values = groups.max() if col == "high" else groups.min()
        values = values.reset_index().rename(columns={col: name})
        values["index"] = intervals.left

        df = df.merge(values, left_on=df.index, right_on="index", how="left")

        return df.drop(["range_id_x", "range_id_y", "index"], axis=1)

    def populate_features(self, dataframe: DataFrame) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)

        # Overbought cycle (RSI > 70 then back below)
        c1_over = qtpylib.crossed_above(dataframe["rsi"], 70)
        c2_over = qtpylib.crossed_below(dataframe["rsi"], 70)
        dataframe = self.extract_features(dataframe, c1_over, c2_over, "high", "max_long")
        dataframe = self.extract_features(dataframe, c2_over, c1_over, "low", "min_long")

        # Oversold cycle (RSI < 30 then back above)
        c1_under = qtpylib.crossed_below(dataframe["rsi"], 30)
        c2_under = qtpylib.crossed_above(dataframe["rsi"], 30)
        dataframe = self.extract_features(dataframe, c1_under, c2_under, "low", "min_short")
        dataframe = self.extract_features(dataframe, c2_under, c1_under, "high", "max_short")

        return dataframe

    # ------------------------------------------------------------------
    # Informative timeframes
    # ------------------------------------------------------------------
    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.populate_features(dataframe)
        return dataframe

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.populate_features(dataframe)
        return dataframe

    # ------------------------------------------------------------------
    # Main timeframe indicators
    # ------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        # Build structural triggers once per RSI cycle
        mask_long = qtpylib.crossed_above(dataframe["rsi"], self.min_rsi.value)
        dataframe["long_trigger"] = np.where(mask_long, dataframe["high"].shift(1), np.nan)

        mask_short = qtpylib.crossed_below(dataframe["rsi"], self.max_rsi.value)
        dataframe["short_trigger"] = np.where(mask_short, dataframe["low"].shift(1), np.nan)

        # Keep last valid trigger
        dataframe["long_trigger"] = dataframe["long_trigger"].ffill()
        dataframe["short_trigger"] = dataframe["short_trigger"].ffill()

        return dataframe

    # ------------------------------------------------------------------
    # Entries
    # ------------------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # LONG:
        # - 4h in bullish phase (price above last 4h min_long)
        # - 1h RSI in deep reactive phase (true oversold on 1h)
        # - 15m price breaks structural long_trigger up
        dataframe.loc[
            (
                (dataframe["close_4h"] > dataframe["min_long_4h"].ffill()) &
                (dataframe["rsi_1h"] < 30) &
                (qtpylib.crossed_above(dataframe["close"], dataframe["long_trigger"]))
            ),
            "enter_long"
        ] = 1

        # SHORT:
        # - 4h in bearish phase (price below last 4h max_short)
        # - 1h RSI in deep reactive phase (true overbought on 1h)
        # - 15m price breaks structural short_trigger down
        dataframe.loc[
            (
                (dataframe["close_4h"] < dataframe["max_short_4h"].ffill()) &
                (dataframe["rsi_1h"] > 70) &
                (qtpylib.crossed_below(dataframe["close"], dataframe["short_trigger"]))
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # exits fully handled by custom_stoploss (structural trailing)
        return dataframe

    # ------------------------------------------------------------------
    # Risk: leverage and stake
    # ------------------------------------------------------------------
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        stop = last_candle["max_long"] if side == "short" else last_candle["min_short"]

        if stop is None or np.isnan(stop):
            return 1.0

        risk = abs(stop / current_rate - 1)
        if risk == 0:
            return 1.0

        lev = self.trade_max_loss_allowed / risk
        return float(max(1, min(ceil(lev), max_leverage)))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        stop = last_candle["max_long"] if side == "short" else last_candle["min_short"]

        if stop is None or np.isnan(stop):
            return 0

        risk = abs(stop / current_rate - 1)
        if risk == 0 or risk < 0.002:
            return 0

        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.trade_max_loss_allowed / (risk * leverage)

        return float(min(stake, max_stake))

    # ------------------------------------------------------------------
    # Structural trailing stoploss
    # ------------------------------------------------------------------
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        stop = trade.get_custom_data("stop")

        # Initialize structural stop at opposite RSI cycle extreme
        if stop is None:
            base_stop = last_candle["max_long"] if trade.is_short else last_candle["min_short"]
            if base_stop is None or np.isnan(base_stop):
                return None

            stop = base_stop
            trade.set_custom_data("stop", stop)

            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data("risk", risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        # Structural trailing
        if stop is not None and not np.isnan(stop):
            if trade.is_short:
                # SHORT: trail down to newer cycle highs
                ss_15m = last_candle.get("max_short")
                if ss_15m is not None and not np.isnan(ss_15m):
                    stop = min(stop, ss_15m)

                ss_1h = last_candle.get("max_short_1h")
                if ss_1h is not None and not np.isnan(ss_1h):
                    stop = min(stop, ss_1h)

            else:
                # LONG: trail up to newer cycle lows
                sl_15m = last_candle.get("min_long")
                if sl_15m is not None and not np.isnan(sl_15m):
                    stop = max(stop, sl_15m)

                sl_1h = last_candle.get("min_long_1h")
                if sl_1h is not None and not np.isnan(sl_1h):
                    stop = max(stop, sl_1h)

            trade.set_custom_data("stop", stop)

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
