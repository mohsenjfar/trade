from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date
)

from pandas import DataFrame
from datetime import datetime, timedelta, date
from typing import Optional
from freqtrade.persistence import Trade

class Base(IStrategy):
    
    INTERFACE_VERSION = 3
    
    stoploss = -1
    
    timeframe = '15m'

    use_exit_signal = False

    use_custom_stoploss = True
    
    can_short: bool = True
    
    process_only_new_candles = True

    position_adjustment_enable = True

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 16,
                "trade_limit": 2,
                "stop_duration_candles": 4,
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": False
            }
        ]

    # Bypass populate_exit_trend method error
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # Max allowed trade loss 0.5 percent (0.005)
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        prev_candle = dataframe.iloc[-1].squeeze()

        stop = prev_candle['high'] if side == "short" else prev_candle['low']
        risk = abs(1 - current_rate / stop)
        trade_max_loss_allowed = 0.005

        return max(min(max_stake * trade_max_loss_allowed / risk, max_stake), min_stake)

    # Take out half of stake to control pull back risk (profit ~= risk)
    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date-timedelta(seconds=10))
        pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
        stop = pre_trade_candle.high if trade.is_short else pre_trade_candle.low
        risk = abs(1 - trade.open_rate / stop)

        if (current_profit > risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2