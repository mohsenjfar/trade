import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from scipy.signal import argrelextrema
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative
)
from datetime import datetime
from typing import Optional


class AtlasEngine(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    # حداکثر ریسک روی کل اکانت در هر معامله (۰.۵٪)
    trade_max_loss_allowed = 0.005

    kernel = 2
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

    # ---------------------------------------------------------
    # Pivot Detection
    # ---------------------------------------------------------
    def detect_pivots(self, dataframe: DataFrame, kernel: int = 2) -> DataFrame:
        dataframe["pivot_high"] = np.nan
        dataframe["pivot_low"] = np.nan

        highs = dataframe["high"].values
        lows = dataframe["low"].values

        max_peaks = argrelextrema(highs, np.greater_equal, order=kernel)[0]
        min_peaks = argrelextrema(lows, np.less_equal, order=kernel)[0]

        dataframe.loc[dataframe.index.isin(max_peaks), "pivot_high"] = dataframe["high"]
        dataframe.loc[dataframe.index.isin(min_peaks), "pivot_low"] = dataframe["low"]

        return dataframe

    # ---------------------------------------------------------
    # ATR Filter → sig_pivot_high / sig_pivot_low
    # ---------------------------------------------------------
    def filter_pivots_atr(self, dataframe: DataFrame, atr_mult: float = 1.0) -> DataFrame:
        # ATR اگر قبلاً نباشد، محاسبه کن
        if "ATR" not in dataframe.columns:
            dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)

        dataframe["sig_pivot_high"] = np.where(
            (dataframe["pivot_high"].notna()) &
            ((dataframe["pivot_high"] - dataframe["pivot_high"].shift(1).ffill()).abs() >
             atr_mult * dataframe["ATR"]),
            dataframe["pivot_high"],
            np.nan,
        )

        dataframe["sig_pivot_low"] = np.where(
            (dataframe["pivot_low"].notna()) &
            ((dataframe["pivot_low"] - dataframe["pivot_low"].shift(1).ffill()).abs() >
             atr_mult * dataframe["ATR"]),
            dataframe["pivot_low"],
            np.nan,
        )
        return dataframe

    # ---------------------------------------------------------
    # Distance Filter → sig_pivot_high_dist / sig_pivot_low_dist
    # (روی sig_pivot_* اعمال می‌شود، نه pivot خام)
    # ---------------------------------------------------------
    def filter_pivots_distance(self, dataframe: DataFrame, min_distance: float = 0.003) -> DataFrame:
        dataframe["sig_pivot_high_dist"] = np.where(
            (dataframe["sig_pivot_high"].notna()) &
            ((dataframe["sig_pivot_high"] - dataframe["sig_pivot_high"].shift(1).ffill()).abs() >
             dataframe["close"] * min_distance),
            dataframe["sig_pivot_high"],
            np.nan,
        )

        dataframe["sig_pivot_low_dist"] = np.where(
            (dataframe["sig_pivot_low"].notna()) &
            ((dataframe["sig_pivot_low"] - dataframe["sig_pivot_low"].shift(1).ffill()).abs() >
             dataframe["close"] * min_distance),
            dataframe["sig_pivot_low"],
            np.nan,
        )
        return dataframe

    # ---------------------------------------------------------
    # Structure Labeling (روی sig_pivot_high / sig_pivot_low)
    # ---------------------------------------------------------
    def label_structure(self, dataframe: DataFrame) -> DataFrame:
        prev_high = dataframe["sig_pivot_high"].ffill().shift(1)
        dataframe["high_label"] = np.where(
            dataframe["sig_pivot_high"].notna(),
            np.where(dataframe["sig_pivot_high"] > prev_high, "HH", "LH"),
            None,
        )

        prev_low = dataframe["sig_pivot_low"].ffill().shift(1)
        dataframe["low_label"] = np.where(
            dataframe["sig_pivot_low"].notna(),
            np.where(dataframe["sig_pivot_low"] < prev_low, "LL", "HL"),
            None,
        )
        return dataframe

    # ---------------------------------------------------------
    # Informative 4H
    # ---------------------------------------------------------
    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.detect_pivots(dataframe, kernel=2)
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.filter_pivots_distance(dataframe, min_distance=0.003)
        dataframe = self.label_structure(dataframe)
        return dataframe

    # ---------------------------------------------------------
    # Informative 1H
    # ---------------------------------------------------------
    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.detect_pivots(dataframe, kernel=2)
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.label_structure(dataframe)
        return dataframe

    # ---------------------------------------------------------
    # Main timeframe (15m)
    # ---------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ATR
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)

        # Pivot + ATR + Distance + Structure (کاملاً هم‌راستا با 4h/1h)
        dataframe = self.detect_pivots(dataframe, kernel=self.kernel)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.filter_pivots_distance(dataframe, min_distance=0.003)
        dataframe = self.label_structure(dataframe)

        # آخرین pivot مهم LTF (برای استاپ و R:R)
        dataframe["last_sig_low"] = dataframe["sig_pivot_low_dist"].ffill()
        dataframe["last_sig_high"] = dataframe["sig_pivot_high_dist"].ffill()

        # اولین pivot مهم بعدی (نقدینگی LTF)
        dataframe["next_sig_high"] = dataframe["sig_pivot_high_dist"][::-1].ffill()[::-1]
        dataframe["next_sig_low"] = dataframe["sig_pivot_low_dist"][::-1].ffill()[::-1]

        # --- R:R لانگ ---
        risk_long = dataframe["close"] - dataframe["last_sig_low"]
        reward_long = dataframe["next_sig_high"] - dataframe["close"]
        dataframe["rr_long"] = np.where(
            (risk_long > 0) & (reward_long > 0),
            reward_long / risk_long,
            np.nan,
        )

        # --- R:R شورت ---
        risk_short = dataframe["last_sig_high"] - dataframe["close"]
        reward_short = dataframe["close"] - dataframe["next_sig_low"]
        dataframe["rr_short"] = np.where(
            (risk_short > 0) & (reward_short > 0),
            reward_short / risk_short,
            np.nan,
        )

        # فقط چیزهایی که منطقاً باید ffill شوند:
        ffill_cols = [
            "high_label", "low_label",
            "high_label_4h", "low_label_4h",
            "high_label_1h", "low_label_1h",
            "sig_pivot_high_dist", "sig_pivot_low_dist",
            "last_sig_low", "last_sig_high",
            "next_sig_high", "next_sig_low",
            "rr_long", "rr_short",
        ]
        for col in ffill_cols:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].ffill()

        return dataframe

    # ---------------------------------------------------------
    # Entry Logic
    # ---------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        hl4 = dataframe["high_label_4h"].ffill()
        ll4 = dataframe["low_label_4h"].ffill()
        hl1 = dataframe["high_label_1h"].ffill()
        ll1 = dataframe["low_label_1h"].ffill()
        lh = dataframe["high_label"].ffill()
        ll = dataframe["low_label"].ffill()

        sig_high_ltf = dataframe["sig_pivot_high_dist"].ffill()
        sig_low_ltf = dataframe["sig_pivot_low_dist"].ffill()

        # -------------------------
        # LONG ENTRY
        # -------------------------
        long_cond = (
            (hl4 == "HH") & (ll4 == "HL") &        # Guard 4h
            (hl1 == "HH") & (ll1 == "HL") &        # Guard 1h
            (ll == "HL") &                         # Guard LTF
            qtpylib.crossed_above(dataframe["close"], sig_high_ltf) &  # Trigger
            (dataframe["rr_long"] >= 2.0)          # Guard R:R
        )

        dataframe.loc[long_cond, "enter_long"] = 1

        # -------------------------
        # SHORT ENTRY
        # -------------------------
        short_cond = (
            (hl4 == "LH") & (ll4 == "LL") &        # Guard 4h
            (hl1 == "LH") & (ll1 == "LL") &        # Guard 1h
            (lh == "LH") &                         # Guard LTF
            qtpylib.crossed_below(dataframe["close"], sig_low_ltf) &  # Trigger
            (dataframe["rr_short"] >= 2.0)         # Guard R:R
        )

        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    # ---------------------------------------------------------
    # Exit Logic (فعلاً خالی، تکیه بر استاپ داینامیک)
    # ---------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ---------------------------------------------------------
    # Position Sizing بر اساس ریسک واقعی
    # ---------------------------------------------------------
    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # برای شورت از last_sig_high، برای لانگ از last_sig_low
        if side == "short":
            stop = last_candle["last_sig_high"]
        else:
            stop = last_candle["last_sig_low"]

        # اگر به هر دلیل stop نداشتیم، از ریسک ثابت استفاده کنیم
        if np.isnan(stop) or stop == 0:
            return min(max_stake, proposed_stake)

        risk = abs(stop / current_rate - 1)

        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.trade_max_loss_allowed / risk

        return float(min(stake, max_stake))

    # ---------------------------------------------------------
    # Dynamic Stoploss (initial + trailing بر اساس pivots)
    # ---------------------------------------------------------
    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # pivot مرجع برای trailing: آخرین sig_pivot_*_dist
        if trade.is_short:
            raw_pivot = last_candle["last_sig_high"]
        else:
            raw_pivot = last_candle["last_sig_low"]

        # اگر pivot نداریم، برگرد به استاپ پیش‌فرض
        if np.isnan(raw_pivot):
            return 0.02  # 2% fallback

        # استاپ اولیه فقط یک‌بار تنظیم می‌شود
        if trade.get_custom_data("stop") is None:
            # offset بر اساس ATR
            atr = last_candle.get("ATR", np.nan)
            if np.isnan(atr):
                offset = current_rate * 0.002  # 0.2%
            else:
                offset = 0.3 * atr

            direction = 1 if trade.is_short else -1
            stop = raw_pivot + direction * offset

            trade.set_custom_data(key="stop", value=stop)

            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data(key="risk", value=risk)

            # اگر notification استفاده می‌کنی
            if hasattr(self.dp, "send_msg"):
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        # trailing: اگر pivot جدید در جهت معامله حرکت کرده، استاپ را به pivot جدید ببریم
        current_stop = trade.get_custom_data("stop")

        if trade.is_short:
            # در شورت، stop باید پایین‌تر بیاید (به نفع ما)
            if raw_pivot < current_stop:
                trade.set_custom_data(key="stop", value=raw_pivot)
        else:
            # در لانگ، stop باید بالاتر برود (به نفع ما)
            if raw_pivot > current_stop:
                trade.set_custom_data(key="stop", value=raw_pivot)

        final_stop = trade.get_custom_data("stop")

        return stoploss_from_absolute(
            final_stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
