# strategy_adaptive_entropy.py
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import talib.abstract as ta

class AdaptiveEntropySimpleStrategy(IStrategy):
    """
    استراتژی تطبیقی ساده برای تشخیص رژیم بازار با آنتروپی
    نسخه اصلاح شده با رفع خطای KeyError
    """
    
    # ============================================
    # تنظیمات پایه
    # ============================================
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True
    stoploss = -0.05
    trailing_stop = True
    
    # پارامترهای قابل بهینه‌سازی با Hyperopt
    window_size = IntParameter(20, 100, default=30, space="buy")
    entropy_threshold_low = IntParameter(10, 30, default=20, space="buy")
    rsi_buy_threshold = IntParameter(25, 45, default=30, space="buy")
    rsi_sell_threshold = IntParameter(55, 75, default=70, space="sell")
    
    # ============================================
    # تابع محاسبه آنتروپی
    # ============================================
    def calculate_entropy(self, returns, bins=10):
        """
        محاسبه آنتروپی یک سری بازدهی
        آنتروپی پایین = روند قوی
        آنتروپی بالا = رنج یا بازار خنثی
        """
        if len(returns) < 5:
            return 0
        
        # ایجاد هیستوگرام از بازدهی‌ها
        hist, _ = np.histogram(returns, bins=bins, density=True)
        
        # حذف صفرها (برای جلوگیری از log(0))
        hist = hist[hist > 0]
        
        if len(hist) == 0:
            return 0
        
        # فرمول آنتروپی شانون: H = -Σ p(x) * log2(p(x))
        entropy = -np.sum(hist * np.log2(hist))
        
        return entropy
    
    # ============================================
    # محاسبه اندیکاتورها
    # ============================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        مح محاسبه تمام اندیکاتورهای مورد نیاز
        """
        
        # 1. محاسبه بازدهی (درصد تغییرات قیمت)
        dataframe['returns'] = dataframe['close'].pct_change()
        
        # 2. محاسبه آنتروپی در پنجره مشخص
        #    برای هر کندل، آنتروپی پنجره قبلی را محاسبه می‌کنیم
        dataframe['entropy'] = 0.0
        
        # دریافت مقدار فعلی پنجره (می‌تواند توسط Hyperopt بهینه شود)
        current_window = self.window_size.value
        
        for i in range(current_window, len(dataframe)):
            # گرفتن بازدهی‌های پنجره قبلی
            window_returns = dataframe['returns'].iloc[i-current_window:i]
            window_returns = window_returns.dropna()
            
            if len(window_returns) > 5:
                entropy = self.calculate_entropy(window_returns)
                dataframe.loc[dataframe.index[i], 'entropy'] = entropy
        
        # 3. محاسبه RSI (شاخص قدرت نسبی)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # 4. محاسبه باند بولینگر (اصلاح شده برای جلوگیری از KeyError)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2, nbdevdn=2)
        dataframe['bb_lowerband'] = bollinger['lowerband']
        dataframe['bb_middleband'] = bollinger['middleband']
        dataframe['bb_upperband'] = bollinger['upperband']
        
        # 5. محاسبه میانگین متحرک نمایی
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        
        # 6. محاسبه حجم نسبی (برای تأیید سیگنال‌ها)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume'].rolling(20).mean()
        
        return dataframe
    
    # ============================================
    # سیگنال‌های ورود به معامله
    # ============================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        تولید سیگنال‌های خرید و فروش بر اساس رژیم بازار
        """
        
        # ========== سیگنال خرید (Long) ==========
        # در رژیم روندی (آنتروپی پایین)
        dataframe.loc[
            (
                # شرط اول: آنتروپی پایین (بازار روندی)
                (dataframe['entropy'] < self.entropy_threshold_low.value) &
                # شرط دوم: RSI در محدوده اشباع فروش نیست اما پایین است
                (dataframe['rsi'] < self.rsi_buy_threshold.value) &
                # شرط سوم: قیمت پایین‌تر از باند پایین بولینگر (حمایت)
                (dataframe['close'] < dataframe['bb_lowerband']) &
                # شرط چهارم: قیمت بالای میانگین متحرک (تأیید روند صعودی)
                (dataframe['close'] > dataframe['ema_50']) &
                # شرط پنجم: حجم معاملات بالاتر از میانگین
                (dataframe['volume_ratio'] > 1.2)
            ),
            'enter_long'] = 1
        
        # در رژیم رنج (آنتروپی بالا) - خرید از کف رنج
        dataframe.loc[
            (
                # شرط اول: آنتروپی بالا (بازار رنج)
                (dataframe['entropy'] >= self.entropy_threshold_low.value) &
                # شرط دوم: RSI در محدوده اشباع فروش
                (dataframe['rsi'] < 30) &
                # شرط سوم: قیمت پایین‌تر از باند پایین بولینگر
                (dataframe['close'] < dataframe['bb_lowerband']) &
                # شرط چهارم: حجم معاملات بالا
                (dataframe['volume_ratio'] > 1.0)
            ),
            'enter_long'] = 1
        
        # ========== سیگنال فروش (Short) ==========
        # در رژیم روندی (آنتروپی پایین) - فروش در روند نزولی
        dataframe.loc[
            (
                # شرط اول: آنتروپی پایین (بازار روندی)
                (dataframe['entropy'] < self.entropy_threshold_low.value) &
                # شرط دوم: RSI در محدوده اشباع خرید
                (dataframe['rsi'] > self.rsi_sell_threshold.value) &
                # شرط سوم: قیمت بالاتر از باند بالای بولینگر
                (dataframe['close'] > dataframe['bb_upperband']) &
                # شرط چهارم: قیمت پایین‌تر از میانگین متحرک (تأیید روند نزولی)
                (dataframe['close'] < dataframe['ema_50']) &
                # شرط پنجم: حجم معاملات بالاتر از میانگین
                (dataframe['volume_ratio'] > 1.2)
            ),
            'enter_short'] = 1
        
        # در رژیم رنج (آنتروپی بالا) - فروش از سقف رنج
        dataframe.loc[
            (
                # شرط اول: آنتروپی بالا (بازار رنج)
                (dataframe['entropy'] >= self.entropy_threshold_low.value) &
                # شرط دوم: RSI در محدوده اشباع خرید
                (dataframe['rsi'] > 70) &
                # شرط سوم: قیمت بالاتر از باند بالای بولینگر
                (dataframe['close'] > dataframe['bb_upperband']) &
                # شرط چهارم: حجم معاملات بالا
                (dataframe['volume_ratio'] > 1.0)
            ),
            'enter_short'] = 1
        
        return dataframe
    
    # ============================================
    # سیگنال‌های خروج از معامله
    # ============================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        تولید سیگنال‌های خروج از معامله
        """
        
        # خروج از معاملات خرید (Long)
        dataframe.loc[
            (
                # خروج وقتی RSI وارد محدوده اشباع خرید می‌شود
                (dataframe['rsi'] > 75)
            ),
            'exit_long'] = 1
        
        # خروج از معاملات فروش (Short)
        dataframe.loc[
            (
                # خروج وقتی RSI وارد محدوده اشباع فروش می‌شود
                (dataframe['rsi'] < 25)
            ),
            'exit_short'] = 1
        
        # خروج در صورت تغییر رژیم بازار (اختیاری)
        # اگر آنتروپی به شدت تغییر کرد، از معامله خارج شو
        dataframe['entropy_change'] = dataframe['entropy'].pct_change()
        dataframe.loc[
            (
                (abs(dataframe['entropy_change']) > 0.5) &
                (dataframe['entropy_change'].notna())
            ),
            'exit_long'] = 1
        
        dataframe.loc[
            (
                (abs(dataframe['entropy_change']) > 0.5) &
                (dataframe['entropy_change'].notna())
            ),
            'exit_short'] = 1
        
        return dataframe