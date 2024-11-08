from datetime import datetime
from pandas import DataFrame
from freqtrade.persistence import Trade
from freqtrade.data.btanalysis import load_trades_from_db
# import api
import talib.abstract as ta
from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    stoploss_from_absolute
)

class AgileStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '5m'

    use_exit_signal = True

    use_custom_stoploss = True

    process_only_new_candles = False

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 2,
                "required_profit": 0,
                "only_per_pair": False,
                "only_per_side": False,
                "stop_duration_candles": 48,
            }
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'],is_open=False)

        if trades:
            dataframe['enter_long'] = 1 if  trades[-1].is_short else 0
            dataframe['enter_short'] = 0 if  trades[-1].is_short else 1
            return dataframe

        dataframe['enter_long'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe
    

    # def leverage(self, pair: str, current_time: datetime, current_rate: float,
    #              proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
    #              **kwargs) -> float:
        
    #     return abs(self.stoploss) * 200
    

    # def bot_loop_start(self, **kwargs) -> None:
    #     pairs = self.dp.current_whitelist()
    #     for pair in pairs:
    #         if self.is_pair_locked(pair):
    #             self.unlock_pair(pair)