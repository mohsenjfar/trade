from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, date
# import api
from typing import Optional
from technical import qtpylib
import talib.abstract as ta
import pandas as pd
import math
import numpy as np
from typing import Dict
from freqtrade.exchange import timeframe_to_prev_date

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    stoploss_from_absolute
)

class MainStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

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
            {"method": "CooldownPeriod", "stop_duration_candles": 4},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 1,
                "unlock_at":"00:00",
                "required_profit": -0.02,
                "only_per_pair": False,
                "only_per_side": False
            }
        ]

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
        dataframe["%-bb_width"] = (dataframe["bb_upperband"] -
                                   dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)

        dataframe["%-relative_volume-period"] = (
            dataframe["volume"] / dataframe["volume"].rolling(period).mean()
        )

        return dataframe

    def feature_engineering_expand_basic(
            self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-raw_price"] = dataframe["close"]
        dataframe["%-pct-change"] = dataframe["close"].pct_change()
        dataframe["%-raw_open"] = dataframe["open"]
        dataframe["%-raw_low"] = dataframe["low"]
        dataframe["%-raw_high"] = dataframe["high"]

        return dataframe

    def feature_engineering_standard(
            self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

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

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        # dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        # dataframe['bb_upperband'] = bollinger['upper']
        # dataframe["bb_percent"] = (
        #     (dataframe["close"] - dataframe["bb_lowerband"]) /
        #     (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        # )
        # dataframe["bb_width"] = (
        #     (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        # )

        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                (df['tema'] < df['bb_middleband']) &  # Guard (tema below middle band)
                (df['tema'] > df['tema'].shift(1)) &  # Guard (tema rising)
                (df['volume'] > 0) &
                (df['do_predict'] == 1) &
                (df['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        df.loc[
            (
                (df['tema'] > df['bb_middleband']) &  # Guard (tema above middle band)
                (df['tema'] < df['tema'].shift(1)) &  # Guard (tema falling)
                (df['volume'] > 0) &
                (df['do_predict'] == 1) &
                (df['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1

        df.to_csv('user_data/notebooks/out.csv', index=False)

        return df

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

    #     return max(max_stake - max_stake * risk / abs(self.stoploss), min_stake)
    
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


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                        current_rate: float, current_profit: float,
                        **kwargs):
        # if (0 < current_profit <= 0.005) and (current_time - trade.open_date_utc).seconds >= 900:
        #     return "Trade expired!"

        if current_profit > 0.02:
            return "Target hit!"

    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        # if self.dp.runmode.value in ('live'):
        #     api.update_task(trade, current_time)

        # if current_profit > 0.04:
        #     return 0.02

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

        side = -1 if trade.is_short else 1
        return stoploss_from_absolute(
            trade.open_price * (1 + side * 0.001),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


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
    
    # def bot_start(self, **kwargs) -> None:
    #     if self.dp.runmode.value in ('live'):
    #         res = api.create_parent(__class__.__name__)
    #         self.dp.send_msg(f"Parent {res.get('title')} created")