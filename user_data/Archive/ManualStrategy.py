from freqtrade.strategy import IStrategy


class ManualStrategy(IStrategy):

    timeframe = '5m'

    stoploss = -1

    def populate_indicators(self, dataframe, metadata):

        return dataframe


    def populate_entry_trend(self, dataframe, metadata):

        dataframe['enter_long'] = 0

        return dataframe


    def populate_exit_trend(self, dataframe, metadata):

        dataframe['enter_short'] = 0

        return dataframe

    
    def custom_exit(self, pair: str, trade, current_time, current_rate,
                    current_profit, **kwargs):
        
        if current_profit > 0.04:
            return "Target Hit!"

        return None
