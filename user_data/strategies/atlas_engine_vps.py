import logging
from functools import reduce
import datetime
from datetime import timedelta
import talib.abstract as ta
from pandas import DataFrame, Series
from technical import qtpylib
from typing import Optional
from freqtrade.strategy.interface import IStrategy
from technical.pivots_points import pivots_points
from freqtrade.exchange import timeframe_to_prev_date
from freqtrade.persistence import Trade
from scipy.signal import argrelextrema
import numpy as np
import pandas_ta as pta
import math

logger = logging.getLogger(__name__)


class AtlasEngineVPS(IStrategy):
    """
    نسخه بهینه‌شده AtlasEngine برای VPS با ۴ گیگ رم
    هماهنگ با مدل XGBVPS و کانفیگ بهینه
    """
    
    # =========== تنظیمات پایه ===========
    timeframe = "15m"
    position_adjustment_enable = False
    stoploss = -0.035  # کاهش استاپ لاس برای ریسک کمتر
    can_short = True
    use_exit_signal = True
    process_only_new_candles = True
    startup_candle_count = 80  # هماهنگ با label_period_candles=40 * 2
    
    # =========== مدیریت سرمایه ===========
    max_open_trades = 2  # حداکثر ۲ معامله همزمان
    minimal_roi = {
        "0": 0.025,      # ۲.۵% سود => خروج
        "120": 0.015,    # بعد از ۲ ساعت => ۱.۵%
        "240": 0.01,     # بعد از ۴ ساعت => ۱%
        "480": -1        # بعد از ۸ ساعت => ضرر را قبول کن
    }
    
    # =========== انواع سفارش ===========
    order_types = {
        "entry": "limit",
        "exit": "market",
        "emergency_exit": "market",
        "force_exit": "market",
        "force_entry": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    
    # =========== نمودار ===========
    plot_config = {
        "subplots": {
            "extrema": {
                "&s-extrema": {"color": "#f53580", "type": "line"},
                "&s-minima_sort_threshold": {"color": "#f66151", "type": "line"},
                "&s-maxima_sort_threshold": {"color": "#8ff0a4", "type": "line"}
            },
            "range_est": {
                "&-s_max": {"color": "#a29db9", "type": "line"},
                "&-s_min": {"color": "#ac7fc", "type": "line"}
            }
        }
    }
    
    # =========== مهندسی ویژگی‌ها ===========
    
    def feature_engineering_expand_all(self, dataframe, period, **kwargs):
        """اندیکاتورهای پایه با پنجره‌های مختلف"""
        
        # مومنتوم
        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-cci-period"] = ta.CCI(dataframe, timeperiod=period)
        
        # روند
        dataframe["%-adx-period"] = ta.ADX(dataframe, window=period)
        
        # نوسان
        dataframe["%-atr-period"] = ta.ATR(dataframe, timeperiod=period)
        dataframe["%-atr-periodp"] = dataframe[f"%-atr-period"] / dataframe['close'] * 1000
        
        # حجم
        dataframe["%-cmf-period"] = self.chaikin_mf(dataframe, periods=period)
        
        # سایر
        dataframe["%-er-period"] = pta.er(dataframe['close'], length=period)
        dataframe["%-chop-period"] = qtpylib.chopiness(dataframe, period)
        
        return dataframe
    
    def feature_engineering_expand_basic(self, dataframe, **kwargs):
        """ویژگی‌های بدون پنجره زمانی"""
        
        # تغییرات قیمت
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        
        # باندهای بولینگر
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=14, stds=2.0)
        dataframe["%-bb_width"] = (bollinger["upper"] - bollinger["lower"]) / bollinger["mid"]
        dataframe["%-bb_position"] = (dataframe["close"] - bollinger["lower"]) / (bollinger["upper"] - bollinger["lower"])
        
        # اندیکاتورهای پایه
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['%-dist_ema20'] = (dataframe['close'] - dataframe['ema_20']) / dataframe['ema_20'] * 100
        dataframe['%-dist_ema50'] = (dataframe['close'] - dataframe['ema_50']) / dataframe['ema_50'] * 100
        
        # مکدی
        macd = ta.MACD(dataframe)
        dataframe['%-macd'] = macd['macd']
        dataframe['%-macdsignal'] = macd['macdsignal']
        dataframe['%-macdhist'] = macd['macdhist']
        
        # آی‌بی‌اس (Internal Bar Strength)
        dataframe["%-ibs"] = ((dataframe['close'] - dataframe['low']) / 
                              (dataframe['high'] - dataframe['low'])).fillna(0.5)
        
        # قیمت خام
        dataframe["%-raw_close"] = dataframe["close"]
        dataframe["%-raw_high"] = dataframe["high"]
        dataframe["%-raw_low"] = dataframe["low"]
        
        return dataframe
    
    def feature_engineering_standard(self, dataframe, **kwargs):
        """ویژگی‌های زمانی"""
        
        # سیکل روز/ساعت
        dataframe['hour_of_day'] = dataframe["date"].dt.hour
        dataframe['day_of_week'] = dataframe["date"].dt.dayofweek
        
        # تبدیل به سیکل مثلثاتی
        hour_norm = 2 * math.pi * dataframe['hour_of_day'] / 24
        day_norm = 2 * math.pi * dataframe['day_of_week'] / 7
        
        dataframe['%%-hour_sin'] = np.sin(hour_norm)
        dataframe['%%-hour_cos'] = np.cos(hour_norm)
        dataframe['%%-day_sin'] = np.sin(day_norm)
        dataframe['%%-day_cos'] = np.cos(day_norm)
        
        return dataframe
    
    # =========== تعریف هدف (Target) ===========
    
    def set_freqai_targets(self, dataframe, **kwargs):
        """پیش‌بینی نقاط افراطی (Extrema)"""
        
        kernel = self.freqai_info["feature_parameters"]["label_period_candles"]
        
        # پیدا کردن قله‌ها و دره‌ها
        dataframe["&s-extrema"] = 0
        min_peaks = argrelextrema(dataframe["low"].values, np.less, order=kernel)
        max_peaks = argrelextrema(dataframe["high"].values, np.greater, order=kernel)
        
        for mp in min_peaks[0]:
            dataframe.at[mp, "&s-extrema"] = -1
        for mp in max_peaks[0]:
            dataframe.at[mp, "&s-extrema"] = 1
        
        # هموارسازی با گاوسین
        dataframe['&s-extrema'] = dataframe['&s-extrema'].rolling(
            window=5, win_type='gaussian', center=True).mean(std=0.5)
        
        # پیش‌بینی محدوده قیمت (برای تعیین حد سود)
        dataframe['&-s_max'] = (dataframe["close"].shift(-kernel).rolling(kernel).max() / 
                               dataframe["close"] - 1) * 100
        dataframe['&-s_min'] = (dataframe["close"].shift(-kernel).rolling(kernel).min() / 
                               dataframe["close"] - 1) * 100
        
        return dataframe
    
    # =========== اندیکاتورهای نهایی ===========
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """اجرای FreqAI و محاسبه اندیکاتورهای نهایی"""
        
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # فیلتر پیش‌بینی‌های غیرمعمول
        if "DI_cutoff" in dataframe.columns:
            dataframe["DI_catch"] = np.where(
                dataframe["DI_values"] > dataframe["DI_cutoff"], 0, 1
            )
        else:
            dataframe["DI_catch"] = 1
        
        # آستانه‌های تطبیقی
        if "&s-maxima_sort_threshold" in dataframe.columns:
            dataframe["maxima_sort_threshold"] = dataframe["&s-maxima_sort_threshold"]
        else:
            dataframe["maxima_sort_threshold"] = 0.5
            
        if "&s-minima_sort_threshold" in dataframe.columns:
            dataframe["minima_sort_threshold"] = dataframe["&s-minima_sort_threshold"]
        else:
            dataframe["minima_sort_threshold"] = -0.5
        
        return dataframe
    
    # =========== سیگنال ورود ===========
    
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """تشکیل سیگنال‌های خرید و فروش"""
        
        # سیگنال خرید (Long)
        enter_long_conditions = [
            df["do_predict"] == 1,
            df["DI_catch"] == 1,
            df["&s-extrema"] < df["minima_sort_threshold"],
            df['&-s_max'] >= 1.5
        ]
        
        df.loc[
            reduce(lambda x, y: x & y, enter_long_conditions),
            ["enter_long", "enter_tag"]
        ] = (1, "long_extrema")
        
        # سیگنال فروش (Short)
        enter_short_conditions = [
            df["do_predict"] == 1,
            df["DI_catch"] == 1,
            df["&s-extrema"] > df["maxima_sort_threshold"],
            abs(df['&-s_min']) >= 1.5
        ]
        
        df.loc[
            reduce(lambda x, y: x & y, enter_short_conditions),
            ["enter_short", "enter_tag"]
        ] = (1, "short_extrema")
        
        return df
    
    # =========== خروج سفارشی ===========
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        """مدیریت هوشمند خروج از معامله"""
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # محافظت در برابر نوسانات شدید
        if current_profit < -0.03:  # ضرر ۳%
            return "emergency_stop_loss"
        
        # خروج بر اساس پیش‌بینی مدل
        if last_candle.get("DI_catch") == 0 and current_profit < 0:
            return "outlier_detected"
        
        # خروج در سود هدف
        trade_candle_idx = dataframe.index[
            dataframe["date"] == timeframe_to_prev_date(
                self.timeframe, trade.open_date_utc
            )
        ]
        
        if len(trade_candle_idx) > 0:
            trade_candle = dataframe.loc[trade_candle_idx[0]]
            
            if trade.enter_tag == "long_extrema":
                target_profit = trade_candle.get("&-s_max", 2.0) / 100
                if current_profit >= target_profit:
                    return "hit_target"
                    
            elif trade.enter_tag == "short_extrema":
                target_profit = abs(trade_candle.get("&-s_min", 2.0)) / 100
                if current_profit >= target_profit:
                    return "hit_target"
        
        # خروج زمانی
        trade_duration = (current_time - trade.open_date_utc).seconds / 3600
        if trade_duration > 12:  # ۱۲ ساعت
            return "time_exit"
        
        return None
    
    # =========== تأیید ورود ===========
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """بررسی نهایی قبل از ورود به معامله"""
        
        # محدودیت تعداد معاملات همزمان
        open_trades = Trade.get_trades(trade_filter=Trade.is_open.is_(True))
        num_shorts = sum(1 for t in open_trades if "short" in t.enter_tag)
        num_longs = sum(1 for t in open_trades if "long" in t.enter_tag)
        
        if side == "long" and num_longs >= 2:
            return False
        if side == "short" and num_shorts >= 2:
            return False
        
        # بررسی Slippage
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = df.iloc[-1].squeeze()
        
        if side == "long":
            if rate > last_candle["close"] * 1.002:  # ۰.۲٪ بالاتر
                return False
        else:
            if rate < last_candle["close"] * 0.998:  # ۰.۲٪ پایین‌تر
                return False
        
        return True
    
    # =========== توابع کمکی ===========
    
    @staticmethod
    def chaikin_mf(df, periods=20):
        """Chaikin Money Flow"""
        close = df['close']
        low = df['low']
        high = df['high']
        volume = df['volume']
        
        mfv = ((close - low) - (high - close)) / (high - low)
        mfv = mfv.fillna(0.0)
        mfv *= volume
        cmf = mfv.rolling(periods).sum() / volume.rolling(periods).sum()
        
        return Series(cmf, name='cmf')
    
    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """الزامی توسط FreqAI"""
        return df