import logging
from typing import Dict, Optional
import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib
from datetime import datetime
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade
from freqtrade.strategy import stoploss_from_open

logger = logging.getLogger(__name__)


class AtlasEngine(IStrategy):
    
    
    # ✅ تایم‌فریم 15m - بهترین تعادل بین دقت و مصرف RAM
    timeframe = '15m'
    
    # ✅ محدودیت هوشمند معاملات
    max_open_trades = 3
    process_only_new_candles = True
    use_exit_signal = True
    use_custom_stoploss = True
    can_short = True
    
    # ✅ استاپ لاس محافظه‌کارانه
    stoploss = -0.03
    trailing_stop = False
    
    # ✅ ROI پویا و واقع‌بینانه
    minimal_roi = {
        "120": 0.02,   # ۲ ساعت: ۲٪ سود کافی است
        "60": 0.025,   # ۱ ساعت: ۲.۵٪ سود
        "30": 0.03,    # ۳۰ دقیقه: ۳٪ سود
        "15": 0.035,   # ۱۵ دقیقه: ۳.۵٪ سود
        "0": 0.04      # بلافاصله: ۴٪ سود
    }
    
    
    # آستانه پیش‌بینی سود
    min_predicted_return = DecimalParameter(0.01, 0.02, default=0.012, space='buy')
    
    # حداقل ریوارد به ریسک
    min_risk_reward = DecimalParameter(1.6, 2.2, default=1.8, space='buy')
    
    # آستانه اطمینان مدل
    min_confidence = DecimalParameter(0.55, 0.75, default=0.65, space='buy')
    
    # فیلترهای RSI
    buy_rsi_min = IntParameter(35, 45, default=40, space='buy')
    buy_rsi_max = IntParameter(60, 70, default=65, space='buy')
    sell_rsi_min = IntParameter(35, 45, default=40, space='sell')
    sell_rsi_max = IntParameter(60, 70, default=65, space='sell')
    
    # فیلتر حجم
    min_volume_ratio = DecimalParameter(0.8, 1.2, default=0.9, space='buy')
    
    # فیلتر نوسان
    max_atr_pct = DecimalParameter(0.035, 0.05, default=0.04, space='buy')
    
    # استاپ لاس
    atr_stop_multiplier = DecimalParameter(1.8, 2.2, default=2.0, space='sell')
    trail_profit_start = DecimalParameter(0.015, 0.025, default=0.02, space='sell')
    trail_percent = DecimalParameter(0.5, 0.7, default=0.6, space='sell')
    
    # =====================================================================
    # Feature Engineering - فقط ویژگی‌های حیاتی (۲۸ ویژگی)
    # =====================================================================
    
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: Dict, **kwargs) -> DataFrame:
        """
        🎯 ۷ نوع ویژگی در ۴ دوره = ۲۸ ویژگی (عالی برای VPS 4GB)
        """
        
        # ================ 1. روند (Trend) ================
        ema = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-trend-ema-{period}"] = ema
        dataframe[f"%-trend-ema-dist-{period}"] = (dataframe['close'] - ema) / ema
        
        # ================ 2. مومنتوم (Momentum) ================
        dataframe[f"%-mom-rsi-{period}"] = ta.RSI(dataframe, timeperiod=period) / 100
        dataframe[f"%-mom-roc-{period}"] = ta.ROC(dataframe, timeperiod=period) / 100
        
        # ================ 3. نوسان (Volatility) ================
        atr = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-vol-atr-{period}"] = atr
        dataframe[f"%-vol-atr-pct-{period}"] = atr / dataframe['close']
        
        # ================ 4. حجم (Volume) ================
        volume_ma = dataframe['volume'].rolling(period).mean()
        dataframe[f"%-vol-ratio-{period}"] = dataframe['volume'] / volume_ma
        
        # ================ 5. قدرت (Strength) ================
        dataframe[f"%-str-adx-{period}"] = ta.ADX(dataframe, timeperiod=period) / 100
        
        # ================ 6. بازده (Returns) ================
        dataframe[f"%-ret-{period}"] = dataframe['close'].pct_change(period)
        
        # ================ 7. باند بولینگر (BB) ================
        bb = qtpylib.bollinger_bands(dataframe['close'], window=period, stds=2)
        dataframe[f"%-bb-width-{period}"] = (bb['upper'] - bb['lower']) / bb['mid']
        dataframe[f"%-bb-pos-{period}"] = (dataframe['close'] - bb['lower']) / (bb['upper'] - bb['lower'])
        
        return dataframe
    
    def feature_engineering_expand_basic(self, dataframe: DataFrame,
                                         metadata: Dict, **kwargs) -> DataFrame:
        """ویژگی‌های پایه - حداقل ممکن"""
        dataframe['%-ret-1'] = dataframe['close'].pct_change(1)
        dataframe['%-ret-3'] = dataframe['close'].pct_change(3)
        dataframe['%-hl-ratio'] = dataframe['high'] / dataframe['low']
        return dataframe
    
    def feature_engineering_standard(self, dataframe: DataFrame,
                                     metadata: Dict, **kwargs) -> DataFrame:
        """ویژگی‌های زمانی - فقط ضروری"""
        dataframe['%-hour'] = dataframe['date'].dt.hour
        dataframe['%-day'] = dataframe['date'].dt.dayofweek
        # ✅ تعطیلات آخر هفته - سود بیشتر!
        dataframe['%-is_weekend'] = dataframe['date'].dt.dayofweek.apply(
            lambda x: 0 if x >= 5 else 1
        )
        return dataframe
    
    # =====================================================================
    # تعریف تارگت - رگرسیون برای پیش‌بینی دقیق
    # =====================================================================
    
    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:
        """
        🎯 تارگت رگرسیون - پیش‌بینی بازده ۵ کندل آینده
        """
        # بازده ۵ کندل آینده (۷۵ دقیقه)
        target = dataframe['close'].pct_change(5).shift(-5)
        
        # محدود کردن مقادیر پرت (winsorization)
        upper = target.quantile(0.98)
        lower = target.quantile(0.02)
        target = target.clip(lower, upper)
        
        dataframe['&-target_return'] = target
        return dataframe
    
    # =====================================================================
    # Populate Indicators
    # =====================================================================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """اندیکاتورهای کلاسیک برای تأیید"""
        
        # 1. فراخوانی FreqAI
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 2. EMA برای روند
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        
        # 3. ATR برای استاپ
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        
        # 4. RSI برای تأیید
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # 5. حجم
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        return dataframe
    
    # =====================================================================
    # سیگنال ورود - محافظه‌کارانه اما نه خفه‌کننده
    # =====================================================================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        🟢 فلسفه ۱۰٪ ماهانه:
        - نه آنقدر سخت که هیچ معامله‌ای نکنی
        - نه آنقدر آسان که همه معاملات ضرر کنن
        """
        
        # ================ شرایط پایه ================
        base_conditions = (
            # 1. مدل اطمینان داره
            (dataframe['do_predict'] == 1) &
            # 2. حجم منطقی
            (dataframe['volume_ratio'] > self.min_volume_ratio.value) &
            # 3. نوسان کنترل شده
            (dataframe['atr_pct'] < self.max_atr_pct.value) &
            # 4. آخر هفته نیست
            (dataframe['%-is_weekend'] == 1)
        )
        
        # ================ شرایط لانگ ================
        long_conditions = base_conditions & (
            # 1. پیش‌بینی سود مثبت
            (dataframe['&-target_return'] > self.min_predicted_return.value) &
            # 2. ریوارد به ریسک مناسب
            ((dataframe['&-target_return'] / dataframe['atr_pct']) > self.min_risk_reward.value) &
            # 3. RSI مناسب
            (dataframe['rsi'] > self.buy_rsi_min.value) &
            (dataframe['rsi'] < self.buy_rsi_max.value) &
            # 4. روند صعودی ملایم
            (dataframe['ema_20'] > dataframe['ema_50'])
        )
        
        # ================ شرایط شورت ================
        short_conditions = base_conditions & (
            (dataframe['&-target_return'] < -self.min_predicted_return.value) &
            ((abs(dataframe['&-target_return']) / dataframe['atr_pct']) > self.min_risk_reward.value) &
            (dataframe['rsi'] > self.sell_rsi_min.value) &
            (dataframe['rsi'] < self.sell_rsi_max.value) &
            (dataframe['ema_20'] < dataframe['ema_50'])
        )
        
        dataframe.loc[long_conditions, 'enter_long'] = 1
        dataframe.loc[long_conditions, 'enter_tag'] = 'guardian_long'
        
        dataframe.loc[short_conditions, 'enter_short'] = 1
        dataframe.loc[short_conditions, 'enter_tag'] = 'guardian_short'
        
        return dataframe
    
    # =====================================================================
    # سیگنال خروج - سریع و قاطع
    # =====================================================================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """🔴 خروج هوشمند - حفظ سود"""
        
        # خروج از لانگ
        exit_long = (
            (dataframe['&-target_return'] < 0) |  # پیش‌بینی منفی
            (dataframe['rsi'] > 75) |            # اشباع خرید
            (dataframe['ema_20'] < dataframe['ema_50'])  # روند ضعیف
        )
        
        # خروج از شورت
        exit_short = (
            (dataframe['&-target_return'] > 0) |
            (dataframe['rsi'] < 25) |
            (dataframe['ema_20'] > dataframe['ema_50'])
        )
        
        dataframe.loc[exit_long, 'exit_long'] = 1
        dataframe.loc[exit_short, 'exit_short'] = 1
        
        return dataframe
    
    
    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        """
        🛑 استاپ لاس ۲ لایه:
        لایه 1: استاپ فیزیکی بر اساس ATR
        لایه 2: تریلینگ در سود
        """
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return -0.03
        
        last_candle = dataframe.iloc[-1]
        atr_pct = last_candle['atr_pct']
        
        # استاپ پایه
        initial_stop = atr_pct * self.atr_stop_multiplier.value
        
        # تریلینگ در سود
        if current_profit > self.trail_profit_start.value:
            if current_profit > 0.04:
                trail = 0.5
            elif current_profit > 0.03:
                trail = 0.55
            else:
                trail = self.trail_percent.value
            
            trailing_stop = stoploss_from_open(current_profit * (1 - trail), current_profit)
            return max(trailing_stop, -initial_stop)
        
        return -initial_stop
    
    
    def confirm_trade_entry(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: float, max_stake: float,
                            leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        ✅ تأیید نهایی - فقط معاملات با کیفیت
        """
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) < 10:
            return False
        
        last_candle = dataframe.iloc[-1]
        
        # 1. بررسی پیش‌بینی
        pred = last_candle['&-target_return']
        if side == 'long' and pred < 0:
            return False
        if side == 'short' and pred > 0:
            return False
        
        # 2. بررسی ریوارد به ریسک
        rr = abs(pred) / last_candle['atr_pct']
        if rr < self.min_risk_reward.value:
            return False
        
        # 3. بررسی نوسان لحظه‌ای
        if last_candle['atr_pct'] > 0.06:
            return False
        
        logger.info(f"✅ {pair}: ورود تأیید شد | RR: {rr:.2f} | Pred: {pred:.2%}")
        return True
    