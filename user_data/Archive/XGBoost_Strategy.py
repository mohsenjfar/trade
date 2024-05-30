import logging
from typing import Dict

import numpy as np  # noqa
import pandas as pd  # noqa
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone, date
from freqtrade.strategy import IntParameter, IStrategy, stoploss_from_absolute, timeframe_to_prev_date  # noqa
from typing import Optional, Union
import api
from freqtrade_client import FtRestClient

logger = logging.getLogger(__name__)

server_url = 'http://127.0.0.1:8080'
username = ''
password = "a88923695f80935a17b99e51df8275bc3440b92defa52106c0cea26ca1bf1ce1"
client = FtRestClient(server_url, username, password)


class XGBoostStrategy(IStrategy):

    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04
    }

    plot_config = {
        'main_plot': {
            'tema': {},
        },
        'subplots': {
            "MACD": {
                'macd': {'color': 'blue'},
                'macdsignal': {'color': 'orange'},
            },
            "RSI": {
                'rsi': {'color': 'red'},
            },
            "Up_or_down": {
                '&s-up_or_down': {'color': 'green'},
            }
        }
    }

    process_only_new_candles = True
    stoploss = -0.05
    use_exit_signal = True
    startup_candle_count: int = 30
    can_short = True

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

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

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                # Signal: RSI crosses above 30
                (qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi.value)) &
                (dataframe['tema'] <= dataframe['bb_middleband']) &  # Guard: tema below BB middle
                (dataframe['tema'] > dataframe['tema'].shift(1)) &  # Guard: tema is raising
                (dataframe['volume'] > 0) &  # Make sure Volume is not 0
                (dataframe['do_predict'] == 1) &  # Make sure Freqai is confident in the prediction
                # Only enter trade if Freqai thinks the trend is in this direction
                (dataframe['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                # Signal: RSI crosses above 70
                (qtpylib.crossed_above(dataframe['rsi'], self.short_rsi.value)) &
                (dataframe['tema'] > dataframe['bb_middleband']) &  # Guard: tema above BB middle
                (dataframe['tema'] < dataframe['tema'].shift(1)) &  # Guard: tema is falling
                (dataframe['volume'] > 0) &  # Make sure Volume is not 0
                (dataframe['do_predict'] == 1) &  # Make sure Freqai is confident in the prediction
                # Only enter trade if Freqai thinks the trend is in this direction
                (dataframe['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def position_size(self, max_stake, risk, min_stake):
        return max(min(max_stake * abs(self.stoploss) / risk, max_stake), min_stake)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        ob = self.dp.orderbook(pair, 1)
        best_bid = ob['bids'][0][0]
        best_ask = ob['asks'][0][0]
        if side == "short":
            self.custom_info['risk'] = (last_candle.close + last_candle.atr - best_ask) / best_ask
        else:
            self.custom_info['risk'] = (best_bid - last_candle.close - last_candle.atr) / best_bid
        
        stake = self.position_size(max_stake, self.custom_info['risk'], min_stake)

        return stake
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
    

        this_week_profit = client.weekly(1).get('data')[0].get('rel_profit')

        starting_balance = client.daily(1).get('data')[0].get('starting_balance')
        dataframe = pd.DataFrame(client.trades().get('trades'))
        dataframe['rel_stake'] = dataframe['stake_amount'] / starting_balance
        dataframe['rel_profit'] = dataframe['close_profit_pct'] * dataframe['rel_stake'] / 100
        today_rel_profit = dataframe[
            (dataframe.close_date > date.today().strftime('%Y-%m-%d')) &
            (dataframe.close_profit_pct < 0)
        ].rel_profit.sum()

        if today_rel_profit <= self.stoploss * 4: # ~2%
            if self.custom_info.get('max_day_not_notified'):
                self.dp.send_msg(f"Max day's loss ({today_rel_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_day_not_notified'] = False
            return False
        
        if this_week_profit <= self.stoploss * 12: # ~6%
            if self.custom_info.get('max_week_not_notified'):
                self.dp.send_msg(f"Max week's loss ({this_week_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_week_not_notified'] = False
            return False
        
        self.custom_info['max_week_not_notified'] = True
        self.custom_info['max_day_not_notified'] = True

        return True

        
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if self.dp.runmode.value in ('live'):
            api.update_task(trade, current_time)

        if trade.is_short:
            if trade.enter_tag == 'lc':
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                candle = dataframe.iloc[-1].squeeze()
                trade.set_custom_data(key='stop', value=current_rate + candle['atr'])
            else:
                borders = self.custom_info['borders']
                stop = trade.get_custom_data(key='stop')
                reward = trade.get_custom_data(key='reward')
                borders = np.sort(np.append(borders, (stop, trade.open_rate, reward)))
                borders = np.flip(borders)
                borders = borders[borders > current_rate]
                if borders.size > 1:
                    if borders[-2] < stop:
                        trade.set_custom_data(key='stop', value=borders[-2])
        else:
            if trade.enter_tag == 'hc':
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                candle = dataframe.iloc[-1].squeeze()
                trade.set_custom_data(key='stop', value=current_rate - candle['atr'])
            else:
                borders = self.custom_info['borders']
                stop = trade.get_custom_data(key='stop')
                reward = trade.get_custom_data(key='reward')
                borders = np.sort(np.append(borders, (stop, trade.open_rate, reward)))
                borders = borders[borders < current_rate]
                if borders.size > 1:
                    if borders[-2] > stop:
                        trade.set_custom_data(key='stop', value=borders[-2])

        if str(borders) != str(self.custom_info['borders']):
            self.dp.send_msg(str(borders))
            self.custom_info['borders'] = str(borders)

        return stoploss_from_absolute(
            trade.get_custom_data(key='stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if trade.nr_of_successful_entries == 1:
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))

            if trade.is_short:
                stop = trade.open_rate * (1 + self.custom_info['risk'])
                reward = trade.open_rate * (1 - 2 * self.custom_info['risk'])
            else:
                stop = trade.open_rate * (1 - self.custom_info['risk'])
                reward = trade.open_rate * (1 + 2 * self.custom_info['risk'])
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='reward', value=reward)
            self.dp.send_msg(
                f"Stop: {stop:.4f}\nReward: {reward:.4f}\nOpen rate: {trade.open_rate:4f}"
            )
            
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