from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta
from typing import Optional
from freqtrade_client import FtRestClient
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    timeframe_to_prev_date
)

server_url = 'http://127.0.0.1:8081'
username = ''
password = ""
client = FtRestClient(server_url, username, password)


class Long(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '15m'

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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['enter_long'] = 1
        dataframe['enter_short'] = 0

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe["close"].iat[-1]


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        
        trade_date = timeframe_to_prev_date(self.timeframe, current_time)
        if current_time - timedelta(seconds=5) > trade_date:
            return False
        
        client_status, client_trades = client.status(), client.trades()
        client_trades = len(client_trades) if client_trades and not client_trades.empty else 0
        client_open_trades = len(client_status) if client_status and not client_status.empty else 0
        trades_count = len(Trade.get_trades_proxy()) + client_trades
        open_trades = Trade.get_open_trade_count() + client_open_trades

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