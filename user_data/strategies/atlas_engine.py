# -*- coding: utf-8 -*-
# AtlasEngine v2 - نسخه اصلاح‌شده برای پایداری بلندمدت
# تغییرات کلیدی:
# - فیلتر روند و قدرت بازار (EMA200 + ADX در 1h)
# - شکست معتبر: دو کلوز متوالی با حجم بالاتر از میانگین
# - R:R واقع‌گرایانه مبتنی بر ATR + بافر هزینه/اسلیپیج
# - استاپ‌لاس: اولیه + فعال‌سازی تریلینگ پس از رسیدن به Break-Even
# - سایز پوزیشن بر اساس موجودی آزاد حساب و ریسک واقعی هر معامله
#
# نکته: ساختار Pivot/Label از نسخه‌ی شما حفظ شده و بهینه‌سازی شده است.

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

    # تنظیمات عمومی
    timeframe = '15m'
    can_short: bool = True
    process_only_new_candles = True
    use_exit_signal = True
    use_custom_stoploss = True

    # هسته‌ی رفتار
    kernel = 2  # حساسیت Pivot

    # مدیریت ریسک کلان
    stoploss = -1  # توسط custom_stoploss مدیریت می‌شود
    # حداکثر ضرر مجاز روی موجودی آزاد حساب در هر معامله (۰.۵٪)
    trade_max_loss_allowed = 0.005

    # نوع سفارش‌ها
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }

    startup_candle_count = 200

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

        # فقط پِیوت‌هایی که فاصله‌شان از پِیوت قبلی > ATR*mult باشد
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
        # فاصله‌ی حداقل 0.3% نسبت به قیمت برای معتبرسازی سطح
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
    # Informative 4H (ساختار و پیوت‌ها)
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
    # Informative 1H (ساختار + فیلتر روند و قدرت)
    # ---------------------------------------------------------
    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.detect_pivots(dataframe, kernel=2)
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.label_structure(dataframe)

        # فیلتر روند و قدرت
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['trend_up'] = ((dataframe['close'] > dataframe['ema200']) & (dataframe['ema200'].diff() > 0)).astype(int)
        dataframe['trend_down'] = ((dataframe['close'] < dataframe['ema200']) & (dataframe['ema200'].diff() < 0)).astype(int)
        dataframe['trend_strength'] = (dataframe['adx'] > 20).astype(int)
        return dataframe

    # ---------------------------------------------------------
    # Main timeframe (15m)
    # ---------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ATR و EMA20 و میانگین حجم
        dataframe["ATR"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["vol_ma20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Pivot + ATR + Distance + Structure (هم‌راستا با 4h/1h)
        dataframe = self.detect_pivots(dataframe, kernel=self.kernel)
        dataframe = self.filter_pivots_atr(dataframe, atr_mult=1.0)
        dataframe = self.filter_pivots_distance(dataframe, min_distance=0.003)
        dataframe = self.label_structure(dataframe)

        # آخرین pivot مهم LTF (برای استاپ و R:R)
        dataframe["last_sig_low"] = dataframe["sig_pivot_low_dist"].ffill()
        dataframe["last_sig_high"] = dataframe["sig_pivot_high_dist"].ffill()

        # هدف‌ها مبتنی بر پیوت‌های 4h (اگر در سمت درست باشند)
        dataframe["tgt_long"]  = dataframe["sig_pivot_high_dist_4h"].where(
            dataframe["sig_pivot_high_dist_4h"] > dataframe["close"]
        ).ffill()
        dataframe["tgt_short"] = dataframe["sig_pivot_low_dist_4h"].where(
            dataframe["sig_pivot_low_dist_4h"] < dataframe["close"]
        ).ffill()

        # R:R واقع‌گرایانه (جایگزین محاسبه‌ی خوش‌بینانه)
        cost_buf = 0.0005  # 0.05% برای کارمزد/اسلیپیج
        reward_long = 1.8 * dataframe["ATR"] - cost_buf * dataframe["close"]
        risk_long = (dataframe["close"] - dataframe["last_sig_low"]).clip(lower=1e-9)
        dataframe["rr_long"] = (reward_long / risk_long).where((reward_long > 0) & (risk_long > 0))

        reward_short = 1.8 * dataframe["ATR"] - cost_buf * dataframe["close"]
        risk_short = (dataframe["last_sig_high"] - dataframe["close"]).clip(lower=1e-9)
        dataframe["rr_short"] = (reward_short / risk_short).where((reward_short > 0) & (risk_short > 0))

        # ffill ایمن برای ستون‌هایی که استفاده می‌کنیم
        ffill_cols = [
            "high_label", "low_label",
            "high_label_4h", "low_label_4h",
            "high_label_1h", "low_label_1h",
            "trend_up_1h", "trend_down_1h", "trend_strength_1h",
            "sig_pivot_high_dist", "sig_pivot_low_dist",
            "last_sig_low", "last_sig_high",
            "rr_long", "rr_short",
            "vol_ma20",
        ]
        for col in ffill_cols:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].ffill()

        return dataframe

    # ---------------------------------------------------------
    # Entry Logic (با شکست معتبر دوکلوزی + حجم)
    # ---------------------------------------------------------
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ساختارهای مولتی‌تایم‌فریم
        hl4 = dataframe["high_label_4h"].ffill()
        ll4 = dataframe["low_label_4h"].ffill()
        hl1 = dataframe["high_label_1h"].ffill()
        ll1 = dataframe["low_label_1h"].ffill()
        lh = dataframe["high_label"].ffill()
        ll = dataframe["low_label"].ffill()

        # فیلتر روند و قدرت (1h)
        trend_up = dataframe['trend_up_1h'].ffill()
        trend_dn = dataframe['trend_down_1h'].ffill()
        trend_str = dataframe['trend_strength_1h'].ffill()

        # سطوح پِیوت و میانگین حجم
        lvl_high = dataframe["sig_pivot_high_dist"].ffill()
        lvl_low = dataframe["sig_pivot_low_dist"].ffill()
        vol_ma = dataframe["vol_ma20"].ffill()

        # شکست معتبر: دو کلوز متوالی + حجم بالاتر از میانگین
        break_up = (
            (dataframe['close'] > lvl_high) &
            (dataframe['close'].shift(1) > lvl_high) &
            (dataframe['volume'] > vol_ma)
        )

        break_dn = (
            (dataframe['close'] < lvl_low) &
            (dataframe['close'].shift(1) < lvl_low) &
            (dataframe['volume'] > vol_ma)
        )

        # -------------------------
        # LONG ENTRY
        # -------------------------
        long_cond = (
            (hl4 == "HH") & (ll4 == "HL") &        # Guard 4h
            (hl1 == "HH") & (ll1 == "HL") &        # Guard 1h
            (ll == "HL") &                         # Guard LTF
            (trend_up == 1) & (trend_str == 1) &   # روند و قدرت
            break_up &                             # شکست معتبر
            (dataframe["rr_long"] >= 1.8)          # R:R واقع‌گرایانه
        )

        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "break_up_pivot"

        # -------------------------
        # SHORT ENTRY
        # -------------------------
        short_cond = (
            (hl4 == "LH") & (ll4 == "LL") &        # Guard 4h
            (hl1 == "LH") & (ll1 == "LL") &        # Guard 1h
            (lh == "LH") &                         # Guard LTF
            (trend_dn == 1) & (trend_str == 1) &   # روند و قدرت
            break_dn &                             # شکست معتبر
            (dataframe["rr_short"] >= 1.8)         # R:R واقع‌گرایانه
        )

        dataframe.loc[short_cond, "enter_short"] = 1
        dataframe.loc[short_cond, "enter_tag"] = "break_dn_pivot"

        return dataframe

    # ---------------------------------------------------------
    # Exit Logic (فعلاً خالی؛ خروج‌ها با استاپ داینامیک مدیریت می‌شوند)
    # ---------------------------------------------------------
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    # ---------------------------------------------------------
    # Position Sizing بر اساس ریسک واقعی و موجودی آزاد
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

        # دریافت آخرین کندل برای برآورد استاپ
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # تعیین سطح استاپ بر اساس آخرین پِیوت معتبر
        if side == "short":
            stop = float(last_candle.get("last_sig_high", np.nan))
        else:
            stop = float(last_candle.get("last_sig_low", np.nan))

        # موجودی آزاد
        try:
            free = float(self.wallets.get_free(pair=pair))
        except Exception:
            free = max_stake

        if np.isnan(stop) or stop == 0 or free <= 0:
            return float(min(proposed_stake, max_stake))

        risk = abs(stop / current_rate - 1)
        allowed_loss = free * self.trade_max_loss_allowed  # 0.5% از موجودی آزاد
        stake = allowed_loss / max(risk, 1e-9)

        # محدودسازی منطقی
        stake = float(max(min(stake, free, max_stake), min_stake or 0.0))
        return stake

    # ---------------------------------------------------------
    # Dynamic Stoploss (initial + trailing پس از BE)
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
            raw_pivot = float(last_candle.get("last_sig_high", np.nan))
        else:
            raw_pivot = float(last_candle.get("last_sig_low", np.nan))

        # اگر pivot نداریم، fallback
        if np.isnan(raw_pivot):
            return 0.02  # 2% fallback

        # استاپ اولیه فقط یک‌بار تنظیم می‌شود
        current_stop = trade.get_custom_data("stop")
        if current_stop is None:
            # offset بر اساس ATR یا حداقل 0.2% قیمت
            atr = float(last_candle.get("ATR", np.nan))
            offset = (0.3 * atr) if not np.isnan(atr) else (current_rate * 0.002)

            direction = 1 if trade.is_short else -1
            stop = raw_pivot + direction * offset

            trade.set_custom_data(key="stop", value=stop)

            # ریسک اولیه صرفاً برای اطلاع
            init_risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data(key="risk", value=init_risk)

            # بازگشت نسبت به قیمت فعلی
            current_stop = stop

        # تا قبل از رسیدن به BE + 0.3%، تریل نکن
        be_threshold = 0.003  # 0.3%
        if current_profit < be_threshold:
            final_stop = trade.get_custom_data("stop")
            return stoploss_from_absolute(
                final_stop,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage,
            )

        # پس از BE، تریل روی پِیوت جدید یا EMA20 (هرکدام محافظه‌کارتر است)
        ema20 = float(last_candle.get("ema20", np.nan))

        if trade.is_short:
            # در شورت، استاپ باید پایین‌تر بیاید (به نفع ما)
            trail_ref = raw_pivot
            if not np.isnan(ema20):
                trail_ref = min(trail_ref, ema20)
            if trail_ref < current_stop:
                trade.set_custom_data(key="stop", value=trail_ref)
        else:
            # در لانگ، استاپ باید بالاتر برود (به نفع ما)
            trail_ref = raw_pivot
            if not np.isnan(ema20):
                trail_ref = max(trail_ref, ema20)
            if trail_ref > current_stop:
                trade.set_custom_data(key="stop", value=trail_ref)

        final_stop = trade.get_custom_data("stop")

        return stoploss_from_absolute(
            final_stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
