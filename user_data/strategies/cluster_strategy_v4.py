from datetime import datetime
from pandas import DataFrame
from freqtrade.persistence import Trade
# import api
import talib.abstract as ta
from datetime import datetime, timedelta
from freqtrade.strategy import (
    IStrategy
)

class ClusterStrategyV4(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    use_exit_signal = False

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
            conditions = (
                (trades[-1].close_profit_abs < 0),
                (trades[-2].close_profit_abs < 0),
                (datetime.now() < (trades[-1].close_date + timedelta(hours=12)))
            )

            if all(conditions):
                dataframe['enter_long'] = 0
                dataframe['enter_short'] = 0
                if not self.custom_info['max_consecutive_loss_notified']:
                    self.dp.send_msg('Two consecutive loss, stop trading for 12 hours...')
                    self.custom_info['max_consecutive_loss_notified'] = True
                return dataframe
            
            if self.custom_info['max_consecutive_loss_notified']:
                dataframe.loc[
                    (dataframe['close'] > dataframe['sma_300']),
                    'enter_long'
                ] = 1

                dataframe.loc[
                    (dataframe['close'] < dataframe['sma_300']),
                    'enter_short'
                ] = 1

                self.custom_info['max_consecutive_loss_notified'] = False

                return dataframe

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
    

    def bot_loop_start(self, **kwargs) -> None:
        
        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)