import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from math import ceil
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    IntParameter,
    DecimalParameter,
    informative
)
from datetime import datetime
from typing import Optional


class AtlasEngine(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '15m'
    tf = ""
    can_short: bool = True
    process_only_new_candles = True

    use_exit_signal = True
    use_custom_stoploss = True

    position_adjustment_enable = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }

    # buy_max_rsi = IntParameter(low=51, high=100, default=70, optimize=True, load=True)
    # buy_min_rsi = IntParameter(low=1, high=50, default=30, optimize=True, load=True)
    
    # buy_long_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    # buy_long_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    # buy_short_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    # buy_short_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    # sell_long_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    # sell_long_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    # sell_short_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    # sell_short_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)


    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe['sma_200'] = ta.SMA(dataframe["close"], timeperiod=200)

        return dataframe
    
    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe['sma_200'] = ta.SMA(dataframe["close"], timeperiod=200)

        return dataframe

    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe['sma_5'] = ta.SMA(dataframe["close"], timeperiod=5)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (dataframe['sma_200_1h'] > dataframe['sma_200_4h']) & # Guard
                (qtpylib.crossed_above(dataframe["rsi"], 30)) # Trigger
            ),
            "enter_long"
        ] = 1

        dataframe.loc[
            (
                (dataframe['sma_200_1h'] < dataframe['sma_200_4h']) & # Guard
                (qtpylib.crossed_below(dataframe["rsi"], 70)) # Trigger
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (qtpylib.crossed_below(dataframe["sma_5"], dataframe["sma_200_1h"]))
            ),
            "exit_long"
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["sma_5"], dataframe["sma_200_1h"]))
            ),
            "exit_short"
        ] = 1

        return dataframe

    def get_initial_stop(self, pair, side):
        
        dataframe_, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        dataframe = dataframe_.copy()
        name = "max_high" if side == "short" else "min_low"
        dataframe[name] = dataframe[name].ffill()
        last_candle = dataframe.iloc[-1].squeeze()
        return float(last_candle[name])

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:

        stop = self.get_initial_stop(pair, side)
        if stop is None or np.isnan(stop): return 1.0
        risk = abs(stop / current_rate - 1)
        if risk == 0: return 1.0
        lev = self.trade_max_loss_allowed / risk
        return float(max(1, min(ceil(lev), max_leverage)))

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        stop = self.get_initial_stop(pair, side)
        if stop is None or np.isnan(stop): return 0
        risk = abs(stop / current_rate - 1)
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stake = total_stake * self.trade_max_loss_allowed / (risk * leverage)
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
