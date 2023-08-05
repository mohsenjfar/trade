from pandas import DataFrame
from datetime import datetime, timezone
from datetime import timedelta
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy


class LTS(IStrategy):

    INTERFACE_VERSION = 3

    timeframe = '1m'

    can_short: bool = False

    stoploss = -0.5

    minimal_roi = {
        "10": 0.0,
        "9": 0.1,
        "8": 0.3,
        "7": 0.5,
        "6": 1,
        "5": 2,
        "4": 3,
        "3": 4,
        "2": 5,
        "1": 10,
        "0": 20
    }

    order_types = {
        'entry': 'market',
        'exit': 'market',
        "force_entry": "market",
        "force_exit": "market",
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        if self.config['runmode'] in ('live', 'dry_run'):

            trade = Trade.get_trades_proxy(pair=metadata['pair'], is_open=False)
            
            print(trade)


            if trade:
                dataframe['enter_long'] = 0
            else:
                dataframe['enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe