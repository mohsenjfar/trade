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

    stoploss = -0.05

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


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['sma_300'] = ta.SMA(dataframe, 300)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'],is_open=False)

        # if trades:
        #     enter_long = 1 if (trades and trades[-1].is_short) else 0
        #     enter_short = 0 if (trades and trades[-1].is_short) else 1
        #     dataframe['enter_long'] = enter_long
        #     dataframe['enter_short'] = enter_short
        #     return dataframe

        dataframe.loc[
            (dataframe['close'] > dataframe['sma_300']),
            'enter_long'
        ] = 0

        dataframe.loc[
            (dataframe['close'] < dataframe['sma_300']),
            'enter_short'
        ] = 0

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> str:
        
    #     if current_profit > 2 * abs(self.stoploss):
    #         return 'Target Hit'

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:
        
        if current_profit > 0.1:
            return 0.03

        return None


    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:

        trades = pd.DataFrame(Trade.get_trades_proxy())

        values = [value for value in trades.head(1).values]

        self.dp.send_msg(str(values))