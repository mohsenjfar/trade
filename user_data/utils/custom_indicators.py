"""
ماژول اندیکاتورهای تخصصی برای معاملات رمزارز
ویژگی‌ها: اندیکاتورهای آنچین، CVD, MVRV, Dominance, و ...
"""

import numpy as np
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class CustomIndicators:
    """
    کلاس اندیکاتورهای تخصصی رمزارز
    
    این کلاس شامل اندیکاتورهایی است که مخصوص بازار کریپتوکارنسی طراحی شده‌اند:
    - CVD (Cumulative Volume Delta)
    - MVRV (Market Value to Realized Value)
    - NUPL (Net Unrealized Profit/Loss)
    - Puell Multiple
    - BTC Dominance Analysis
    - Session-based Volatility
    - Whale Detection
    - Market Regime Detection
    - Dynamic Support/Resistance
    - ATR-based Stop Loss
    """
    
    def __init__(self, 
                 btc_dominance_pair: str = "BTC.D",
                 use_onchain_data: bool = False,
                 onchain_api_key: Optional[str] = None):
        """
        Args:
            btc_dominance_pair: جفت‌ارز نمایش‌دهنده dominance
            use_onchain_data: آیا از داده‌های آنچین استفاده شود
            onchain_api_key: API key برای سرویس‌های آنچین
        """
        self.btc_dominance_pair = btc_dominance_pair
        self.use_onchain_data = use_onchain_data
        self.onchain_api_key = onchain_api_key
        self._cache = {}
        
    # =========================================================================
    # 1. اندیکاتورهای حجم و فشار خرید/فروش
    # =========================================================================
    
    def add_cvd(self, dataframe: DataFrame, period: int = 20) -> DataFrame:
        """
        Cumulative Volume Delta - فشار خرید/فروش تجمعی
        
        CVD نشان می‌دهد که در طول زمان، فشار خرید بیشتر بوده یا فروش
        افزایش CVD صعودی = قدرت خریداران
        واگرایی CVD با قیمت = سیگنال برگشت
        """
        df = dataframe.copy()
        
        # محاسبه دلتای هر کندل
        df['cvd_raw'] = (df['close'] - df['open']) * df['volume']
        
        # CVD تجمعی
        df['cvd'] = df['cvd_raw'].cumsum()
        
        # میانگین متحرک CVD
        df['cvd_ema'] = ta.EMA(df['cvd'], timeperiod=period)
        df['cvd_sma'] = ta.SMA(df['cvd'], timeperiod=period)
        
        # مشتق CVD (سرعت تغییر)
        df['cvd_slope'] = np.gradient(df['cvd_ema'])
        df['cvd_acceleration'] = np.gradient(df['cvd_slope'])
        
        # واگرایی CVD و قیمت
        df['cvd_divergence'] = df['close'] - df['cvd_ema']
        df['cvd_divergence_pct'] = (df['cvd_divergence'] / df['cvd_ema']) * 100
        
        # سیگنال‌ها
        df['cvd_buy_signal'] = (
            (qtpylib.crossed_above(df['cvd'], df['cvd_ema'])) & 
            (df['cvd_slope'] > 0)
        ).astype(int)
        
        df['cvd_sell_signal'] = (
            (qtpylib.crossed_below(df['cvd'], df['cvd_ema'])) & 
            (df['cvd_slope'] < 0)
        ).astype(int)
        
        # نرمالایز شده CVD (0-100)
        if len(df) > 20:
            min_cvd = df['cvd'].rolling(20).min()
            max_cvd = df['cvd'].rolling(20).max()
            df['cvd_normalized'] = 100 * (df['cvd'] - min_cvd) / (max_cvd - min_cvd)
        
        return df
    
    # =========================================================================
    # 2. اندیکاتورهای ATR و استاپ لاس
    # =========================================================================
    
    def add_atr_stop_levels(self, 
                           dataframe: DataFrame, 
                           period: int = 14,
                           long_multiplier: float = 1.5,
                           short_multiplier: float = 1.5) -> DataFrame:
        """
        محاسبه سطوح استاپ داینامیک بر اساس ATR
        """
        df = dataframe.copy()
        
        # ATR استاندارد
        df['atr'] = ta.ATR(df, timeperiod=period)
        df['atr_pct'] = df['atr'] / df['close'] * 100
        
        # نوسان بر اساس سشن
        if isinstance(df.index, pd.DatetimeIndex):
            df['hour'] = df.index.hour
        else:
            df['hour'] = range(len(df))
        
        # محاسبه ضرایب نوسان سشن
        session_vol = {
            'asia': df[df['hour'].between(0, 7)]['atr_pct'].mean() if len(df) > 0 else 1,
            'london': df[df['hour'].between(8, 15)]['atr_pct'].mean() if len(df) > 0 else 1,
            'ny': df[df['hour'].between(16, 23)]['atr_pct'].mean() if len(df) > 0 else 1
        }
        
        # ضریب تعدیل سشن
        df['session'] = df['hour'].apply(
            lambda x: 'ny' if 16 <= x <= 23 else ('london' if 8 <= x <= 15 else 'asia')
        )
        df['vol_multiplier'] = df['session'].map(
            lambda s: session_vol.get(s, 1) / session_vol.get('london', 1)
        )
        
        # ATR تعدیل شده بر اساس سشن
        df['atr_adjusted'] = df['atr'] * df['vol_multiplier']
        
        # سطوح استاپ داینامیک
        df['long_stop_price'] = df['close'] - (df['atr_adjusted'] * long_multiplier)
        df['short_stop_price'] = df['close'] + (df['atr_adjusted'] * short_multiplier)
        
        # سطوح تریلینگ استاپ
        df['trailing_stop_long'] = df['close'].rolling(window=20).max() - (df['atr_adjusted'] * 2)
        df['trailing_stop_short'] = df['close'].rolling(window=20).min() + (df['atr_adjusted'] * 2)
        
        # رژیم نوسان
        df['volatility_regime'] = 'normal'
        df.loc[df['atr_pct'] > df['atr_pct'].rolling(50).mean() * 1.5, 'volatility_regime'] = 'high'
        df.loc[df['atr_pct'] < df['atr_pct'].rolling(50).mean() * 0.5, 'volatility_regime'] = 'low'
        
        return df
    
    def calculate_dynamic_stop(self,
                              dataframe: DataFrame,
                              entry_price: float,
                              side: str,
                              current_profit: float = 0) -> float:
        """
        محاسبه استاپ داینامیک بر اساس ATR و شرایط بازار
        """
        if len(dataframe) == 0:
            return entry_price * (0.95 if side == 'long' else 1.05)
        
        last_candle = dataframe.iloc[-1]
        atr = last_candle.get('atr_adjusted', last_candle.get('atr', entry_price * 0.02))
        
        # فاصله پایه استاپ
        if side == 'long':
            base_stop = entry_price - (atr * 1.5)
        else:
            base_stop = entry_price + (atr * 1.5)
        
        # تعدیل استاپ بر اساس سود
        if current_profit > 0:
            if side == 'long':
                trail_stop = max(
                    base_stop,
                    entry_price * (1 + current_profit * 0.5)
                )
            else:
                trail_stop = min(
                    base_stop,
                    entry_price * (1 - current_profit * 0.5)
                )
            return trail_stop
        
        # تعدیل استاپ بر اساس رژیم نوسان
        volatility_regime = last_candle.get('volatility_regime', 'normal')
        if volatility_regime == 'high':
            if side == 'long':
                return entry_price - (atr * 2.0)
            else:
                return entry_price + (atr * 2.0)
        elif volatility_regime == 'low':
            if side == 'long':
                return entry_price - (atr * 1.0)
            else:
                return entry_price + (atr * 1.0)
        
        return base_stop
    
    # =========================================================================
    # 3. اندیکاتورهای مخصوص بیت‌کوین و آلتکوین‌ها
    # =========================================================================
    
    def add_mvrv(self, dataframe: DataFrame, pair: str) -> DataFrame:
        """
        MVRV Ratio - نسبت ارزش بازار به ارزش تحققیافته
        """
        df = dataframe.copy()
        
        if "BTC" in pair:
            # تخمین قیمت تحققیافته با میانگین متحرک 200 هفته‌ای
            df['realized_price'] = ta.WMA(df['close'], timeperiod=200)
            
            # MVRV Ratio
            df['mvrv_ratio'] = df['close'] / df['realized_price']
            
            # MVRV Z-Score
            mvrv_mean = df['mvrv_ratio'].rolling(200).mean()
            mvrv_std = df['mvrv_ratio'].rolling(200).std()
            df['mvrv_zscore'] = (df['mvrv_ratio'] - mvrv_mean) / mvrv_std
            
            # مناطق خرید/فروش
            df['mvrv_oversold'] = (df['mvrv_ratio'] < 0.9).astype(int)
            df['mvrv_overbought'] = (df['mvrv_ratio'] > 2.5).astype(int)
            df['mvrv_extreme'] = (df['mvrv_ratio'] > 3.5).astype(int)
            
            # سیگنال
            df['mvrv_buy_zone'] = ((df['mvrv_ratio'] < 1) & (df['mvrv_zscore'] < -1)).astype(int)
            df['mvrv_sell_zone'] = ((df['mvrv_ratio'] > 2.5) & (df['mvrv_zscore'] > 1.5)).astype(int)
            
        return df
    
    def add_nupl(self, dataframe: DataFrame) -> DataFrame:
        """
        NUPL - سود/زیان تحقق‌نیافته خالص
        """
        df = dataframe.copy()
        
        # تخمین سود/زیان تحقق‌نیافته
        df['avg_entry'] = ta.EMA(df['close'], timeperiod=150)
        df['unrealized_pnl'] = (df['close'] - df['avg_entry']) / df['avg_entry']
        
        # NUPL
        df['nupl'] = df['unrealized_pnl'].clip(-1, 1)
        
        # فازهای احساسات
        conditions = [
            (df['nupl'] >= 0.75),
            (df['nupl'] >= 0.5) & (df['nupl'] < 0.75),
            (df['nupl'] >= 0.25) & (df['nupl'] < 0.5),
            (df['nupl'] >= 0) & (df['nupl'] < 0.25),
            (df['nupl'] < 0)
        ]
        choices = ['euphoria', 'belief', 'optimism', 'hope', 'capitulation']
        df['market_phase'] = np.select(conditions, choices, default='neutral')
        
        return df
    
    def add_puell_multiple(self, dataframe: DataFrame) -> DataFrame:
        """
        Puell Multiple - نسبت ارزش کوین‌های استخراج شده به میانگین 365 روزه
        """
        df = dataframe.copy()
        
        # شبیه‌سازی ارزش کوین‌های استخراج شده
        df['mining_revenue'] = df['volume'] * 0.01  # تخمین
        
        df['puell'] = df['mining_revenue'] / df['mining_revenue'].rolling(365).mean()
        df['puell_buy'] = (df['puell'] < 0.5).astype(int)
        df['puell_sell'] = (df['puell'] > 4).astype(int)
        
        return df
    
    # =========================================================================
    # 4. اندیکاتورهای Dominance و همبستگی
    # =========================================================================
    
    def add_btc_dominance_impact(self, 
                                  alt_dataframe: DataFrame, 
                                  btc_dom_dataframe: DataFrame) -> DataFrame:
        """
        تحلیل تاثیر Dominance بیت‌کوین بر آلتکوین
        """
        df = alt_dataframe.copy()
        
        # اطمینان از هم‌اندازه بودن دیتافریم‌ها
        min_length = min(len(df), len(btc_dom_dataframe))
        df = df.iloc[-min_length:].copy()
        btc_dom = btc_dom_dataframe.iloc[-min_length:].copy()
        
        # روند Dominance
        df['btc_dom'] = btc_dom['close'].values
        df['btc_dom_ema'] = ta.EMA(df['btc_dom'], timeperiod=50)
        df['btc_dom_slope'] = np.gradient(df['btc_dom_ema'])
        df['btc_dom_trend'] = np.where(df['btc_dom_slope'] > 0, 'up', 'down')
        
        # همبستگی متحرک
        df['btc_correlation'] = df['close'].rolling(24).corr(btc_dom['close'])
        
        # فازهای آلت سیزن
        df['alt_season'] = (
            (df['btc_dom_slope'] < 0) & 
            (df['btc_dom'] < df['btc_dom_ema'])
        ).astype(int)
        
        return df
    
    # =========================================================================
    # 5. اندیکاتورهای نوسان و ریسک
    # =========================================================================
    
    def add_crypto_volatility(self, 
                              dataframe: DataFrame, 
                              pair: str = None) -> DataFrame:
        """
        اندازه‌گیری نوسان ویژه کریپتو
        """
        df = dataframe.copy()
        
        # ATR استاندارد
        df['atr'] = ta.ATR(df, timeperiod=14)
        df['atr_pct'] = df['atr'] / df['close'] * 100
        
        # نوسان تاریخی
        df['historical_vol'] = df['close'].pct_change().rolling(24).std() * np.sqrt(365)
        
        # نوسان بر اساس سشن
        df['hour'] = pd.to_datetime(df.index).hour if isinstance(df.index, pd.DatetimeIndex) else range(len(df))
        
        session_vol = {
            'asia': df[df['hour'].between(0, 7)]['atr_pct'].mean() if len(df) > 0 else 1,
            'london': df[df['hour'].between(8, 15)]['atr_pct'].mean() if len(df) > 0 else 1,
            'ny': df[df['hour'].between(16, 23)]['atr_pct'].mean() if len(df) > 0 else 1
        }
        
        # ضریب تعدیل سشن
        df['session'] = df['hour'].apply(
            lambda x: 'ny' if 16 <= x <= 23 else ('london' if 8 <= x <= 15 else 'asia')
        )
        df['vol_multiplier'] = df['session'].map(
            lambda s: session_vol.get(s, 1) / session_vol.get('london', 1)
        )
        
        # ATR تعدیل شده بر اساس سشن
        df['atr_adjusted'] = df['atr'] * df['vol_multiplier']
        
        return df
    
    def add_whale_activity(self, dataframe: DataFrame) -> DataFrame:
        """
        تشخیص فعالیت نهنگ‌ها (معاملات بزرگ)
        """
        df = dataframe.copy()
        
        # حجم معاملات
        df['volume_ma'] = ta.SMA(df['volume'], timeperiod=20)
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # معاملات بزرگ
        whale_threshold = df['volume'].quantile(0.9) if len(df) > 0 else 0
        df['whale_trade'] = (df['volume'] > whale_threshold).astype(int)
        df['whale_buy'] = ((df['volume'] > whale_threshold) & (df['close'] > df['open'])).astype(int)
        df['whale_sell'] = ((df['volume'] > whale_threshold) & (df['close'] < df['open'])).astype(int)
        
        # انباشت/توزیع نهنگ‌ها
        df['whale_accumulation'] = df['whale_buy'].rolling(5).sum() - df['whale_sell'].rolling(5).sum()
        
        return df
    
    # =========================================================================
    # 6. تشخیص رژیم بازار (Market Regime Detection)
    # =========================================================================
    
    def detect_market_regime(self, dataframe: DataFrame) -> str:
        """
        تشخیص رژیم فعلی بازار (bull, bear, accumulation, distribution, neutral)
        """
        df = dataframe.tail(50).copy()
        
        if len(df) < 50:
            return 'neutral'
        
        # محاسبه اندیکاتورهای کلیدی
        df['ema_20'] = ta.EMA(df['close'], timeperiod=20)
        df['ema_50'] = ta.EMA(df['close'], timeperiod=50)
        df['ema_200'] = ta.EMA(df['close'], timeperiod=200)
        
        current_price = df['close'].iloc[-1]
        ema_20 = df['ema_20'].iloc[-1]
        ema_50 = df['ema_50'].iloc[-1]
        ema_200 = df['ema_200'].iloc[-1]
        
        # موقعیت قیمت نسبت به EMAها
        above_ema20 = current_price > ema_20
        above_ema50 = current_price > ema_50
        above_ema200 = current_price > ema_200
        
        # ترتیب EMAها
        ema_bullish = ema_20 > ema_50 > ema_200
        ema_bearish = ema_20 < ema_50 < ema_200
        
        # روند حجم
        volume_ma = df['volume'].rolling(20).mean()
        volume_trend = df['volume'].iloc[-5:].mean() > volume_ma.iloc[-5:].mean()
        
        # محاسبه ADX برای قدرت روند
        df['adx'] = ta.ADX(df)
        current_adx = df['adx'].iloc[-1]
        
        # محاسبه RSI
        df['rsi'] = ta.RSI(df, timeperiod=14)
        current_rsi = df['rsi'].iloc[-1]
        
        # ============== منطق تشخیص رژیم ==============
        
        # بازار صعودی قوی
        if (above_ema20 and above_ema50 and above_ema200 and 
            ema_bullish and volume_trend and current_adx > 25):
            return 'bull_run'
        
        # بازار نزولی قوی
        elif (not above_ema20 and not above_ema50 and not above_ema200 and 
              ema_bearish and current_adx > 25):
            return 'bear_run'
        
        # انباشت (قیمت بالای EMA50 ولی پایین EMA200)
        elif above_ema50 and not above_ema200 and 40 <= current_rsi <= 60:
            return 'accumulation'
        
        # توزیع (قیمت پایین EMA50 ولی بالای EMA200)
        elif not above_ema50 and above_ema200 and 40 <= current_rsi <= 60:
            return 'distribution'
        
        # خنثی
        else:
            return 'neutral'
    
    def get_regime_adjustments(self, regime: str) -> Dict:
        """
        دریافت تنظیمات استراتژی بر اساس رژیم بازار
        """
        adjustments = {
            'bull_run': {
                'risk_multiplier': 1.3,
                'min_profit': 0.015,
                'trail_percent': 0.6,
                'max_position_size': 1.0,
                'prefer_long': True,
                'prefer_short': False,
                'atr_multiplier': 1.2,
                'max_leverage': 5
            },
            'bear_run': {
                'risk_multiplier': 0.5,
                'min_profit': 0.025,
                'trail_percent': 0.8,
                'max_position_size': 0.3,
                'prefer_long': False,
                'prefer_short': True,
                'atr_multiplier': 1.8,
                'max_leverage': 2
            },
            'accumulation': {
                'risk_multiplier': 0.8,
                'min_profit': 0.02,
                'trail_percent': 0.7,
                'max_position_size': 0.6,
                'prefer_long': True,
                'prefer_short': False,
                'atr_multiplier': 1.5,
                'max_leverage': 3
            },
            'distribution': {
                'risk_multiplier': 0.6,
                'min_profit': 0.022,
                'trail_percent': 0.7,
                'max_position_size': 0.5,
                'prefer_long': False,
                'prefer_short': True,
                'atr_multiplier': 1.5,
                'max_leverage': 3
            },
            'neutral': {
                'risk_multiplier': 1.0,
                'min_profit': 0.02,
                'trail_percent': 0.7,
                'max_position_size': 0.8,
                'prefer_long': True,
                'prefer_short': True,
                'atr_multiplier': 1.5,
                'max_leverage': 3
            }
        }
        
        return adjustments.get(regime, adjustments['neutral'])
    
    # =========================================================================
    # 7. اندیکاتورهای مومنتوم و قدرت روند
    # =========================================================================
    
    def add_crypto_momentum(self, dataframe: DataFrame) -> DataFrame:
        """
        اندیکاتور مومنتوم ترکیبی برای کریپتو
        """
        df = dataframe.copy()
        
        # RSI
        df['rsi_14'] = ta.RSI(df, timeperiod=14)
        
        # MACD
        macd = ta.MACD(df)
        df['macd'] = macd['macd']
        df['macd_signal'] = macd['macdsignal']
        df['macd_hist'] = macd['macdhist']
        
        # MFI
        df['mfi'] = ta.MFI(df)
        
        # OBV
        df['obv'] = ta.OBV(df)
        df['obv_ema'] = ta.EMA(df['obv'], timeperiod=20)
        df['obv_slope'] = np.gradient(df['obv_ema'])
        
        # مومنتوم ترکیبی
        df['composite_momentum'] = (
            (df['rsi_14'] - 50) * 0.3 +
            (df['macd_hist'] / df['close'] * 100) * 0.4 +
            ((df['obv'] - df['obv_ema']) / df['obv_ema'] * 100) * 0.3
        )
        
        df['composite_momentum_sma'] = ta.SMA(df['composite_momentum'], timeperiod=14)
        
        return df
    
    def add_market_structure(self, dataframe: DataFrame) -> DataFrame:
        """
        تشخیص ساختار بازار (سقف‌ها و کف‌های بالاتر/پایین‌تر)
        """
        df = dataframe.copy()
        
        # تشخیص سقف‌ها و کف‌های محلی
        df['swing_high'] = (
            (df['high'] > df['high'].shift(1)) & 
            (df['high'] > df['high'].shift(-1)) & 
            (df['high'] > df['high'].shift(2)) & 
            (df['high'] > df['high'].shift(-2))
        )
        
        df['swing_low'] = (
            (df['low'] < df['low'].shift(1)) & 
            (df['low'] < df['low'].shift(-1)) & 
            (df['low'] < df['low'].shift(2)) & 
            (df['low'] < df['low'].shift(-2))
        )
        
        # روند ساختاری
        df['higher_high'] = df['swing_high'] & (df['high'] > df['high'].shift(1))
        df['higher_low'] = df['swing_low'] & (df['low'] > df['low'].shift(1))
        df['lower_high'] = df['swing_high'] & (df['high'] < df['high'].shift(1))
        df['lower_low'] = df['swing_low'] & (df['low'] < df['low'].shift(1))
        
        # تشخیص روند
        hh_count = df['higher_high'].rolling(10).sum()
        hl_count = df['higher_low'].rolling(10).sum()
        lh_count = df['lower_high'].rolling(10).sum()
        ll_count = df['lower_low'].rolling(10).sum()
        
        df['structure_trend'] = 'ranging'
        df.loc[(hh_count >= 2) & (hl_count >= 2), 'structure_trend'] = 'uptrend'
        df.loc[(lh_count >= 2) & (ll_count >= 2), 'structure_trend'] = 'downtrend'
        
        return df
    
    # =========================================================================
    # 8. اندیکاتورهای حمایت و مقاومت (Support & Resistance)
    # =========================================================================
    
    def identify_support_levels(self, dataframe: DataFrame, lookback: int = 200) -> list:
        """
        شناسایی سطوح حمایتی افقی بر اساس کف‌های قیمتی قبلی
        این متد با نام identify_support_levels برای استفاده در استراتژی اصلی است
        """
        return self.identify_horizontal_support(dataframe, lookback)
    
    def identify_horizontal_support(self, dataframe: DataFrame, lookback: int = 200) -> list:
        """
        شناسایی سطوح حمایتی افقی بر اساس کف‌های قیمتی قبلی
        """
        df = dataframe.tail(lookback).copy()
        
        if len(df) < 20:
            return []
        
        # پیدا کردن کف‌های قیمتی
        df['swing_low'] = (
            (df['low'] < df['low'].shift(1)) & 
            (df['low'] < df['low'].shift(-1)) &
            (df['low'] < df['low'].shift(2)) & 
            (df['low'] < df['low'].shift(-2))
        )
        
        # استخراج قیمت کف‌ها
        swing_lows = df[df['swing_low']]['low'].tolist()
        
        # خوشه‌بندی سطوح نزدیک به هم
        support_levels = []
        threshold = df['close'].iloc[-1] * 0.005  # 0.5% آستانه
        
        for low in sorted(swing_lows):
            if not support_levels or abs(low - support_levels[-1]) > threshold:
                support_levels.append(low)
        
        return support_levels[-5:]  # ۵ سطح حمایتی آخر
    
    def identify_resistance_levels(self, dataframe: DataFrame, lookback: int = 200) -> list:
        """
        شناسایی سطوح مقاومتی افقی بر اساس سقف‌های قیمتی قبلی
        این متد با نام identify_resistance_levels برای استفاده در استراتژی اصلی است
        """
        return self.identify_horizontal_resistance(dataframe, lookback)
    
    def identify_horizontal_resistance(self, dataframe: DataFrame, lookback: int = 200) -> list:
        """
        شناسایی سطوح مقاومتی افقی بر اساس سقف‌های قیمتی قبلی
        """
        df = dataframe.tail(lookback).copy()
        
        if len(df) < 20:
            return []
        
        # پیدا کردن سقف‌های قیمتی
        df['swing_high'] = (
            (df['high'] > df['high'].shift(1)) & 
            (df['high'] > df['high'].shift(-1)) &
            (df['high'] > df['high'].shift(2)) & 
            (df['high'] > df['high'].shift(-2))
        )
        
        # استخراج قیمت سقف‌ها
        swing_highs = df[df['swing_high']]['high'].tolist()
        
        # خوشه‌بندی سطوح نزدیک به هم
        resistance_levels = []
        threshold = df['close'].iloc[-1] * 0.005  # 0.5% آستانه
        
        for high in sorted(swing_highs, reverse=True):
            if not resistance_levels or abs(high - resistance_levels[-1]) > threshold:
                resistance_levels.append(high)
        
        return resistance_levels[-5:]  # ۵ سطح مقاومتی آخر
    
    def validate_support_with_volume(self, dataframe: DataFrame, support_price: float) -> bool:
        """
        اعتبارسنجی حمایت با حجم معاملات
        """
        df = dataframe.tail(20).copy()
        
        if len(df) < 10:
            return False
        
        # بررسی حجم در نزدیکی حمایت
        near_support = df[df['low'].between(support_price * 0.99, support_price * 1.01)]
        
        if len(near_support) > 0:
            avg_volume = df['volume'].mean()
            support_volume = near_support['volume'].mean()
            
            # حمایت معتبر: افزایش حجم در برخورد به حمایت
            return support_volume > avg_volume * 1.2
        
        return False
    
    def add_fibonacci_levels(self, dataframe: DataFrame) -> DataFrame:
        """
        محاسبه سطوح فیبوناچی اصلاحی
        """
        df = dataframe.copy()
        
        # پیدا کردن آخرین موج
        last_high = df['high'].rolling(50).max().iloc[-1]
        last_low = df['low'].rolling(50).min().iloc[-1]
        
        if last_high > last_low:
            diff = last_high - last_low
            
            # سطوح کلیدی فیبوناچی
            df['fib_382'] = last_high - (diff * 0.382)
            df['fib_500'] = last_high - (diff * 0.5)
            df['fib_618'] = last_high - (diff * 0.618)
            df['fib_786'] = last_high - (diff * 0.786)
            
        return df
    
    def add_ma_support_resistance(self, dataframe: DataFrame) -> DataFrame:
        """
        میانگین‌های متحرک به عنوان حمایت و مقاومت داینامیک
        """
        df = dataframe.copy()
        
        df['ma_50'] = ta.SMA(df['close'], timeperiod=50)
        df['ma_100'] = ta.SMA(df['close'], timeperiod=100)
        df['ma_200'] = ta.SMA(df['close'], timeperiod=200)
        
        # فاصله تا میانگین‌های متحرک
        df['distance_to_ma50'] = (df['close'] - df['ma_50']) / df['ma_50'] * 100
        df['distance_to_ma100'] = (df['close'] - df['ma_100']) / df['ma_100'] * 100
        df['distance_to_ma200'] = (df['close'] - df['ma_200']) / df['ma_200'] * 100
        
        return df
    
    # =========================================================================
    # 9. متد جامع: اضافه کردن همه اندیکاتورها
    # =========================================================================
    
    def add_all_indicators(self, 
                           dataframe: DataFrame, 
                           pair: str,
                           btc_dom_data: Optional[DataFrame] = None) -> DataFrame:
        """
        اضافه کردن همه اندیکاتورهای کریپتو به دیتافریم
        """
        df = dataframe.copy()
        
        # 1. اندیکاتورهای پایه
        df = self.add_cvd(df)
        df = self.add_crypto_volatility(df, pair)
        df = self.add_atr_stop_levels(df)
        df = self.add_whale_activity(df)
        
        # 2. اندیکاتورهای مخصوص بیت‌کوین
        if "BTC" in pair:
            df = self.add_mvrv(df, pair)
            df = self.add_nupl(df)
            df = self.add_puell_multiple(df)
        
        # 3. تحلیل Dominance برای آلتکوین‌ها
        if btc_dom_data is not None and "BTC" not in pair:
            df = self.add_btc_dominance_impact(df, btc_dom_data)
        
        # 4. مومنتوم و ساختار بازار
        df = self.add_crypto_momentum(df)
        df = self.add_market_structure(df)
        
        # 5. تشخیص رژیم بازار
        df['market_regime'] = self.detect_market_regime(df)
        
        # 6. حمایت و مقاومت
        support_levels = self.identify_support_levels(df)
        if support_levels:
            df['nearest_support'] = support_levels[-1]
        
        resistance_levels = self.identify_resistance_levels(df)
        if resistance_levels:
            df['nearest_resistance'] = resistance_levels[-1]
        
        # 7. اندیکاتورهای اضافی
        df = self.add_fibonacci_levels(df)
        df = self.add_ma_support_resistance(df)
        
        # 8. سیگنال‌های ترکیبی
        df = self.add_consensus_signals(df)
        
        return df
    
    def add_consensus_signals(self, dataframe: DataFrame) -> DataFrame:
        """
        ایجاد سیگنال‌های اجماع از ترکیب اندیکاتورها
        """
        df = dataframe.copy()
        
        # سیگنال خرید قوی
        buy_conditions = [
            df.get('cvd_buy_signal', 0),
            df.get('mvrv_buy_zone', 0) if 'mvrv_buy_zone' in df.columns else 0,
            df.get('puell_buy', 0) if 'puell_buy' in df.columns else 0,
            (df.get('rsi_14', 50) < 30).astype(int),
            (df.get('composite_momentum', 0) < -2).astype(int),
            (df.get('whale_accumulation', 0) > 0).astype(int),
        ]
        
        # سیگنال فروش قوی
        sell_conditions = [
            df.get('cvd_sell_signal', 0),
            df.get('mvrv_sell_zone', 0) if 'mvrv_sell_zone' in df.columns else 0,
            df.get('puell_sell', 0) if 'puell_sell' in df.columns else 0,
            (df.get('rsi_14', 50) > 70).astype(int),
            (df.get('composite_momentum', 0) > 2).astype(int),
            (df.get('whale_accumulation', 0) < 0).astype(int),
        ]
        
        df['consensus_buy'] = sum(buy_conditions) / max(len(buy_conditions), 1)
        df['consensus_sell'] = sum(sell_conditions) / max(len(sell_conditions), 1)
        
        df['consensus_signal'] = 0
        df.loc[df['consensus_buy'] > 0.6, 'consensus_signal'] = 1
        df.loc[df['consensus_sell'] > 0.6, 'consensus_signal'] = -1
        
        return df
    
    # =========================================================================
    # 10. متدهای کمکی
    # =========================================================================
    
    def get_indicator_summary(self, dataframe: DataFrame) -> Dict:
        """
        خلاصه‌ای از وضعیت اندیکاتورها
        """
        if len(dataframe) == 0:
            return {}
        
        last = dataframe.iloc[-1]
        
        summary = {
            'cvd_status': 'bullish' if last.get('cvd_slope', 0) > 0 else 'bearish',
            'momentum': last.get('composite_momentum', 0),
            'volatility': last.get('atr_pct', 0),
            'volatility_regime': last.get('volatility_regime', 'normal'),
            'whale_activity': 'high' if last.get('whale_trade', 0) else 'normal',
            'consensus': last.get('consensus_signal', 0),
            'market_regime': last.get('market_regime', 'neutral'),
            'rsi': last.get('rsi_14', 50),
        }
        
        if 'nearest_support' in last:
            summary['nearest_support'] = last['nearest_support']
        
        if 'nearest_resistance' in last:
            summary['nearest_resistance'] = last['nearest_resistance']
        
        return summary
    
    def clear_cache(self):
        """پاک کردن کش"""
        self._cache.clear()