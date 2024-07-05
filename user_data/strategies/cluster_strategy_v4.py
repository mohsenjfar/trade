from datetime import datetime
from pandas import DataFrame
from freqtrade.persistence import Trade
# import api
import talib.abstract as ta
from typing import Optional
from datetime import datetime, timedelta
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open
)

class ClusterStrategyV4(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '15m'

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

    custom_info = {
        'max_consecutive_loss_notified': False
    }


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
    

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> str | bool | None:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        conditions_1 = (
            (last_candle['close'] > last_candle['sma_300']),
            trade.is_short,
            current_profit > 0.02
        )

        conditions_2 = (
            (last_candle['close'] < last_candle['sma_300']),
            not trade.is_short,
            current_profit > 0.02
        )

        if all(conditions_1) or all(conditions_2):
            return "Opposite direction target hit!"

        return None


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:
        
        if current_profit > 0.1:
            return 0.05
        
        if current_profit > 0.05:
            return stoploss_from_open(
                0.02,
                current_profit,
                is_short=trade.is_short,
                leverage=trade.leverage
            )


    def bot_loop_start(self, **kwargs) -> None:
        
        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)