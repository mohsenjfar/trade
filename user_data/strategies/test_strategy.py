# strategy_adaptive_simple.py
# هشدار: این یک الگوی اولیه است و نیاز به توسعه و بهینه‌سازی دارد.

import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame

class AdaptiveEntropySimpleStrategy(IStrategy):
    """
    یک استراتژی تطبیقی ساده که از آنتروپی برای تشخیص رژیم بازار استفاده می‌کند.
    این استراتژی صرفاً برای اهداف آموزشی ارائه شده است.
    """
    # --- تنظیمات اولیه استراتژی ---
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True
    stoploss = -0.05
    trailing_stop = True

    # --- پارامترهای قابل بهینه‌سازی با Hyperopt ---
    window_size = IntParameter(20, 100, default=30, space="buy")
    entropy_threshold_low = IntParameter(10, 30, default=20, space="buy")
    rsi_buy_threshold = IntParameter(25, 45, default=30, space="buy")
    rsi_sell_threshold = IntParameter(55, 75, default=70, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. محاسبه بازدهی
        dataframe['returns'] = dataframe['close'].pct_change()

        # 2. محاسبه آنتروپی در یک پنجره مشخص (قابل بهینه‌سازی)
        dataframe['entropy'] = 0.0
        for i in range(self.window_size.value, len(dataframe)):
            window_returns = dataframe['returns'].iloc[i-self.window_size.value:i]
            # حذف مقادیر null
            window_returns = window_returns.dropna()
            if len(window_returns) > 5:
                # محاسبه هیستوگرام و آنتروپی
                hist, _ = np.histogram(window_returns, bins=10, density=True)
                hist = hist[hist > 0]
                if len(hist) > 0:
                    entropy = -np.sum(hist * np.log2(hist))
                    dataframe.loc[dataframe.index[i], 'entropy'] = entropy

        # 3. سایر اندیکاتورها
        dataframe['rsi'] = ta.RSI(dataframe, length=14)
        bb = ta.BBANDS(dataframe, length=20)
        dataframe['bb_lowerband'] = bb['bb_lowerband']
        dataframe['bb_upperband'] = bb['bb_upperband']
        dataframe['bb_middleband'] = bb['bb_middleband']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # منطق ورود به معامله بر اساس آنتروپی
        # اگر آنتروپی پایین باشد (زیر آستانه) یعنی روندی است
        dataframe.loc[
            (
                (dataframe['entropy'] < self.entropy_threshold_low.value) &
                (dataframe['rsi'] < self.rsi_buy_threshold.value) &
                (dataframe['close'] < dataframe['bb_lowerband'])
            ),
            'enter_long'] = 1

        # اگر آنتروپی بالا باشد (بالای آستانه) یعنی رنج است
        dataframe.loc[
            (
                (dataframe['entropy'] >= self.entropy_threshold_low.value) &
                (dataframe['rsi'] > self.rsi_sell_threshold.value) &
                (dataframe['close'] > dataframe['bb_upperband'])
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # منطق خروج ساده بر اساس RSI
        dataframe.loc[
            (dataframe['rsi'] > 75),
            'exit_long'] = 1
        dataframe.loc[
            (dataframe['rsi'] < 25),
            'exit_short'] = 1
        return dataframe