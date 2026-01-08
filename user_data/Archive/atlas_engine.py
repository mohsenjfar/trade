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

    buy_max_rsi = IntParameter(low=51, high=100, default=70, optimize=True, load=True)
    buy_min_rsi = IntParameter(low=1, high=50, default=30, optimize=True, load=True)
    
    buy_long_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    buy_long_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    buy_short_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    buy_short_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    sell_long_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    sell_long_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    sell_short_pt = DecimalParameter(low=0.01, high=0.1,default=0.01, decimals=2, optimize=True, load=True)
    sell_short_tt = IntParameter(low=1, high=10, default=2, optimize=True, load=True)

    def extract_features(self, dataframe, c1, c2, col, name, tt=0, pt=0, d="forward"):
        
        df = dataframe.copy()

        starts = df.loc[c1].reset_index().rename(columns={"index": "start"})
        ends   = df.loc[c2].reset_index().rename(columns={"index": "end"})

        if starts.empty or ends.empty:
            dataframe[name] = np.nan
            dataframe[f"{name}_index_dist"] = np.nan
            dataframe[f"{name}_price_dist"] = np.nan
            return dataframe

        pairs = pd.merge_asof(
            starts[['start']].sort_values("start"),
            ends[['end']].sort_values("end"),
            left_on="start",
            right_on="end",
            direction=d,
        ).dropna()[["start", "end"]]

        if pairs.empty:
            dataframe[name] = np.nan
            dataframe[f"{name}_index_dist"] = np.nan
            dataframe[f"{name}_price_dist"] = np.nan
            return dataframe

        intervals = pd.IntervalIndex.from_arrays(pairs["start"], pairs["end"], closed="both")
        df["range_id"] = pd.cut(df.index, intervals)

        e = 'max' if col == 'high' else 'min'
        group = df.groupby("range_id", observed=True)
        df[name] = group[col].transform(e)

        df[f"{name}_index_dist"] = group.cumcount() + 1
        df[f"{name}_index_dist"] = group[f"{name}_index_dist"].transform('max')

        hi = group['high'].transform('max')
        lo = group['low'].transform('min')
        df[f"{name}_price_dist"] = np.abs(hi - lo)

        df.loc[
            (df[col] != df[name]),
            [name, f"{name}_index_dist", f"{name}_price_dist"]
        ] = np.nan

        dataframe = dataframe.merge(df[[name, f"{name}_index_dist", f"{name}_price_dist"]],
                            left_index=True, right_index=True, how="left")

        c1 = (dataframe[f'{name}_index_dist'] >= tt)
        c2 = (dataframe[f'{name}_price_dist'] >= dataframe['close'] * pt)
        dataframe[name] = np.where((c1 & c2), dataframe[name], np.nan)
        
        return dataframe

    def populate_features(self, dataframe):

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)

        c1 = qtpylib.crossed_above(dataframe["rsi"], self.buy_max_rsi.value)
        c2 = qtpylib.crossed_below(dataframe["rsi"], self.buy_max_rsi.value)
        dataframe = self.extract_features(dataframe, c1, c2, "high", "max_high", 
                                          tt=self.buy_long_tt.value, 
                                          pt=self.buy_long_pt.value)
        dataframe = self.extract_features(dataframe, c2, c1, "low", "min_high", 
                                          tt=self.sell_long_tt.value,
                                          pt=self.sell_long_pt.value)
        c1 = qtpylib.crossed_below(dataframe["rsi"], self.buy_min_rsi.value)
        c2 = qtpylib.crossed_above(dataframe["rsi"], self.buy_min_rsi.value)
        dataframe = self.extract_features(dataframe, c1, c2, "low", "min_low", 
                                          tt=self.buy_short_tt.value, 
                                          pt=self.buy_short_pt.value)
        dataframe = self.extract_features(dataframe, c2, c1, "high", "max_low", 
                                          tt=self.sell_short_tt.value,
                                          pt=self.sell_short_pt.value)
        dataframe.loc[dataframe['max_high']==dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low']==dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = dataframe['cat'].ffill()

        return dataframe

    # @informative('1h')
    # def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

    #     dataframe = self.populate_features(dataframe, rsi_high=70, rsi_low=30, tt=1, pt=0)

    #     return dataframe
    
    # @informative('4h')
    # def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

    #     dataframe = self.populate_features(dataframe, rsi_high=70, rsi_low=30, tt=0, pt=0)

    #     return dataframe

    # @informative('1d')
    # def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

    #     dataframe = self.populate_features(dataframe, rsi_high=70, rsi_low=30, tt=2, pt=0)

    #     return dataframe
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)

        c1 = qtpylib.crossed_above(dataframe["rsi"], self.buy_max_rsi.value)
        c2 = qtpylib.crossed_below(dataframe["rsi"], self.buy_max_rsi.value)
        dataframe = self.extract_features(dataframe, c1, c2, "high", "max_high", 
                                          tt=self.buy_long_tt.value, 
                                          pt=self.buy_long_pt.value)
        dataframe = self.extract_features(dataframe, c2, c1, "low", "min_high", 
                                          tt=self.sell_long_tt.value,
                                          pt=self.sell_long_pt.value)
        c1 = qtpylib.crossed_below(dataframe["rsi"], self.buy_min_rsi.value)
        c2 = qtpylib.crossed_above(dataframe["rsi"], self.buy_min_rsi.value)
        dataframe = self.extract_features(dataframe, c1, c2, "low", "min_low", 
                                          tt=self.buy_short_tt.value, 
                                          pt=self.buy_short_pt.value)
        dataframe = self.extract_features(dataframe, c2, c1, "high", "max_low", 
                                          tt=self.sell_short_tt.value,
                                          pt=self.sell_short_pt.value)
        dataframe.loc[dataframe['max_high']==dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low']==dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = dataframe['cat'].ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (   
                (qtpylib.crossed_above(dataframe["close"], dataframe["max_high"].ffill())) # Trigger
            ),
            "enter_long"
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["close"], dataframe["min_low"].ffill())) # Trigger
            ),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def get_initial_stop(self, pair, side):
        
        dataframe_, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        dataframe = dataframe_.copy()
        name = "max_low" if side == "short" else "min_high"
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

    def get_trailing_stop(self, pair, side):
        
        dataframe_, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        dataframe = dataframe_.copy()
        name = f"max_low{self.tf}" if side == "short" else f"min_high{self.tf}"
        dataframe[name] = dataframe[name].ffill()
        last_candle = dataframe.iloc[-1].squeeze()
        return float(last_candle[name]), last_candle[f'cat{self.tf}'], last_candle[f'rsi{self.tf}']
    
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

        if trade.is_short and stop is not None and not np.isnan(stop):
            trailing_stop, cat, rsi = self.get_trailing_stop(pair, trade.trade_direction)
            if (trailing_stop < stop) and cat == 'L' and (trailing_stop > current_rate) and rsi < 30:
                trade.set_custom_data("stop", trailing_stop)

        if not trade.is_short and stop is not None and not np.isnan(stop):
            trailing_stop, cat, rsi = self.get_trailing_stop(pair, trade.trade_direction)
            if (trailing_stop > stop) and cat == 'H' and (trailing_stop < current_rate) and rsi > 70:
                trade.set_custom_data("stop", trailing_stop)

        return stoploss_from_absolute(
            trade.get_custom_data("stop"),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage,
        )
