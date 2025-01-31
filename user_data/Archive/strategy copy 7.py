# importing freqtrade modules
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

# importing calculation modules
from pandas import DataFrame
from technical import qtpylib
import talib.abstract as ta

# importing other modules
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = False

    startup_candle_count: int = 240

    process_only_new_candles = True

    position_adjustment_enable = True

    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['rsi'] = ta.RSI(dataframe)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['rsi'], 30))
            ),
            ['enter_long', 'enter_tag']] = (1, 'rsi_cross')

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['rsi'], 70))
            ),
            ['enter_short', 'enter_tag']] = (1, 'rsi_cross')
                
        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        return 10


    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        if (current_profit > 1) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2

    
    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                current_profit: float, **kwargs):

        if current_profit > 10:
            return 'Target Hit!'