# importing freqtrade modules
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_open

# importing calculation modules
from pandas import DataFrame

# importing other modules
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    use_exit_signal = True

    use_custom_stoploss = True

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

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'],is_open=False)

        if trades:
            dataframe['enter_long'] = 1 if  trades[-1].is_short else 0
            dataframe['enter_short'] = 0 if  trades[-1].is_short else 1
            return dataframe

        dataframe['enter_short'] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        try:
            today = datetime.now(timezone.utc).date()
            closed_trades = Trade.get_trades_proxy(close_date=today)
            today_loss = sum(trade.close_profit_abs for trade in closed_trades if trade.close_profit_abs < 0)
            stake_in_use = Trade.total_open_trades_stakes()
            total_stake = stake_in_use + max_stake
            today_loss_ratio = today_loss / total_stake

            if today_loss_ratio < self.stoploss * 2:
                logger.info(f"Max day loss ({today_loss_ratio * 100:.2f}%), stop entering {side} position for {pair}")
                return None
            
            return proposed_stake
        
        except Exception as e:
            logger.warning(e)
            return None


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        side = 1 if side == 'short' else -1
        return proposed_rate * (1 + side * 0.01)
    

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        if (current_profit > abs(self.stoploss)) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if current_profit > 0.2:
            return 0.1

        if current_profit > 0.1:
            return 0.05

        if current_profit > 0.05:
            return 0.02

        return stoploss_from_open(
            -0.01,
            current_profit, 
            is_short=trade.is_short, 
            leverage=trade.leverage
        )