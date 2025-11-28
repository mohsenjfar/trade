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

    timeframe = '15m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    max_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    min_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-sma-period"] = ta.SMA(dataframe, timeperiod=period)
        dataframe["%-ema-period"] = ta.EMA(dataframe, timeperiod=period)

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=period, stds=2.2
        )
        dataframe["bb_lowerband-period"] = bollinger["lower"]
        dataframe["bb_middleband-period"] = bollinger["mid"]
        dataframe["bb_upperband-period"] = bollinger["upper"]

        dataframe["%-bb_width-period"] = (
            dataframe["bb_upperband-period"]
            - dataframe["bb_lowerband-period"]
        ) / dataframe["bb_middleband-period"]
        dataframe["%-close-bb_lower-period"] = (
            dataframe["close"] / dataframe["bb_lowerband-period"]
        )

        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe['%-price_change'] = dataframe['close'] - dataframe['open']
        dataframe['%-range'] = dataframe['high'] - dataframe['low']
        dataframe['%-close_open_ratio'] = dataframe['close'] / dataframe['open']
        dataframe['%-high_close_ratio'] = dataframe['high'] / dataframe['close']
        dataframe['%-is_bullish'] = (dataframe['close'] > dataframe['open']).astype(int)
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        dataframe['%-volume_price_ratio'] = dataframe['volume'] / (dataframe['high'] - dataframe['low']).replace(0, np.nan)
        dataframe['%-volume_change'] = dataframe['volume'] / dataframe['volume'].shift(1)

        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-3) > dataframe["close"], 'up', 'down')

        return dataframe

    def extract_features(self, df, c1, c2, e, col, name):

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

    @informative('1h')
    @informative('4h')
    def populate_indicators_(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.populate_features(dataframe)

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.freqai.start(dataframe, metadata, self)
        
        dataframe = self.populate_features(dataframe)

        indicies = dataframe[dataframe['max_high'].notna()].index
        dataframe['sb'] = dataframe['max_high'].iat[indicies[-2]]

        indicies = dataframe[dataframe['min_low'].notna()].index
        dataframe['lb'] = dataframe['min_low'].iat[indicies[-2]]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'up') & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['lb'])) # Trigger
            ), "enter_long"] = 1

        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) & # Guard
                (dataframe['&s-up_or_down'] == 'down') & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['sb'])) # Trigger
            ), "enter_short"] = 1

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
        stop = last_candle["high"] if side == "short" else last_candle["low"]
        risk = abs(stop / last_candle["close"] - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        
        return dataframe['close'].iat[-1]

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if current_profit > 1: return 0.3

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        
        if trade.get_custom_data('stop') is None:
            last_candle = dataframe.iloc[-1].squeeze()
            stop = last_candle['high'] if trade.is_short else last_candle['low']
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle["close"] - 1)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %")
            
            trigger = 'max_high' if trade.is_short else 'min_low'
            index = dataframe[dataframe[trigger].notna()].index[-2]
            trade.set_custom_data(key='index', value=index)

        index = trade.get_custom_data('index')
        tfs = ['_4h', '_1h', '']
        if trade.is_short:    
            for tf in tfs:
                values = dataframe.loc[
                    (
                        (dataframe[f'ss{tf}'].notna()) &
                        (dataframe.index >= index)
                    ),f'ss{tf}'].values
                if values.size > 0: break
            stop = np.append(values, trade.get_custom_data('stop')).min()
        else:
            for tf in tfs:
                values = dataframe.loc[
                    (
                        (dataframe[f'sl{tf}'].notna()) &
                        (dataframe.index >= index)
                    ),f'sl{tf}'].values
                if values.size > 0: break
            stop = np.append(values, trade.get_custom_data('stop')).max()

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )

