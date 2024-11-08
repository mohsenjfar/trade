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
    stoploss_from_absolute,
    stoploss_from_open
)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '5m'

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
            {"method": "CooldownPeriod", "stop_duration_candles": 6},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 4,
                "trade_limit": 1,
                "required_profit": 0,
                "only_per_pair": False,
                "only_per_side": False,
                "unlock_at":"00:00"
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
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-6) > dataframe["close"], 'up', 'down')

        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # noqa: C901


        dataframe = self.freqai.start(dataframe, metadata, self)

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_middleband'] = bollinger['mid']

        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)

        return dataframe


    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                (df['tema'] > df['tema'].shift(1)) &
                qtpylib.crossed_above(df['tema'], df['bb_middleband']) &
                (df['volume'] > 0) &
                (df['do_predict'] == 1) &
                (df['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        df.loc[
            (
                (df['tema'] < df['tema'].shift(1)) &
                qtpylib.crossed_below(df['tema'], df['bb_middleband']) &
                (df['volume'] > 0) &
                (df['do_predict'] == 1) &
                (df['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1

        df.to_csv('user_data/notebooks/out.csv', index=False)

        return df


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        return 5


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))

        return None
    

    # def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
    #                     current_rate: float, current_profit: float, after_fill: bool, 
    #                     **kwargs) -> Optional[float]:

    #     if current_profit > 0.02:
    #         return 0.01    

    #     if current_profit > 0.01:
    #         return stoploss_from_open(
    #             0.01, 
    #             current_profit, 
    #             is_short=trade.is_short, 
    #             leverage=trade.leverage
    #         )
        
    #     return None

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                        current_rate: float, current_profit: float,
                        **kwargs):
        if current_profit >= 0.02:
            return "Target Hit!"