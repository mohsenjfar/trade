import pandas as pd
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta

class HighWinRateStrategy(IStrategy):
    # تنظیمات اساسی استراتژی
    minimal_roi = {
        "0": 0.1
    }
    stoploss = -0.02
    timeframe = '5m'
    
    # شاخص‌هایی که استفاده می‌شود
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # میانگین متحرک ساده (SMA)
        dataframe['sma50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['sma200'] = ta.SMA(dataframe, timeperiod=200)
        
        # شاخص قدرت نسبی (RSI)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # استوکاستیک RSI
        stochrsi = ta.STOCHRSI(dataframe, timeperiod=14)
        dataframe['stochrsi_k'] = stochrsi['fastk']
        dataframe['stochrsi_d'] = stochrsi['fastd']
        
        return dataframe
    
    # قوانین خرید
    def populate_buy_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        
        # میانگین متحرک کوتاه‌مدت بالای بلندمدت (Golden Cross)
        conditions.append(dataframe['sma50'] > dataframe['sma200'])
        
        # RSI پایین‌تر از 30 (موقعیت اشباع فروش)
        conditions.append(dataframe['rsi'] < 30)
        
        # تقاطع MACD
        conditions.append(dataframe['macd'] > dataframe['macdsignal'])
        
        # استوکاستیک RSI پایین‌تر از 20
        conditions.append(dataframe['stochrsi_k'] < 20)
        
        if conditions:
            dataframe.loc[
                (conditions),
                'buy'] = 1
        
        return dataframe
    
    # قوانین فروش
    def populate_sell_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        
        # RSI بالاتر از 70 (موقعیت اشباع خرید)
        conditions.append(dataframe['rsi'] > 70)
        
        if conditions:
            dataframe.loc[
                (conditions),
                'sell'] = 1
        
        return dataframe

# فراخوانی استراتژی در فریکترید
