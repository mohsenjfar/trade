from freqtrade.strategy import (
    informative
)
import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from base import Base

class RSICrossStrategy(Base):

    # @informative('4h')
    # def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
    #     dataframe['rsi'] = ta.RSI(dataframe, 14)
    #     dataframe['rsi_max_index'] = dataframe[dataframe['rsi'] > 70].index.max()
    #     dataframe['rsi_min_index'] = dataframe[dataframe['rsi'] < 30].index.max()

    #     return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_70_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_30_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high_above_70'] = dataframe.groupby('above_70_group')['high'].transform('max')
        dataframe['min_low_below_30'] = dataframe.groupby('below_30_group')['low'].transform('min')
        dataframe.loc[dataframe['above_70_group'] == 0, 'max_high_above_70'] = None
        dataframe.loc[dataframe['below_30_group'] == 0, 'min_low_below_30'] = None
        dataframe = dataframe.ffill()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['close'], dataframe['max_high_above_70'])
                (dataframe['volume'] > 0 )
            ), "enter_long"] = 1
    
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['close'], dataframe['min_low_below_30'])
                (dataframe['volume'] > 0 )
            ), "enter_short"] = 1

        return dataframe