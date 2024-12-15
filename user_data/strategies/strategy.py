from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open
)


class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 288

    process_only_new_candles = True

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
    

    def correlated_pairs(self):
        pairs = self.dp.current_whitelist()
        tickers = {p:self.dp.get_pair_dataframe(pair=p, timeframe=self.timeframe).close for p in pairs}
        dataframe = pd.DataFrame(tickers).ffill()
        corr_df = dataframe.corr()
        max_corrs = corr_df[(corr_df != 1)].max()
        return corr_df[max_corrs == max_corrs.max()].index.to_list()


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        pairs = self.correlated_pairs()
        dataframe['enter_long'] = 1 if metadata['pair'] == pairs[0] else 0
        dataframe['enter_short'] = 1 if metadata['pair'] == pairs[1] else 0

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        trades_count = len(Trade.get_trades_proxy())
        open_trades = Trade.get_open_trade_count()

        if (trades_count % 2 == 0) and open_trades > 0:
            return False
        
        return True
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if current_profit >= 0.005:
            return stoploss_from_open(
                0,
                current_profit, 
                is_short=trade.is_short, 
                leverage=trade.leverage
            )

        return stoploss_from_open(
            -0.005,
            current_profit, 
            is_short=trade.is_short, 
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        if current_profit >= 0.01:
            return 'Target Hit!'