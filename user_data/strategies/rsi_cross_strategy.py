from freqtrade.strategy import (
    informative
)
import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from base import Base

class RSICrossStrategy(Base):

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe['rsi'] = ta.RSI(dataframe, 14)
        dataframe['rsi_max_index'] = dataframe[dataframe['rsi'] > 70].index.max()
        dataframe['rsi_min_index'] = dataframe[dataframe['rsi'] < 30].index.max()

        return dataframe

    # @informative('1d')
    # def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
    #     dataframe['rsi'] = ta.RSI(dataframe, 14)
    #     dataframe['rsi_max_index'] = dataframe[dataframe['rsi'] > 70].index.max()
    #     dataframe['rsi_min_index'] = dataframe[dataframe['rsi'] < 30].index.max()

    #     return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['rsi'], 30) &
                (dataframe['rsi_min_index_4h'] > dataframe['rsi_max_index_4h'] ) &
                (dataframe['rsi_4h'] > 30 ) & 
                (dataframe['rsi_4h'] < 50 )
            ), "enter_long"] = 1
    
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['rsi'], 70) &
                (dataframe['rsi_max_index_4h'] > dataframe['rsi_min_index_4h'] ) &
                (dataframe['rsi_4h'] < 70 ) &
                (dataframe['rsi_4h'] > 50 )
            ), "enter_short"] = 1

        return dataframe