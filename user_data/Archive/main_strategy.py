from pandas import DataFrame, Series
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, date
# import api
from typing import Optional
from technical import qtpylib
import talib.abstract as ta
import pandas as pd
import numpy as np
from typing import Dict
from technical.pivots_points import pivots_points
from freqtrade.exchange import timeframe_to_prev_date
import math
import pandas_ta as pta

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    stoploss_from_absolute,
    stoploss_from_open
)

class MainStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.005

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 240

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    @property
    def protections(self):
        return [
            # {"method": "CooldownPeriod", "stop_duration_candles": 4},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 1,
                "stop_duration_candles": 24,
                "required_profit": 0,
                "only_per_pair": False,
                "only_per_side": False
            }
        ]

    # def bot_start(self, **kwargs) -> None:
    #     if self.dp.runmode.value in ('live'):
    #         res = api.create_parent(__class__.__name__)
    #         self.dp.send_msg(f"Parent {res.get('title')} created")

    def feature_engineering_expand_all(self, dataframe, period, **kwargs):
        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)
        dataframe["%-adx-period"] = ta.ADX(dataframe, window=period)
        dataframe["%-cci-period"] = ta.CCI(dataframe, timeperiod=period)
        dataframe["%-er-period"] = pta.er(dataframe['close'], length=period)
        dataframe["%-rocr-period"] = ta.ROCR(dataframe, timeperiod=period)
        dataframe["%-cmf-period"] = chaikin_mf(dataframe, periods=period)
        dataframe["%-tcp-period"] = top_percent_change(dataframe, period)
        dataframe["%-cti-period"] = pta.cti(dataframe['close'], length=period)
        dataframe["%-chop-period"] = qtpylib.chopiness(dataframe, period)
        dataframe["%-linear-period"] = ta.LINEARREG_ANGLE(
            dataframe['close'], timeperiod=period)
        dataframe["%-atr-period"] = ta.ATR(dataframe, timeperiod=period)
        dataframe["%-atr-periodp"] = dataframe[f"%-atr-period"] / dataframe['close'] * 1000
        return dataframe

    def feature_engineering_expand_basic(self, dataframe, **kwargs):
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-obv"] = ta.OBV(dataframe)
        # Added
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=14, stds=2.2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["%-bb_width"] = (dataframe["bb_upperband"] -
                                   dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        dataframe["%-ibs"] = ((dataframe['close'] - dataframe['low']) /
                              (dataframe['high'] - dataframe['low']))
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['%-distema50'] = get_distance(
            dataframe['close'], dataframe['ema_50'])
        dataframe['%-distema12'] = get_distance(
            dataframe['close'], dataframe['ema_12'])
        dataframe['%-distema26'] = get_distance(
            dataframe['close'], dataframe['ema_26'])
        macd = ta.MACD(dataframe)
        dataframe['%-macd'] = macd['macd']
        dataframe['%-macdsignal'] = macd['macdsignal']
        dataframe['%-macdhist'] = macd['macdhist']
        dataframe['%-dist_to_macdsignal'] = get_distance(
            dataframe['%-macd'], dataframe['%-macdsignal'])
        dataframe['%-dist_to_zerohist'] = get_distance(
            0, dataframe['%-macdhist'])
        # VWAP
        vwap_low, vwap, vwap_high = VWAPB(dataframe, 20, 1)
        dataframe['vwap_upperband'] = vwap_high
        dataframe['vwap_middleband'] = vwap
        dataframe['vwap_lowerband'] = vwap_low
        dataframe['%-vwap_width'] = ((dataframe['vwap_upperband'] -
                                     dataframe['vwap_lowerband']) / dataframe['vwap_middleband']) * 100
        dataframe = dataframe.copy()
        dataframe['%-dist_to_vwap_upperband'] = get_distance(
            dataframe['close'], dataframe['vwap_upperband'])
        dataframe['%-dist_to_vwap_middleband'] = get_distance(
            dataframe['close'], dataframe['vwap_middleband'])
        dataframe['%-dist_to_vwap_lowerband'] = get_distance(
            dataframe['close'], dataframe['vwap_lowerband'])
        dataframe['%-tail'] = (dataframe['close'] - dataframe['low']).abs()
        dataframe['%-wick'] = (dataframe['high'] - dataframe['close']).abs()
        pp = pivots_points(dataframe)
        dataframe['pivot'] = pp['pivot']
        dataframe['r1'] = pp['r1']
        dataframe['s1'] = pp['s1']
        dataframe['r2'] = pp['r2']
        dataframe['s2'] = pp['s2']
        dataframe['r3'] = pp['r3']
        dataframe['s3'] = pp['s3']
        dataframe['rawclose'] = dataframe['close']
        dataframe['%-dist_to_r1'] = get_distance(
            dataframe['close'], dataframe['r1'])
        dataframe['%-dist_to_r2'] = get_distance(
            dataframe['close'], dataframe['r2'])
        dataframe['%-dist_to_r3'] = get_distance(
            dataframe['close'], dataframe['r3'])
        dataframe['%-dist_to_s1'] = get_distance(
            dataframe['close'], dataframe['s1'])
        dataframe['%-dist_to_s2'] = get_distance(
            dataframe['close'], dataframe['s2'])
        dataframe['%-dist_to_s3'] = get_distance(
            dataframe['close'], dataframe['s3'])
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        dataframe["%-raw_open"] = dataframe["open"]
        dataframe["%-raw_low"] = dataframe["low"]
        dataframe["%-raw_high"] = dataframe["high"]
        return dataframe

    def feature_engineering_standard(self, dataframe, **kwargs):
        dataframe["day_of_week"] = (dataframe["date"].dt.dayofweek)
        dataframe["hour_of_day"] = (dataframe["date"].dt.hour)
        dataframe['day_of_week_norm'] = 2 * math.pi * \
            dataframe['day_of_week'] / dataframe['day_of_week'].max()
        dataframe['hour_of_day_norm'] = 2 * math.pi * \
            dataframe['hour_of_day'] / dataframe['hour_of_day'].max()

        dataframe['%%-day_of_week_cos'] = np.cos(dataframe['day_of_week_norm'])
        dataframe['%%-hour_of_day_cos'] = np.cos(dataframe['hour_of_day_norm'])
        dataframe['%%-day_of_week_sin'] = np.sin(dataframe['day_of_week_norm'])
        dataframe['%%-hour_of_day_sin'] = np.sin(dataframe['hour_of_day_norm'])
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-1) > dataframe["close"], 'up', 'down')

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # noqa: C901


        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['volume'] > 0) &
                (dataframe['do_predict'] == 1) &
                (dataframe['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['volume'] > 0) &
                (dataframe['do_predict'] == 1) &
                (dataframe['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1

        dataframe.to_csv('user_data/notebooks/out.csv', index=False)

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    # def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
    #                         proposed_stake: float, min_stake: Optional[float], max_stake: float,
    #                         leverage: float, entry_tag: Optional[str], side: str,
    #                         **kwargs) -> float:

    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
    #     prev_candle = dataframe.iloc[-2].squeeze()

    #     candle = prev_candle['high'] if side == "short" else prev_candle['low']
    #     risk = abs(1 - current_rate / candle)

    #     if risk > abs(self.stoploss):
    #         self.dp.send_msg(f"High risk, stop entering trade")
    #         return None

    #     return max_stake - max_stake * risk / abs(self.stoploss)
    
    # def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
    #                         time_in_force: str, current_time: datetime, entry_tag: Optional[str],
    #                         side: str, **kwargs) -> bool:

    #     today_trades = Trade.get_trades_proxy(open_date = date.today())
    #     today_loss = sum(trade.close_profit_abs for trade in today_trades if trade.close_profit_abs < 0)
    #     if (today_loss <= abs(self.stoploss)):
    #         self.dp.send_msg(f"Max day's loss ({today_loss:.2f}) is reached, stop trade entry ...")
    #         return False

    #     week_day = date.weekday(date.today())
    #     this_week_trades = Trade.get_trades_proxy(open_date = date.today() - timedelta(days=week_day))
    #     this_week_loss = sum(trade.close_profit_abs for trade in this_week_trades if trade.close_profit_abs < 0)
    #     if this_week_loss <= abs(self.stoploss) * 3:
    #         self.dp.send_msg(f"Max week's loss ({this_week_loss:.2f}) is reached, stop trade entry ...")
    #         return False

    #     return True


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        # dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        # last_candle = dataframe.iloc[-1].squeeze()

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            # side = 1 if trade.is_short else -1
            # stop = trade.open_rate + side * last_candle.atr
            # reward = trade.open_rate + side * last_candle.reward
            # trade.set_custom_data(key='stop', value=stop)
            # trade.set_custom_data(key='reward', value=reward)
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
            # if self.dp.runmode.value in ('live'):
            #     task = api.create_task(trade, __class__.__name__)
            #     trade.set_custom_data(key='task_id', value=task.get('id'))
            #     self.dp.send_msg(f"Task {task.get('summary')} created")

        # if trade.nr_of_successful_entries == 2 and self.dp.runmode.value in ('live'):
        #     task = api.complete(trade)
        #     self.dp.send_msg(f"Task {task.get('summary')} completed")

        return None

    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        # if self.dp.runmode.value in ('live'):
        #     api.update_task(trade, current_time)

        if current_profit > 0.04:
            return 0.02

        # dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        # pre_trade_dataframe = dataframe[(dataframe["date"] < trade.open_date_utc)]
        # pre_trade_candle = pre_trade_dataframe.iloc[-1].squeeze()

        # stop = pre_trade_candle['high'] if trade.is_short else pre_trade_candle['low']
        # return stoploss_from_absolute(
        #     stop,
        #     current_rate,
        #     is_short=trade.is_short,
        #     leverage=trade.leverage
        # )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                        current_rate: float, current_profit: float,
                        **kwargs):
        if (0 < current_profit <= 0.005) and (current_time - trade.open_date_utc).seconds >= 900:
            return "Trade expired!"


def top_percent_change(dataframe: DataFrame, length: int) -> float:
    """
    Percentage change of the current close from the range maximum Open price
    :param dataframe: DataFrame The original OHLC dataframe
    :param length: int The length to look back
    """
    if length == 0:
        return (dataframe['open'] - dataframe['close']) / dataframe['close']
    else:
        return (dataframe['open'].rolling(length).max() - dataframe['close']) / dataframe['close']


def chaikin_mf(df, periods=20):
    close = df['close']
    low = df['low']
    high = df['high']
    volume = df['volume']
    mfv = ((close - low) - (high - close)) / (high - low)
    mfv = mfv.fillna(0.0)
    mfv *= volume
    cmf = mfv.rolling(periods).sum() / volume.rolling(periods).sum()
    return Series(cmf, name='cmf')

# VWAP bands


def VWAPB(dataframe, window_size=20, num_of_std=1):
    df = dataframe.copy()
    df['vwap'] = qtpylib.rolling_vwap(df, window=window_size)
    rolling_std = df['vwap'].rolling(window=window_size).std()
    df['vwap_low'] = df['vwap'] - (rolling_std * num_of_std)
    df['vwap_high'] = df['vwap'] + (rolling_std * num_of_std)
    return df['vwap_low'], df['vwap'], df['vwap_high']


def EWO(dataframe, sma_length=5, sma2_length=35):
    df = dataframe.copy()
    sma1 = ta.EMA(df, timeperiod=sma_length)
    sma2 = ta.EMA(df, timeperiod=sma2_length)
    smadif = (sma1 - sma2) / df['close'] * 100
    return smadif


def get_distance(p1, p2):
    return abs((p1) - (p2))