import logging
from freqtrade.strategy import IStrategy, informative
from pandas import DataFrame
from technical.indicators import ichimoku
import talib.abstract as ta
from typing import Dict

logger = logging.getLogger(__name__)

class IchimokuRSIStrategy(IStrategy):
 
    timeframe = '15m'
    # informative_timeframe = '1h'
    can_short = True
    trailing_stop = False
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # @informative(informative_timeframe)
    # def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
    #     dataframe['rsi'] = ta.RSI(dataframe, period=14)
    #     return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:

        ichimoku_data = ichimoku(dataframe)
        dataframe['tenkan_sen'] = ichimoku_data['tenkan_sen']
        dataframe['kijun_sen'] = ichimoku_data['kijun_sen']
        dataframe['senkou_span_a'] = ichimoku_data['senkou_span_a']
        dataframe['senkou_span_b'] = ichimoku_data['senkou_span_b']
        dataframe['chikou_span'] = ichimoku_data['chikou_span']

        dataframe['rsi'] = ta.RSI(dataframe, period=14)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['senkou_span_a']) & 
                (dataframe['close'] > dataframe['senkou_span_b']) & 
                (dataframe['tenkan_sen'] > dataframe['kijun_sen']) & 
                (dataframe['chikou_span'] > dataframe['close'].shift(26))

            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['senkou_span_a']) & 
                (dataframe['close'] < dataframe['senkou_span_b']) & 
                (dataframe['tenkan_sen'] < dataframe['kijun_sen']) & 
                (dataframe['chikou_span'] < dataframe['close'].shift(26))
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict) -> DataFrame:

        return dataframe
