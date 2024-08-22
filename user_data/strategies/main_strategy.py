from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, date
# import api
from typing import Optional
from technical import qtpylib
import talib.abstract as ta
import pandas as pd
import numpy as np
from typing import Dict

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    stoploss_from_absolute
)

class MainStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.02

    timeframe = '15m'

    use_exit_signal = False

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

    custom_info = {
        'max_day_not_notified': True,
        'max_week_not_notified': True
    }

    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)

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

        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict, **kwargs) -> DataFrame:

        self.freqai.class_names = ["down", "up"]
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-50) >
                                              dataframe["close"], 'up', 'down')

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # noqa: C901

        # User creates their own custom strat here. Present example is a supertrend
        # based strategy.

        dataframe = self.freqai.start(dataframe, metadata, self)

        # TA indicators to combine with the Freqai targets
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lowerband"]) /
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"])
        )
        dataframe["bb_width"] = (
            (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]
        )

        # TEMA - Triple Exponential Moving Average
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)

        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                (df['tema'] <= df['bb_middleband']) &  # Guard (tema below middle band)
                (df['tema'] > df['tema'].shift(1)) &  # Guard (tema rising)
                (qtpylib.crossed_above(df['rsi'], self.buy_rsi.value)) & # Trigger
                (df['volume'] > 0) &
                (df['do_predict'] == 1) &
                (df['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        df.loc[
            (
                (df['tema'] > df['bb_middleband']) &  # Guard (tema above middle band)
                (df['tema'] < df['tema'].shift(1)) &  # Guard (tema falling)
                (qtpylib.crossed_below(df['rsi'], self.short_rsi.value)) & # Trigger
                (df['volume'] > 0) &
                (df['do_predict'] == 1) &
                (df['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1

        return df

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        risk = current_candle.atr / current_rate
        return max(max_stake - max_stake * risk / abs(self.stoploss), min_stake)
    
    # def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
    #                         time_in_force: str, current_time: datetime, entry_tag: Optional[str],
    #                         side: str, **kwargs) -> bool:

    #     trades = pd.DataFrame(Trade.get_trades_proxy())

    #     today_loss = sum(trade.close_profit_abs for trade in today_trades if trade.close_profit_abs < 0)
    #     today_gain = sum(trade.close_profit_abs for trade in today_trades if trade.close_profit_abs > 0)
    #     today_profit = sum(trade.close_profit_abs for trade in today_trades)

    #     week_day = date.weekday(date.today())
    #     this_week_trades = Trade.get_trades_proxy(open_date = date.today() - timedelta(days=week_day))
    #     this_week_profit = sum(trade.close_profit_abs for trade in this_week_trades)

    #     if (today_profit <= self.custom_info['total_daily_risk']):
    #         if self.custom_info.get('max_day_not_notified'):
    #             self.dp.send_msg(f"Max day's loss ({today_profit:.2f}) is reached, stop trade entry ...")
    #             self.custom_info['max_day_not_notified'] = False
    #         return False
        
    #     if this_week_profit <= self.custom_info['total_daily_risk'] * 3:
    #         if self.custom_info.get('max_week_not_notified'):
    #             self.dp.send_msg(f"Max week's loss ({this_week_profit:.2f}) is reached, stop trade entry ...")
    #             self.custom_info['max_week_not_notified'] = False
    #         return False
        
    #     self.custom_info['max_week_not_notified'] = True
    #     self.custom_info['max_day_not_notified'] = True

    #     return True

    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if self.dp.runmode.value in ('live'):
            api.update_task(trade, current_time)

        if current_profit > 0.05:
            return 0.02

        if current_profit > 0.02:
            return stoploss_from_absolute(
                trade.open_rate,
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
            
            if self.dp.runmode.value in ('live'):
                task = api.create_task(trade, __class__.__name__)
                trade.set_custom_data(key='task_id', value=task.get('id'))
                self.dp.send_msg(f"Task {task.get('summary')} created")

        if trade.nr_of_successful_entries == 2 and self.dp.runmode.value in ('live'):
            task = api.complete(trade)
            self.dp.send_msg(f"Task {task.get('summary')} completed")

        return None
    
    def bot_start(self, **kwargs) -> None:
        if self.dp.runmode.value in ('live'):
            res = api.create_parent(__class__.__name__)
            self.dp.send_msg(f"Parent {res.get('title')} created")