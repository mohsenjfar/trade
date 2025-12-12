import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import numpy as np
import pandas as pd
import talib.abstract as ta
from freqtrade.persistence import Trade
from typing import Dict
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    IntParameter,
    informative
)
from datetime import datetime
from typing import Optional

class HybridStrategy(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.01

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

        dataframe['market'] = ''.join(dataframe.loc[dataframe['cat'].notna(), 'cat'].values)[-2:]

        return dataframe

    @informative('15m')
    @informative('1h')
    @informative('4h')
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe = self.populate_features(dataframe)

        dataframe['isl'] = dataframe['min_low'].ffill()
        dataframe['iss'] = dataframe['max_high'].ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['market_4h'] == 'HH') & # Guard
                (dataframe['rsi_1h'] < 40) & # Guard
                (dataframe['rsi_15m'] < 40) & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], 30)) # Trigger
            ), ["enter_long",'enter_tag']] = (1,'up_trend')

        dataframe.loc[
            (
                (dataframe['market_4h'] == 'LH') & # Guard
                (dataframe['rsi_1h'] < 40) & # Guard
                (dataframe['rsi_15m'] < 40) & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], 30)) # Trigger
            ), ["enter_long",'enter_tag']] = (1,'Range')
        
        dataframe.loc[
            (
                (dataframe['market_4h'] == 'LL') & # Guard
                (dataframe['rsi_1h'] > 60) & # Guard
                (dataframe['rsi_15m'] > 60) & # Guard
                (qtpylib.crossed_below(dataframe['rsi'], 70)) # Trigger
            ), ["enter_short",'enter_tag']] = (1,'down_trend')

        dataframe.loc[
            (
                (dataframe['market_4h'] == 'HL') & # Guard
                (dataframe['rsi_1h'] > 60) & # Guard
                (dataframe['rsi_15m'] > 60) & # Guard
                (qtpylib.crossed_below(dataframe['rsi'], 70)) # Trigger
            ), ["enter_short",'enter_tag']] = (1,'Range')
        
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
        stop = last_candle["iss"] if side == "short" else last_candle["isl"]
        risk = abs(stop / current_rate - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if current_profit > 1: return 0.3

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if trade.get_custom_data('stop') is None:
            last_candle = dataframe.iloc[-1].squeeze()
            stop = last_candle['iss'] if trade.is_short else last_candle['isl']
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / trade.open_rate - 1)
            trade.set_custom_data(key='risk', value=risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")
            
            trigger = 'max_high' if trade.is_short else 'min_low'
            index = dataframe[dataframe[trigger].notna()].index[-2]
            trade.set_custom_data(key='index', value=index)
        
        risk = trade.get_custom_data(key='risk')
        if current_profit > risk * 4:
            side = -1 if trade.is_short else 1
            stop = trade.open_rate * (1 + risk * 2 * side)
            trade.set_custom_data(key='stop', value=stop)

        index = trade.get_custom_data('index')
        tfs = ['_4h', '_1h', '_15m']
        if trade.is_short:    
            for tf in tfs:
                values = dataframe.loc[
                    (
                        (dataframe[f'ss{tf}'].notna()) &
                        (dataframe.index >= index)
                    ),f'ss{tf}'].values
                if values.size > 0: break
            stop_rate = np.append(values, trade.get_custom_data('stop')).min()
            
            return stoploss_from_absolute(
                stop_rate,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        
        else:
            for tf in tfs:
                values = dataframe.loc[
                    (
                        (dataframe[f'sl{tf}'].notna()) &
                        (dataframe.index >= index)
                    ),f'sl{tf}'].values
                if values.size > 0: break
            stop_rate = np.append(values, trade.get_custom_data('stop')).max()
            
            return stoploss_from_absolute(
                stop_rate,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

        
