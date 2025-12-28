# -*- coding: utf-8 -*-
# AtlasEngine v3 — High R:R Focus (Long-only)
# کلیدها:
# - Long-only در رژیم ترنددار قوی (EMA200 صعودی + ADX>25)
# - شکست معتبر + برگشت (retest) برای ورود با استاپ نزدیک و منطقی
# - فیلتر حجم و ولتیلیتی (BB squeeze-break)
# - محاسبه‌ی R:R واقع‌گرایانه: فقط سیگنال‌هایی که R:R >= 3 را عبور می‌دهند
# - استاپ اولیه کوچک (بر پایه‌ی سوئینگ اخیر + 0.5×ATR) و تریلینگ فقط پس از BE
# - خروج‌ها توسط تریلینگ/ROI پله‌ای مدیریت می‌شوند

import numpy as np
import talib.abstract as ta
from pandas import DataFrame
from scipy.signal import argrelextrema
from datetime import datetime
from typing import Optional

import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    informative,
    stoploss_from_absolute,
)

class AtlasEngine(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = '15m'
    can_short: bool = False  # Long-only برای تمرکز بر R:R بالا
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

    startup_candle_count = 300

    # مدیریت ریسک حساب
    stoploss = -1
    trade_max_loss_allowed = 0.005  # 0.5% از موجودی آزاد هر معامله

    # هسته‌ی Pivot
    kernel = 2

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
    # Distance Filter
    # ---------------------------------------------------------
    def filter_pivots_distance(self, dataframe: DataFrame, min_distance: float = 0.004) -> DataFrame:
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
    # Structure Labeling
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
    # Informative 4H — ساختار و ولتیلیتی
    # ---------------------------------------------------------
    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.detect_pivots(dataframe, kernel=2)
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.filter_pivots_distance(dataframe, min_distance=0.004)
        dataframe = self.label_structure(dataframe)
        # Bollinger برای ارزیابی رژیم ولتیلیتی
        bb = ta.BBANDS(dataframe['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        return dataframe

    # ---------------------------------------------------------
    # Informative 1H — روند و قدرت
    # ---------------------------------------------------------
    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.detect_pivots(dataframe, kernel=2)
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.label_structure(dataframe)

        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['trend_up'] = ((dataframe['close'] > dataframe['ema200']) & (dataframe['ema200'].diff() > 0)).astype(int)
        dataframe['trend_strength'] = (dataframe['adx'] > 25).astype(int)
        return dataframe

    # ---------------------------------------------------------
    # 15m — اندیکاتورها و مقدمات ورود
    # ---------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["vol_ma20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # BB برای ارزیابی شکست‌ها
        bb = ta.BBANDS(dataframe['close'], timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']

        dataframe = self.detect_pivots(dataframe, kernel=self.kernel)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.filter_pivots_distance(dataframe, min_distance=0.004)
        dataframe = self.label_structure(dataframe)

        # آخرین سطوح
        dataframe["last_sig_low"] = dataframe["sig_pivot_low_dist"].ffill()
        dataframe["last_sig_high"] = dataframe["sig_pivot_high_dist"].ffill()

        # محاسبه‌ی R:R هدف (Target ≈ 2.5×ATR تا 3×ATR)
        cost_buf = 0.0005
        dataframe["risk_base"] = (dataframe["close"] - dataframe["last_sig_low"]).clip(lower=1e-9)
        dataframe["reward_base"] = (2.7 * dataframe["ATR"] - cost_buf * dataframe["close"]).clip(lower=0)
        dataframe["rr_long"] = (dataframe["reward_base"] / dataframe["risk_base"]).where(
            (dataframe["reward_base"] > 0) & (dataframe["risk_base"] > 0)
        )

        for col in [
            "high_label", "low_label",
            "high_label_4h", "low_label_4h",
            "high_label_1h", "low_label_1h",
            "trend_up_1h", "trend_strength_1h",
            "sig_pivot_high_dist", "sig_pivot_low_dist",
            "last_sig_low", "last_sig_high",
            "rr_long", "vol_ma20", "bb_width", "bb_width_4h",
        ]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].ffill()

        return dataframe

    # ---------------------------------------------------------
    # Entry Logic — شکست معتبر + Retest برای استاپ کوچک
    # ---------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ساختارهای مولتی‌تایم‌فریم
        hl4 = dataframe["high_label_4h"].ffill()
        ll4 = dataframe["low_label_4h"].ffill()
        hl1 = dataframe["high_label_1h"].ffill()
        ll1 = dataframe["low_label_1h"].ffill()
        ll = dataframe["low_label"].ffill()

        # روند و قدرت
        trend_up = dataframe['trend_up_1h'].ffill()
        trend_str = dataframe['trend_strength_1h'].ffill()

        # سطوح و حجم
        lvl_high = dataframe["sig_pivot_high_dist"].ffill()
        vol_ma = dataframe["vol_ma20"].ffill()

        # شرایط شکست معتبر (دو کلوز + حجم)
        break_up = (
            (dataframe['close'] > lvl_high) &
            (dataframe['close'].shift(1) > lvl_high) &
            (dataframe['volume'] > vol_ma)
        )

        # Retest: برگشت قیمت به سطحِ شکست (برای استاپ نزدیک و منطقی)
        retest = (
            (dataframe['low'] <= lvl_high * 1.0005) &  # لمس سطح با کمی بافر
            (dataframe['close'] >= lvl_high)           # کلوز بالای سطح
        )

        # رژیم ولتیلیتی: BB در 4h خیلی بسته نباشد (شکست‌های کاذب کمتر)
        bb_ok = (dataframe.get('bb_width_4h', dataframe['bb_width']) > 0.02)

        long_cond = (
            (hl4 == "HH") & (ll4 == "HL") &
            (hl1 == "HH") & (ll1 == "HL") &
            (ll == "HL") &
            (trend_up == 1) & (trend_str == 1) &
            break_up & retest & bb_ok &
            (dataframe["rr_long"] >= 3.0)  # R:R بسیار بالا
        )

        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "break_retest_highRR"

        return dataframe

    # ---------------------------------------------------------
    # Exit Logic — مدیریت با استاپ داینامیک و ROI پله‌ای
    # ---------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # خروج‌ها با custom_stoploss مدیریت می‌شوند؛
        # در صورت نیاز می‌توان سیگنال‌های خروج اضافه کرد.
        return dataframe

    # ---------------------------------------------------------
    # Position Sizing — 0.5% از موجودی آزاد با توجه به ریسک واقعی
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
        last = dataframe.iloc[-1].squeeze()

        stop_level = float(last.get("last_sig_low", np.nan))
        try:
            free = float(self.wallets.get_free(pair=pair))
        except Exception:
            free = max_stake

        if np.isnan(stop_level) or stop_level == 0 or free <= 0:
            return float(min(proposed_stake, max_stake))

        risk = abs(stop_level / current_rate - 1)
        allowed_loss = free * self.trade_max_loss_allowed
        stake = allowed_loss / max(risk, 1e-9)

        return float(max(min(stake, free, max_stake), min_stake or 0.0))

    # ---------------------------------------------------------
    # Custom Stoploss — استاپ اولیه کوچک + تریلینگ پس از BE
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
        last = dataframe.iloc[-1].squeeze()

        raw_pivot = float(last.get("last_sig_low", np.nan))
        if np.isnan(raw_pivot):
            return 0.02  #fallback

        current_stop = trade.get_custom_data("stop")
        if current_stop is None:
            atr = float(last.get("ATR", np.nan))
            offset = (0.5 * atr) if not np.isnan(atr) else (current_rate * 0.003)  # کوچک اما منطقی

            # استاپ زیر سوئینگ لو + آفست
            stop = raw_pivot - offset
            trade.set_custom_data(key="stop", value=stop)

            init_risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data(key="risk", value=init_risk)

            current_stop = stop

        # تا قبل از BE + 0.4% تریل نکن
        be_threshold = 0.004
        if current_profit < be_threshold:
            final_stop = trade.get_custom_data("stop")
            return stoploss_from_absolute(
                final_stop,
                current_rate,
                is_short=False,
                leverage=trade.leverage,
            )

        # پس از BE: تریل روی max(EMA20, آخرین سوئینگ لو جدید) — محافظه‌کار
        ema20 = float(last.get("ema20", np.nan))
        trail_ref = raw_pivot
        if not np.isnan(ema20):
            trail_ref = max(trail_ref, ema20)

        if trail_ref > current_stop:
            trade.set_custom_data(key="stop", value=trail_ref)

        final_stop = trade.get_custom_data("stop")
        return stoploss_from_absolute(
            final_stop,
            current_rate,
            is_short=False,
            leverage=trade.leverage,
        )
