import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import talib.abstract as ta
from freqtrade.persistence import Trade
from math import ceil
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    IntParameter,
    DecimalParameter,
    informative,
    BooleanParameter
)
from datetime import datetime
from typing import Optional


class AtlasEngine(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    timeframe = '5m'

    can_short: bool = True
    process_only_new_candles = True

    use_exit_signal = True
    use_custom_stoploss = True

    position_adjustment_enable = False

    exit_profit_only = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }

    low = IntParameter(low=5, high=50, default=10, optimize=True, load=True, space='buy')
    medium = IntParameter(low=20, high=200, default=50, optimize=True, load=True, space='buy')
    # high = IntParameter(low=100, high=500, default=200, optimize=True, load=True, space='buy')
    atr = DecimalParameter(low=1, high=10, default=3, decimals=1, optimize=True, load=True, space='buy')
    # cooldown_lookback = IntParameter(2, 48, default=5, space="protection", optimize=True)
    # stop_duration = IntParameter(12, 200, default=5, space="protection", optimize=True)
    # use_stop_protection = BooleanParameter(default=True, space="protection", optimize=True)
    allowed_loss = DecimalParameter(low=0.001, high=0.05, default=0.01, decimals=3, optimize=True, load=True, space='allowed_loss')

    # @property
    # def protections(self):
    #     prot = []

    #     prot.append({
    #         "method": "CooldownPeriod",
    #         "stop_duration_candles": self.cooldown_lookback.value
    #     })
    #     if self.use_stop_protection.value:
    #         prot.append({
    #             "method": "StoplossGuard",
    #             "lookback_period_candles": 24 * 3,
    #             "trade_limit": 4,
    #             "stop_duration_candles": self.stop_duration.value,
    #             "only_per_pair": False
    #         })

    #     return prot

    
    # @informative('1h')
    # def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

    #     dataframe[f'sma_{self.medium.value}'] = ta.SMA(dataframe["close"], timeperiod=self.medium.value)

    #     return dataframe
    
    # @informative('4h')
    # def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

    #     dataframe[f'sma_{self.high.value}'] = ta.SMA(dataframe["close"], timeperiod=self.high.value)

    #     return dataframe

    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe[f'sma_{self.low.value}'] = ta.SMA(dataframe["close"], timeperiod=self.low.value)
        dataframe[f'sma_{self.medium.value}'] = ta.SMA(dataframe["close"], timeperiod=self.medium.value)
        dataframe['gradient'] = dataframe[f'sma_{self.medium.value}'].diff()
        dataframe[f'atr'] = ta.ATR(dataframe, timeperiod=14) * self.atr.value

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                # (dataframe[f"sma_{self.medium.value}"] > dataframe[f"sma_{self.high.value}"]) & # Guard
                (dataframe[f"gradient"] > 0) & # Guard
                (dataframe[f"gradient"].shift(1) > dataframe[f"gradient"]) & # Guard
                (qtpylib.crossed_above(dataframe[f"sma_{self.low.value}"], dataframe[f"sma_{self.medium.value}"])) # Trigger
            ),
            "enter_long"
        ] = 1

        dataframe.loc[
            (
                # (dataframe[f"sma_{self.medium.value}"] < dataframe[f"sma_{self.high.value}"]) & # Guard
                (dataframe[f"gradient"] < 0) & # Guard
                (dataframe[f"gradient"].shift(1) < dataframe[f"gradient"]) & # Guard
                (qtpylib.crossed_below(dataframe[f"sma_{self.low.value}"], dataframe[f"sma_{self.medium.value}"])) # Trigger
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (qtpylib.crossed_below(dataframe[f"sma_{self.low.value}"], dataframe[f"sma_{self.medium.value}"]))
            ),
            "exit_long"
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe[f"sma_{self.low.value}"], dataframe[f"sma_{self.medium.value}"]))
            ),
            "exit_short"
        ] = 1

        return dataframe

    def get_initial_stop(self, pair, side):
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        side = 1 if side == "short" else -1
        stop = last_candle['close'] + side * last_candle['atr']
        return stop

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:

        stop = self.get_initial_stop(pair, side)
        if stop is None or np.isnan(stop): return 1.0
        risk = abs(stop / current_rate - 1)
        if risk == 0: return 1.0
        lev = self.allowed_loss.value / risk
        return float(max(1, min(ceil(lev), max_leverage)))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        stop = self.get_initial_stop(pair, side)
        if stop is None or np.isnan(stop): return 0
        risk = abs(stop / current_rate - 1)
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.allowed_loss.value / (risk * leverage)
        return float(min(stake, max_stake))

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        risk = trade.get_custom_data(key='risk')
        if (current_profit > 2 * risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount * 0.3
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:

        stop = trade.get_custom_data("stop")
        if stop is None:
            stop = self.get_initial_stop(pair, trade.trade_direction)
            trade.set_custom_data("stop", stop)
            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data("risk", risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        return stoploss_from_absolute(
            trade.get_custom_data("stop"),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
