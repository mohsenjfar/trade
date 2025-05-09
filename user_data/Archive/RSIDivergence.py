from freqtrade.strategy import IStrategy, stoploss_from_absolute
import talib.abstract as ta
import pandas as pd

class RSIDivergence(IStrategy):
    timeframe = '15m'  # تایم‌فریم کوتاه برای اسکالپینگ
    minimal_roi = {"0": 0.2}  # تعیین حداقل سود
    stoploss = -1 # مقدار پایه‌ای حد ضرر، ولی مقدار واقعی داینامیک تنظیم می‌شود
    use_custom_stoploss = True

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # محاسبه شاخص RSI
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        # محاسبه ماکسیمم و مینیمم RSI
        dataframe['rsi_peak'] = dataframe['rsi'].rolling(window=10).max()
        dataframe['rsi_min'] = dataframe['rsi'].rolling(window=10).min()

        # محاسبه ماکسیمم قیمت در همان بازه برای تأیید واگرایی
        dataframe['price_peak'] = dataframe['high'].rolling(window=10).max()
        dataframe['price_min'] = dataframe['low'].rolling(window=10).min()

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # ورود به معامله شورت (واگرایی نزولی RSI + قیمت)
        dataframe.loc[
            (dataframe['rsi_peak'].shift(1) > dataframe['rsi_peak']) &  # پیک دوم RSI کمتر از اول
            (dataframe['rsi_peak'].shift(1) > 50) & 
            (dataframe['rsi_peak'] > 50) &
            (dataframe['price_peak'].shift(1) > dataframe['price_peak']),  # ماکس قیمت هم کاهش پیدا کند
            'enter_short'] = 1  # ورود به معامله شورت
        
        # ورود به معامله لانگ (واگرایی صعودی RSI + قیمت)
        dataframe.loc[
            (dataframe['rsi_min'].shift(1) < dataframe['rsi_min']) &  # مینیمم دوم RSI بزرگ‌تر از اول
            (dataframe['rsi_min'].shift(1) < 50) & 
            (dataframe['rsi_min'] < 50) &
            (dataframe['price_min'].shift(1) < dataframe['price_min']),  # مینیمم قیمت هم افزایش پیدا کند
            'enter_long'] = 1  # ورود به معامله لانگ

        return dataframe


    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        
        return dataframe


    def order_filled(self, pair: str, trade, order, current_time, **kwargs):

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        stop = candle.price_peak if trade.is_short else candle.price_min
        trade.set_custom_data(key='stop', value=stop)
        return None
    
    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        
        stop = trade.get_custom_data(key='stop')
        return stoploss_from_absolute(
                stop,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )