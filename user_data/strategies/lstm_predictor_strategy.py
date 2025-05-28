import numpy as np
import tensorflow as tf
from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date,
    stoploss_from_absolute
)
from pandas import DataFrame
from sklearn.preprocessing import MinMaxScaler
import talib.abstract as ta
from tensorflow.keras.losses import MeanSquaredError
from datetime import datetime, timedelta
from typing import Optional
from freqtrade.persistence import Trade

class LSTMPredictorStrategy(IStrategy):
    
    INTERFACE_VERSION = 3
    
    stoploss = -0.05
    
    timeframe = '15m'

    trigger_multiplier = 4

    target_multiplier = 4
    
    can_short: bool = True
    
    use_exit_signal = True

    use_custom_stoploss = True
    
    process_only_new_candles = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = tf.keras.models.load_model(
            "user_data/models/lstm_scalping_model.h5",
            custom_objects={"mse": MeanSquaredError()}
        )
        self.features = ['close', 'volume', 'rsi', 'ema', 'atr']
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.price_scaler = MinMaxScaler(feature_range=(0, 1))

    def prepare_data(self, dataframe: DataFrame, seq_length=10):
        values = dataframe[self.features].iloc[-seq_length:].values
        return np.array(values).reshape(1, seq_length, len(self.features))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['ema'] = ta.EMA(dataframe['close'], timeperiod=10)
        dataframe['atr'] = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe.fillna(dataframe.mean())

        self.price_scaler.fit(dataframe[['close']])
        self.price_scaler.transform(dataframe[['close']])
        self.scaler.fit(dataframe[self.features])
        dataframe[self.features] = self.scaler.transform(dataframe[self.features])
        
        X_live = self.prepare_data(dataframe, seq_length=10)
        y_pred = self.model.predict(X_live)

        dataframe[self.features] = self.scaler.inverse_transform(dataframe[self.features])
        real_predicted_prices = self.price_scaler.inverse_transform(y_pred.reshape(-1, 1))
        
        dataframe['max_predicted'] = real_predicted_prices.max()
        dataframe['min_predicted'] = real_predicted_prices.min()

        values = (
            f"Close: {dataframe.close.iat[-1]:.4f}",
            f"Max: {real_predicted_prices.max():.4f}",
            f"Min: {real_predicted_prices.min():.4f}",
            f"ُStop: {(dataframe.atr.iat[-1] / dataframe.close.iat[-1]):.2f} %",
            f"Max: {(real_predicted_prices.max() / dataframe.close.iat[-1] - 1):.2f} %",
            f"Min: {(real_predicted_prices.min() / dataframe.close.iat[-1] - 1):.2f} %"
        )
        self.dp.send_msg('\n'.join(values))

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                (dataframe["min_predicted"] >= dataframe['close']) &
                (dataframe["max_predicted"] >= dataframe['close'] + self.trigger_multiplier * dataframe["atr"])
            ), "enter_long"] = 1
    
        dataframe.loc[
            (
                (dataframe["max_predicted"] <= dataframe['close']) &
                (dataframe["min_predicted"] <= dataframe['close'] - self.trigger_multiplier * dataframe["atr"])
            ), "enter_short"] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe["close"].iat[-1]
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        side = 1 if trade.is_short else -1
        stop = trade.open_rate + side * pre_trade_candle.atr

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        side = -1 if trade.is_short else 1
        target = trade.open_rate + self.target_multiplier * side * pre_trade_candle.atr

        conditions = [
            (current_rate < target) and trade.is_short,
            (current_rate > target) and not trade.is_short
        ]
        if any(conditions): return 'Target Hit'

        current_candle = dataframe.iloc[-1].squeeze()
        conditions = [
            (current_candle.max_predicted > trade.open_rate) and trade.is_short,
            (current_candle.min_predicted < trade.open_rate) and not trade.is_short,
        ]
        if any(conditions): return "Trade expired"