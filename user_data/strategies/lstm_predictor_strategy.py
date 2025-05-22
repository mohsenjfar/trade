import numpy as np
import tensorflow as tf
from freqtrade.strategy import IStrategy
from pandas import DataFrame
from sklearn.preprocessing import MinMaxScaler
import talib.abstract as ta
from tensorflow.keras.losses import MeanSquaredError

class LSTMPredictorStrategy(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {"0": 0.02}
    stoploss = -0.01
    timeframe = '5m'
    can_short: bool = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = tf.keras.models.load_model(
            "user_data/models/wif_lstm_model.h5",
            custom_objects={"mse": MeanSquaredError()}
        )
        self.scaler = MinMaxScaler(feature_range=(0, 1))

    def prepare_data(self, dataframe: DataFrame, seq_length=10):
        data_array = dataframe.to_numpy()
        num_rows = len(data_array) - (len(data_array) % seq_length)
        X = np.split(data_array[:num_rows], num_rows // seq_length)
        return np.array(X, dtype=np.float32)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_10"] = ta.EMA(dataframe, timeperiod=10)
        dataframe["sma_50"] = ta.SMA(dataframe, timeperiod=50)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["volume_change"] = dataframe["volume"].pct_change()
        dataframe.dropna(inplace=True)

        features = ["rsi", "ema_10", "sma_50", "atr", "volume_change", "close"]
        if not hasattr(self, 'scaler_fitted'):
            self.scaler.fit(dataframe[features])
            self.scaler_fitted = True

        dataframe[features] = self.scaler.transform(dataframe[features])

        seq_length = 10
        X = self.prepare_data(dataframe[features], seq_length)

        y_pred = self.model.predict(X)
        real_predicted_prices = self.scaler.inverse_transform(
            np.concatenate([np.zeros((len(y_pred), len(features)-1)), y_pred], axis=1)
        )[:, -1]

        dataframe["predicted_close"] = np.nan
        dataframe.iloc[-len(real_predicted_prices):, dataframe.columns.get_loc("predicted_close")] = real_predicted_prices

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["predicted_close"]), 
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] > dataframe["predicted_close"]),
            "enter_short"
        ] = 1
        return dataframe
