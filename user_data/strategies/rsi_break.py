import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    stoploss_from_absolute
)
from datetime import datetime
from math import ceil
from typing import Optional
from user_data.utils.json_store import JsonStore

class RSIBreak(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    store = JsonStore(
        '/freqtrade/user_data/custom_info.json',
        default_data={'last_index': 0, 'exclude': []}
    )

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99
    }

    def extract_features(self, df, c1, c2, e, col, name, direction='forward'):

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
        values = groups.max() if e == "max" else groups.min()
        values = values.reset_index().rename(columns={col: name})
        values['index'] = intervals.left

        df = df.merge(values, left_on=df.index, right_on='index', how='left')

        return df.drop(['range_id_x','range_id_y','index'],axis=1)

    def populate_features(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        c1_over = qtpylib.crossed_above(dataframe['rsi'], 70)
        c2_over = qtpylib.crossed_below(dataframe['rsi'], 70)

        dataframe = self.extract_features(dataframe, c1_over, c2_over, 'max', "high", "max_high")
        dataframe = self.extract_features(dataframe, c1_over, c2_over, 'max', "rsi", "max_rsi")
        dataframe = self.extract_features(dataframe, c2_over, c1_over, 'min', 'low', "sl")
        dataframe = self.extract_features(dataframe, c2_over, c1_over, 'min', 'rsi', "sl_rsi")
        
        c1_under = qtpylib.crossed_below(dataframe['rsi'], 30)
        c2_under = qtpylib.crossed_above(dataframe['rsi'], 30)

        dataframe = self.extract_features(dataframe, c1_under, c2_under, 'min', "low", "min_low")
        dataframe = self.extract_features(dataframe, c1_under, c2_under, 'min', "rsi", "min_rsi")
        dataframe = self.extract_features(dataframe, c2_under, c1_under, 'max', "high", "ss")
        dataframe = self.extract_features(dataframe, c2_under, c1_under, 'max', "rsi", "ss_rsi")

        dataframe.loc[dataframe['max_high'].notna(),"cat"] = 'H'
        dataframe.loc[dataframe['min_low'].notna(),"cat"] = 'L'

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe = self.populate_features(dataframe)
        
        indicies = [
            dataframe[dataframe[trigger].notna()].date.max()
            for trigger in ['max_high', 'min_low']
        ]
        if max(indicies) != self.store['last_index']:
            self.store['last_index'] = max(indicies)
            self.store['exclude'] = []
        dataframe.drop(self.store['exclude'])

        indicies = dataframe[dataframe['max_high'].notna()].index
        dataframe['sb'] = dataframe['max_high'].iat[indicies[-2]]

        indicies = dataframe[dataframe['min_low'].notna()].index
        dataframe['lb'] = dataframe['min_low'].iat[indicies[-2]]

        dataframe['extrema'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-2:]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['extrema']=='LL') &
                (qtpylib.crossed_above(dataframe['close'], dataframe['lb']))
            ), "enter_long"] = 1

        dataframe.loc[
            (
                (dataframe['extrema']=='HH') &
                (qtpylib.crossed_below(dataframe['close'], dataframe['sb']))
            ), "enter_short"] = 1

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

            trigger = 'max_high' if trade.is_short else 'min_low'
            index = dataframe[dataframe[trigger].notna()].index[-2]
            trade.set_custom_data(key='index', value=int(index))

        return stoploss_from_absolute(
            trade.get_custom_data('stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        
        risk = trade.get_custom_data('risk')
        if current_profit > 5 * risk * trade.leverage: return "Target hit!"

    def order_filled(self, pair: str, trade: Trade, order: Order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_exits == 1) and (trade.close_profit_abs < 0):
            index = trade.get_custom_data('index')
            self.store.append('exclude', index)
            self.dp.send_msg(f"Excluded indicies: {self.store['exclude']}")

        return None
