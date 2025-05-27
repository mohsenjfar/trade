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
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from freqtrade.persistence import Trade

class LSTMPredictorStrategy(IStrategy):
    
    INTERFACE_VERSION = 3
    
    stoploss = -0.01
    
    timeframe = '1m'
    
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
        data_array = dataframe.to_numpy()
        num_rows = len(data_array) - (len(data_array) % seq_length)
        X = np.split(data_array[:num_rows], num_rows // seq_length)
        return np.array(X, dtype=np.float32)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['ema'] = ta.EMA(dataframe['close'], timeperiod=10)
        dataframe['atr'] = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
        dataframe['Close'] = dataframe['close']

        dataframe = pd.bfill(dataframe)

        if not hasattr(self, 'scaler_fitted'):
            self.scaler.fit(dataframe[self.features])
            self.scaler_fitted = True

        if not hasattr(self, 'price_scaler_fitted'):
            self.scaler.fit(dataframe['Close'])
            self.price_scaler_fitted = True

        dataframe[self.features] = self.scaler.transform(dataframe[self.features])
        self.price_scaler.transform(dataframe['Close'])

        seq_length = 10
        X_live = np.array(dataframe[self.features].iloc[-seq_length:].values).reshape(1, seq_length, len(self.features))

        y_pred = self.model.predict(X_live)
        real_predicted_prices = self.scaler.inverse_transform(
            np.concatenate([np.zeros((len(y_pred), len(self.features)-1)), y_pred], axis=1)
        )[:, -1]

        dataframe['max_predicted'] = real_predicted_prices.max()
        dataframe['min_predicted'] = real_predicted_prices.min()

        return dataframe
    

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                (dataframe["min_predicted"] >= dataframe['Close'] - dataframe["atr"]) &
                (dataframe["max_predicted"] >= dataframe['Close'] + 2 * dataframe["atr"])
            ), "enter_long"] = 1
    
        dataframe.loc[
            (
                (dataframe["max_predicted"] <= dataframe['Close'] + dataframe["atr"]) &
                (dataframe["min_predicted"] <= dataframe['Close'] - 2 * dataframe["atr"])
            ), "enter_short"] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        side = 1 if trade.is_short else -1
        stop = pre_trade_candle.close + side * pre_trade_candle.atr

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
        target = trade.open_rate + 2 * side * pre_trade_candle.atr

        conditions = [
            (current_rate < target) and trade.is_short,
            (current_rate > target) and not trade.is_short
        ]

        if any(conditions):
            return 'Target Hit'

        current_candle = dataframe.loc[-1].squeeze()
        conditions = [
            (current_candle.max_predicted > trade.open_rate) and trade.is_short,
            (current_candle.min_predicted < trade.open_rate) and not trade.is_short,
        ]
        if any(conditions):
            return "Trade expired"