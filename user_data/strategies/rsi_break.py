import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import (
    IStrategy,
    Trade,
    stoploss_from_absolute
)
from datetime import datetime, date
from math import ceil
from typing import Optional

class RSIBreak(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99
    }
    
    def extract_features(self, df, c1, c2, col, name, direction='forward'):

        highs = df.loc[c1].reset_index().rename(columns={'index':'up_index'})
        crosses = df.loc[c2].reset_index().rename(columns={'index':'down_index'})

        if highs.empty or crosses.empty:
            df[name] = np.nan
            return df

        pairs = pd.merge_asof(
            highs.sort_values('up_index'),
            crosses.sort_values('down_index'),
            left_on='up_index',
            right_on='down_index',
            direction=direction
        )

        pairs = pairs[['up_index','down_index']].drop_duplicates('down_index', keep='last').dropna().reset_index(drop=True)

        intervals = pd.IntervalIndex.from_arrays(pairs['up_index'], pairs['down_index'], closed='both')
        df['range_id'] = pd.cut(df.index, intervals)

        groups = df.groupby('range_id', observed=True)[col]
        values = groups.max() if col == "high" else groups.min()
        values = values.reset_index().rename(columns={col: name})
        values['index'] = intervals.left

        df = df.merge(values, left_on=df.index, right_on='index', how='left')

        return df.drop(['range_id_x','range_id_y','index'],axis=1)

    def populate_features(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        c1_over = qtpylib.crossed_above(dataframe['rsi'], 70)
        c2_over = qtpylib.crossed_below(dataframe['rsi'], 70)
        dataframe = self.extract_features(dataframe, c1_over, c2_over, "high", "max_high")
        dataframe = self.extract_features(dataframe, c1_over, c2_over, "low", "min_high")

        mask = dataframe['min_high'].notna()
        dataframe.loc[mask,'hlt'] = dataframe.loc[mask, 'high']
        dataframe.loc[mask,'hst'] = dataframe.loc[mask, 'low']
        
        c1_under = qtpylib.crossed_below(dataframe['rsi'], 30)
        c2_under = qtpylib.crossed_above(dataframe['rsi'], 30)
        dataframe = self.extract_features(dataframe, c1_under, c2_under, "low" ,"min_low")
        dataframe = self.extract_features(dataframe, c1_under, c2_under, "high", "max_low")

        mask = dataframe['max_low'].notna()
        dataframe.loc[mask,'llt'] = dataframe.loc[mask, 'high']
        dataframe.loc[mask,'lst'] = dataframe.loc[mask, 'low']

        dataframe.loc[dataframe['max_high'].notna(),"cat"] = 'H'
        dataframe.loc[dataframe['min_low'].notna(),"cat"] = 'L'

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['hlt'].ffill()))
            ), ["enter_long","enter_tag"]] = (1, 'high_long_trigger')
        
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['hst'].ffill()))
            ), ["enter_short","enter_tag"]] = (1, 'high_short_trigger')

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['llt'].ffill()))
            ), ["enter_long","enter_tag"]] = (1, 'low_long_trigger')
    
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['lst'].ffill()))
            ), ["enter_short","enter_tag"]] = (1, 'low_short_trigger')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        return dataframe

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stop = last_candle["high"] if side == "short" else last_candle["low"]
        risk = abs(stop / current_rate - 1)
        return ceil(self.trade_max_loss_allowed / risk)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        trades = Trade.get_trades_proxy(is_open=False, open_date=date.today())
        losses = [trade.close_profit_abs for trade in trades if trade.close_profit_abs < 0]
        if len(losses) == 4: return 0

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stop = last_candle["high"] if side == "short" else last_candle["low"]
        risk = abs(stop / current_rate - 1)
        if risk < 0.002: return 0
        return min(total_stake * self.trade_max_loss_allowed / (risk * leverage), max_stake)

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if trade.get_custom_data('stop') is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            
            stop = last_candle['high'] if trade.is_short else last_candle['low']
            trade.set_custom_data(key='stop', value=stop)
            
            risk = abs(stop / trade.open_rate - 1) * trade.leverage
            trade.set_custom_data(key='risk', value=risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

        return stoploss_from_absolute(
            trade.get_custom_data('stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        
        risk = trade.get_custom_data('risk')
        if current_profit > 4 * risk * trade.leverage: return "Target hit!"

    def custom_exit_price(self, pair: str, trade: Trade,
                          current_time: datetime, proposed_rate: float,
                          current_profit: float, exit_tag: str | None, **kwargs) -> float:

        risk = trade.get_custom_data('risk')
        side = -1 if trade.is_short else 1
        return trade.open_rate * (1 + 5 * risk * trade.leverage * side)
    

