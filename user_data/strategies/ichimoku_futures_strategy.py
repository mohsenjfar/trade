import logging
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from technical.indicators import ichimoku
from typing import Dict

logger = logging.getLogger(__name__)

class IchimokuFuturesStrategy(IStrategy):
    # تنظیمات استراتژی
    timeframe = '4h'
    stoploss = -0.05
    minimal_roi = {
        "0": 0.1
    }
    
    # امکان معامله دو طرفه
    can_short = True

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        """
        محاسبه اندیکاتور ایشیموکو و اضافه کردن آن به dataframe
        """
        ichimoku_data = ichimoku(dataframe)
        dataframe['tenkan_sen'] = ichimoku_data['tenkan_sen']
        dataframe['kijun_sen'] = ichimoku_data['kijun_sen']
        dataframe['senkou_span_a'] = ichimoku_data['senkou_span_a']
        dataframe['senkou_span_b'] = ichimoku_data['senkou_span_b']
        dataframe['chikou_span'] = ichimoku_data['chikou_span']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        """
        شرایط ورود به معامله
        """
        # ورود به معامله لانگ
        dataframe.loc[
            (dataframe['close'] > dataframe['senkou_span_a']) & 
            (dataframe['close'] > dataframe['senkou_span_b']) & 
            (dataframe['tenkan_sen'] > dataframe['kijun_sen']) & 
            (dataframe['chikou_span'] > dataframe['close'].shift(26)),
            'enter_long'
        ] = 1

        # ورود به معامله شورت
        dataframe.loc[
            (dataframe['close'] < dataframe['senkou_span_a']) & 
            (dataframe['close'] < dataframe['senkou_span_b']) & 
            (dataframe['tenkan_sen'] < dataframe['kijun_sen']) & 
            (dataframe['chikou_span'] < dataframe['close'].shift(26)),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:
        """
        شرایط خروج از معامله
        """
        # خروج از معامله لانگ
        dataframe.loc[
            (dataframe['close'] < dataframe['senkou_span_a']) | 
            (dataframe['close'] < dataframe['senkou_span_b']),
            'exit_long'
        ] = 1

        # خروج از معامله شورت
        dataframe.loc[
            (dataframe['close'] > dataframe['senkou_span_a']) | 
            (dataframe['close'] > dataframe['senkou_span_b']),
            'exit_short'
        ] = 1

        return dataframe
