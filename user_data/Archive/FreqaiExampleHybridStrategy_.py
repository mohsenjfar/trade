import logging
from typing import Dict, List

import numpy as np  # noqa
import pandas as pd  # noqa
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib
from freqtrade.optimize.space import Categorical, Dimension, Integer, SKDecimal
from datetime import datetime, timedelta
from freqtrade.persistence import Trade
from freqtrade.exchange import timeframe_to_prev_date, timeframe_to_minutes
from typing import Optional, Union

from freqtrade.strategy import IntParameter, IStrategy, merge_informative_pair  # noqa


logger = logging.getLogger(__name__)


class FreqaiExampleHybridStrategy(IStrategy):

    # class HyperOpt:
    #     # Define a custom stoploss space.
    #     def stoploss_space():
    #         return [SKDecimal(-0.05, -0.01, decimals=3, name='stoploss')]

    #     # Define custom ROI space
    #     def roi_space() -> List[Dimension]:
    #         return [
    #             Integer(10, 120, name='roi_t1'),
    #             Integer(10, 60, name='roi_t2'),
    #             Integer(10, 40, name='roi_t3'),
    #             SKDecimal(0.01, 0.04, decimals=3, name='roi_p1'),
    #             SKDecimal(0.01, 0.07, decimals=3, name='roi_p2'),
    #             SKDecimal(0.01, 0.20, decimals=3, name='roi_p3'),
    #         ]

    #     def generate_roi_table(params: Dict) -> Dict[int, float]:

    #         roi_table = {}
    #         roi_table[0] = params['roi_p1'] + params['roi_p2'] + params['roi_p3']
    #         roi_table[params['roi_t3']] = params['roi_p1'] + params['roi_p2']
    #         roi_table[params['roi_t3'] + params['roi_t2']] = params['roi_p1']
    #         roi_table[params['roi_t3'] + params['roi_t2'] + params['roi_t1']] = 0

    #         return roi_table

    #     def trailing_space() -> List[Dimension]:
    #         # All parameters here are mandatory, you can only modify their type or the range.
    #         return [
    #             # Fixed to true, if optimizing trailing_stop we assume to use trailing stop at all times.
    #             Categorical([True], name='trailing_stop'),

    #             SKDecimal(0.01, 0.35, decimals=3, name='trailing_stop_positive'),
    #             # 'trailing_stop_positive_offset' should be greater than 'trailing_stop_positive',
    #             # so this intermediate parameter is used as the value of the difference between
    #             # them. The value of the 'trailing_stop_positive_offset' is constructed in the
    #             # generate_trailing_params() method.
    #             # This is similar to the hyperspace dimensions used for constructing the ROI tables.
    #             SKDecimal(0.001, 0.1, decimals=3, name='trailing_stop_positive_offset_p1'),

    #             Categorical([True, False], name='trailing_only_offset_is_reached'),
    #     ]

    lev = 1

    # ROI before leverage
    roi = 0.0025

    # Stoploss before leverage
    stoploss = -0.02

    risk_reward_ratio = 1
    atr_distance = 2

    timeframe = '5m'
    can_short = True
    timeframe_minutes = timeframe_to_minutes(timeframe)

    # Disable ROI
    minimal_roi = {
        "0": 1000
    }

    plot_config = {
        'main_plot': {
            'tema': {},
        },
        'subplots': {
            "MACD": {
                'macd': {'color': 'blue'},
                'macdsignal': {'color': 'orange'},
            },
            "RSI": {
                'rsi': {'color': 'red'},
            },
            "Up_or_down": {
                '&s-up_or_down': {'color': 'green'},
            }
        }
    }

    process_only_new_candles = True
    # stoploss = -0.05
    use_exit_signal = True
    startup_candle_count: int = 30
    can_short = True

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: Dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This function will automatically expand the defined features on the config defined
        `indicator_periods_candles`, `include_timeframes`, `include_shifted_candles`, and
        `include_corr_pairs`. In other words, a single feature defined in this function
        will automatically expand to a total of
        `indicator_periods_candles` * `include_timeframes` * `include_shifted_candles` *
        `include_corr_pairs` numbers of features added to the model.

        All features must be prepended with `%` to be recognized by FreqAI internals.

        More details on how these config defined parameters accelerate feature engineering
        in the documentation at:

        https://www.freqtrade.io/en/latest/freqai-parameter-table/#feature-parameters

        https://www.freqtrade.io/en/latest/freqai-feature-engineering/#defining-the-features

        :param dataframe: strategy dataframe which will receive the features
        :param period: period of the indicator - usage example:
        :param metadata: metadata of current pair
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)
        """

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe["bb_lowerband-period"] = bollinger["lower"]
        dataframe["bb_middleband-period"] = bollinger["mid"]
        dataframe["bb_upperband-period"] = bollinger["upper"]

        dataframe["%-bb_width-period"] = (
            dataframe["bb_upperband-period"]
            - dataframe["bb_lowerband-period"]
        ) / dataframe["bb_middleband-period"]
        dataframe["%-close-bb_lower-period"] = (
            dataframe["close"] / dataframe["bb_lowerband-period"]
        )

        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(
            self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This function will automatically expand the defined features on the config defined
        `include_timeframes`, `include_shifted_candles`, and `include_corr_pairs`.
        In other words, a single feature defined in this function
        will automatically expand to a total of
        `include_timeframes` * `include_shifted_candles` * `include_corr_pairs`
        numbers of features added to the model.

        Features defined here will *not* be automatically duplicated on user defined
        `indicator_periods_candles`

        All features must be prepended with `%` to be recognized by FreqAI internals.

        More details on how these config defined parameters accelerate feature engineering
        in the documentation at:

        https://www.freqtrade.io/en/latest/freqai-parameter-table/#feature-parameters

        https://www.freqtrade.io/en/latest/freqai-feature-engineering/#defining-the-features

        :param dataframe: strategy dataframe which will receive the features
        :param metadata: metadata of current pair
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-ema-200"] = ta.EMA(dataframe, timeperiod=200)
        """
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        return dataframe

    def feature_engineering_standard(
            self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        This optional function will be called once with the dataframe of the base timeframe.
        This is the final function to be called, which means that the dataframe entering this
        function will contain all the features and columns created by all other
        freqai_feature_engineering_* functions.

        This function is a good place to do custom exotic feature extractions (e.g. tsfresh).
        This function is a good place for any feature that should not be auto-expanded upon
        (e.g. day of the week).

        All features must be prepended with `%` to be recognized by FreqAI internals.

        More details about feature engineering available:

        https://www.freqtrade.io/en/latest/freqai-feature-engineering

        :param dataframe: strategy dataframe which will receive the features
        :param metadata: metadata of current pair
        usage example: dataframe["%-day_of_week"] = (dataframe["date"].dt.dayofweek + 1) / 7
        """
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:
        """
        *Only functional with FreqAI enabled strategies*
        Required function to set the targets for the model.
        All targets must be prepended with `&` to be recognized by the FreqAI internals.

        More details about feature engineering available:

        https://www.freqtrade.io/en/latest/freqai-feature-engineering

        :param dataframe: strategy dataframe which will receive the targets
        :param metadata: metadata of current pair
        usage example: dataframe["&-target"] = dataframe["close"].shift(-1) / dataframe["close"]
        """
        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-50) >
                                              dataframe["close"], 'up', 'down')

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # noqa: C901

        # User creates their own custom strat here. Present example is a supertrend
        # based strategy.

        dataframe = self.freqai.start(dataframe, metadata, self)

        # TA indicators to combine with the Freqai targets
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lowerband"]) /
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        )
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        # TEMA - Triple Exponential Moving Average
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        dataframe['atr'] = ta.ATR(dataframe, 14)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                # Signal: RSI crosses above 30
                (qtpylib.crossed_above(df['rsi'], self.buy_rsi.value)) &
                (df['tema'] <= df['bb_middleband']) &  # Guard: tema below BB middle
                (df['tema'] > df['tema'].shift(1)) &  # Guard: tema is raising
                (df['volume'] > 0) &  # Make sure Volume is not 0
                (df['do_predict'] == 1) &  # Make sure Freqai is confident in the prediction
                # Only enter trade if Freqai thinks the trend is in this direction
                (df['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        df.loc[
            (
                # Signal: RSI crosses above 70
                (qtpylib.crossed_above(df['rsi'], self.short_rsi.value)) &
                (df['tema'] > df['bb_middleband']) &  # Guard: tema above BB middle
                (df['tema'] < df['tema'].shift(1)) &  # Guard: tema is falling
                (df['volume'] > 0) &  # Make sure Volume is not 0
                (df['do_predict'] == 1) &  # Make sure Freqai is confident in the prediction
                # Only enter trade if Freqai thinks the trend is in this direction
                (df['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                # Signal: RSI crosses above 70
                (qtpylib.crossed_above(df['rsi'], self.sell_rsi.value)) &
                (df['tema'] > df['bb_middleband']) &  # Guard: tema above BB middle
                (df['tema'] < df['tema'].shift(1)) &  # Guard: tema is falling
                (df['volume'] > 0)  # Make sure Volume is not 0
            ),

            'exit_long'] = 1

        df.loc[
            (
                # Signal: RSI crosses above 30
                (qtpylib.crossed_above(df['rsi'], self.exit_short_rsi.value)) &
                # Guard: tema below BB middle
                (df['tema'] <= df['bb_middleband']) &
                (df['tema'] > df['tema'].shift(1)) &  # Guard: tema is raising
                (df['volume'] > 0)  # Make sure Volume is not 0
            ),
            'exit_short'] = 1

        return df

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:

        entry_time = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        cur_time = timeframe_to_prev_date(self.timeframe, current_time)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        atr_roi = trade.get_custom_data(key='atr_roi', default=None)
        atr_sl = trade.get_custom_data(key='atr_sl', default=None)

        if (atr_roi is not None):
            signal_time = entry_time - timedelta(minutes=int(self.timeframe_minutes))
            signal_candle = dataframe.loc[dataframe['date'] == signal_time]
            if not signal_candle.empty:
                signal_candle = signal_candle.iloc[-1].squeeze()
                if trade.is_short:
                    trade.set_custom_data(key='atr_roi', value=(signal_candle['close'] - (self.atr_distance * self.risk_reward_ratio * signal_candle['atr'])))
                    trade.set_custom_data(key='atr_sl', value=(signal_candle['close'] + (self.atr_distance * signal_candle['atr'])))
                else:
                    trade.set_custom_data(key='atr_roi', value=(signal_candle['close'] + (self.atr_distance * self.risk_reward_ratio * signal_candle['atr'])))
                    trade.set_custom_data(key='atr_sl', value=(signal_candle['close'] - (self.atr_distance * signal_candle['atr'])))
            
            atr_roi = trade.get_custom_data(key='atr_roi', default=None)
            atr_sl = trade.get_custom_data(key='atr_sl', default=None)

        if (cur_time > entry_time):
            current_candle = dataframe.iloc[-1].squeeze()
            
            # use ATR
            if atr_roi:
                if (current_candle['close'] >= atr_roi):
                    return "atr_roi"

                if (current_candle['close'] <= atr_sl):
                    return "atr_sl"
            # Use simple % roi/SL
            else:
                current_profit = trade.calc_profit_ratio(current_candle['close'])
                if current_profit >= (self.roi * self.lev):
                    return "emergency roi"
                if current_profit <= -(self.stoploss * self.lev):
                    return "emergency sl"
        return None
