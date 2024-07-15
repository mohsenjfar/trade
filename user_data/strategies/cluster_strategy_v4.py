from datetime import datetime
from pandas import DataFrame
from freqtrade.persistence import Trade
# import api
import talib.abstract as ta
from typing import Optional
from datetime import datetime, timedelta
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    stoploss_from_absolute
)

class ClusterStrategyV4(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.04

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
                "lookback_period_candles": 2,
                "trade_limit": 1,
                "stop_duration_candles": 50,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False
            }
        ]


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['sma_300'] = ta.SMA(dataframe, 300)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'],is_open=False)

        if trades:
            enter_long = 1 if (trades and trades[-1].is_short) else 0
            enter_short = 0 if (trades and trades[-1].is_short) else 1
            dataframe['enter_long'] = enter_long
            dataframe['enter_short'] = enter_short
            return dataframe

        dataframe.loc[
            (dataframe['close'] > dataframe['sma_300']),
            'enter_long'
        ] = 1

        dataframe.loc[
            (dataframe['close'] < dataframe['sma_300']),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if current_profit > 0.01:
            return -0.005
        return -1