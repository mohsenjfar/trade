import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    informative
)
from datetime import datetime
from typing import Optional

class RSIBreak(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '15m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    def extract_features(self, df, c1, c2, e, name):

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
            direction='forward'
        )

        pairs = pairs[['up_index','down_index']].drop_duplicates('down_index', keep='last').dropna().reset_index(drop=True)

        intervals = pd.IntervalIndex.from_arrays(pairs['up_index'], pairs['down_index'], closed='both')
        df['range_id'] = pd.cut(df.index, intervals)

        groups = df.groupby('range_id', observed=True)[e]
        values = groups.max() if e == "high" else groups.min()
        values = values.reset_index().rename(columns={e: name})
        values['index'] = intervals.left

        df = df.merge(values, left_on=df.index, right_on='index', how='left')

        return df.drop(['range_id_x','range_id_y','index'],axis=1)

    def populate_features(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)

        c1 = qtpylib.crossed_above(dataframe['rsi'], 70)
        c2 = qtpylib.crossed_below(dataframe['rsi'], 70)
        dataframe = self.extract_features(dataframe, c1, c2, 'high', "max_high")

        c1 = qtpylib.crossed_below(dataframe['rsi'], 30)
        c2 = qtpylib.crossed_above(dataframe['rsi'], 30)
        dataframe = self.extract_features(dataframe, c1, c2, 'low', "min_low")

        dataframe.loc[dataframe['max_high'].notna(),"cat"] = 'H'
        dataframe.loc[dataframe['min_low'].notna(),"cat"] = 'L'

        c1 = dataframe['max_high'].notna()
        c2 = qtpylib.crossed_above(dataframe['close'], dataframe['max_high'].ffill())
        dataframe = self.extract_features(dataframe, c1, c2, 'low', "sl")

        c1 = dataframe['min_low'].notna()
        c2 = qtpylib.crossed_below(dataframe['close'], dataframe['min_low'].ffill())
        dataframe = self.extract_features(dataframe, c1, c2, 'high', "ss")
        
        return dataframe

    @informative('1h')
    @informative('4h')
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['min_low_1h'].ffill()) & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['ss'].ffill())) # Trigger
            ), ["enter_long", "enter_tag"]] = (1,"15m")
        
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['min_low_4h'].ffill()) & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['ss_1h'].ffill())) # Trigger
            ), ["enter_long", "enter_tag"]] = (1,"1h")

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['max_high_1h'].ffill()) & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['sl'].ffill())) # Trigger
            ), ["enter_short", "enter_tag"]] = (1,"15m")
        
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['max_high_4h'].ffill()) & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['sl_1h'].ffill())) # Trigger
            ), ["enter_short", "enter_tag"]] = (1,"1h")
        
        dataframe.to_feather("user_data/notebooks/df.feather")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        stop = last_candle.high if side == "short" else last_candle.low
        risk = abs(stop / last_candle.close - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe_, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        dataframe = dataframe_.copy().ffill()
        last_candle = dataframe.iloc[-1].squeeze()
        
        if trade.is_short:
            if last_candle.ss_1h < trade.open_rate:
                stop = last_candle.ss_1h
            elif last_candle.ss_15m < trade.open_rate:
                stop = last_candle.ss_15m
            else:
                stop = last_candle.high
            
            if trade.get_custom_data(key='risk') is None:
                risk = abs(stop / last_candle.close - 1)
                trade.set_custom_data(key='risk', value=risk)
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

            return stoploss_from_absolute(
                stop,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

        else:
            if last_candle.sl_1h > trade.open_rate:
                stop = last_candle.sl_1h
            elif last_candle.sl_15m > trade.open_rate:
                stop = last_candle.sl_15m
            else:
                stop = last_candle.low
            
            if trade.get_custom_data(key='risk') is None:
                risk = abs(stop / last_candle.close - 1)
                trade.set_custom_data(key='risk', value=risk)
                self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")

            return stoploss_from_absolute(
                stop,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 240) and (current_profit < 0),
            (trade_duration > 1440) and (current_profit < risk * 2)
        )
        if any(conditions): return "Trade expired!"
