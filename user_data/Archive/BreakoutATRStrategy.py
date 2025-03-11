import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
from freqtrade.strategy.interface import IStrategy
from freqtrade.persistence import Trade
from technical.indicators import TEMA, ATR
from freqtrade.data.btanalysis import merge_informative_pair

class BreakoutATRStrategy(IStrategy):
    timeframe = '15m'
    informative_timeframe = '1w'
    stoploss = -0.10
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    use_custom_stoploss = False
    startup_candle_count: int = 30
    can_short: bool = True

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative_pairs = [(pair, self.informative_timeframe) for pair in pairs]
        return informative_pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.informative_timeframe)
        
        informative['weekly_max'] = informative['high'].rolling(1).max()
        informative['weekly_min'] = informative['low'].rolling(1).min()
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, self.informative_timeframe, ffill=True)
        dataframe['atr'] = ATR(dataframe, timeperiod=4)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['weekly_max'] + dataframe['atr']))
            ),
            ['enter_long', 'entry_tag']] = (1, 'weekly_max')

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['weekly_min'] + dataframe['atr']))
            ),
            ['enter_long', 'entry_tag']] = (1, 'weekly_min')

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['weekly_max'] - dataframe['atr']))
            ),
            ['enter_short', 'entry_tag']] = (1, 'weekly_max')

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['weekly_min'] - dataframe['atr']))
            ),
            ['enter_short', 'entry_tag']] = (1, 'weekly_min')

        return dataframe