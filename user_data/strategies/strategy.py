from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_open
from pandas import DataFrame
from datetime import datetime
from typing import Optional
from collections import defaultdict

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '1h'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 48

    process_only_new_candles = False

    notifications = defaultdict(None)

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

    
    def bot_loop_start(self, **kwargs) -> None:
        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'], is_open=False)
        if trades:
            if trades[-1].is_short:
                dataframe['enter_long'] = 1
            else:
                dataframe['enter_short'] = 1
            return dataframe
        
        dataframe['enter_long'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        trades = Trade.get_trades_proxy()
        if trades:
            conditions = (
                all(trade.close_profit_abs < 0 for trade in trades[-2:]),
                (datetime.now() - trades[-2].close_date).seconds / 3600 < 1
            )
            if all(conditions):
                if (datetime.now() - trades[-1].close_date).seconds / 3600 < 4:
                    message = f"Two consecutive losses for {pair}, stop entering position for 4 hours."
                    if self.notifications.get(pair) != message:
                        self.dp.send_msg(message)
                        self.notifications[pair] = message
                    return False

        return True


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:


        if current_profit > 0.05:
            return 0.03

        if current_profit > 0.01:
            return stoploss_from_open(
                0.005,
                current_profit, 
                is_short=trade.is_short, 
                leverage=trade.leverage
            )

        return -1
