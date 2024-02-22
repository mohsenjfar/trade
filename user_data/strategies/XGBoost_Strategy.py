import logging
from typing import Dict

import numpy as np  # noqa
import pandas as pd  # noqa
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib
from freqtrade.persistence import Trade
from datetime import datetime, timedelta
from freqtrade.strategy import IntParameter, IStrategy, merge_informative_pair  # noqa
from typing import Optional, Union

logger = logging.getLogger(__name__)


class XGBoostStrategy(IStrategy):

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
    stoploss = -0.1
    use_exit_signal = True
    startup_candle_count: int = 30
    can_short = True
    use_custom_stoploss = True

    total_risk = 0.01

    custom_info = {}

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
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-8) >
                                              dataframe["close"], 'up', 'down')

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # noqa: C901


        dataframe = self.freqai.start(dataframe, metadata, self)

        dataframe['rsi'] = ta.RSI(dataframe)

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

        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        dataframe['atr'] = ta.ATR(dataframe)
        dataframe['stop_loss'] = dataframe['close']-(dataframe['atr']*2)

        return dataframe
    
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                # Signal: RSI crosses above 30
                (qtpylib.crossed_above(df['rsi'], self.buy_rsi.value)) &
                (df['tema'] <= df['bb_middleband']) &  # Guard: tema below BB middle
                (df['tema'] > df['tema'].shift(1)) &  # Guard: tema is raising
                (df['volume'] > 0) &  # Make sure Volume is not 0
                (df['do_predict'] == 1) &  # Make sure Freqai is confident in the prediction
                # Only enter trade if Freqai thinks the trend is in this direction
                (df['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        df.loc[
            (
                # Signal: RSI crosses above 70
                (qtpylib.crossed_above(df['rsi'], self.short_rsi.value)) &
                (df['tema'] > df['bb_middleband']) &  # Guard: tema above BB middle
                (df['tema'] < df['tema'].shift(1)) &  # Guard: tema is falling
                (df['volume'] > 0) &  # Make sure Volume is not 0
                (df['do_predict'] == 1) &  # Make sure Freqai is confident in the prediction
                # Only enter trade if Freqai thinks the trend is in this direction
                (df['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1
        
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        return df

    def position_size(self, total_asset, leverage, stop, total_risk):
        if stop < total_risk:
            return total_asset
        else:
            return (total_asset * total_risk) / (leverage * stop)

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        previous_candle = dataframe.iloc[-2].squeeze()
        stop = previous_candle['stop_loss']
        stake = self.position_size(max_stake, leverage, stop, self.total_risk)

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        prev_candle = dataframe.iloc[-2].squeeze()

        if (current_time - timedelta(minutes=60) > trade.open_date_utc):
            if current_profit >= 0.03:
                return 0.01
            
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        current_profit = trade.calc_profit_ratio(current_candle['close'])

        if (current_time - timedelta(minutes=51) > trade.open_date_utc):
            if current_profit < 0:
                self.custom_info[pair] = {}
                if trade.is_short:
                    self.custom_info[pair]["short_reverse"] = True
                else:
                    self.custom_info[pair]["long_reverse"] = True
                self.custom_info[pair]["unlock_me"] = True
                message = f"Trade expired, changing direction for {pair}"
                self.dp.send_msg(message)
                return True

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:

        for pair in list(self.custom_info):
            if "unlock_me" in self.custom_info[pair]:
                message = f"Unlocking {pair}"
                self.dp.send_msg(message)
                self.unlock_pair(pair)
                del self.custom_info[pair]

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        if self.custom_info.get(pair):
            del self.custom_info[pair]
        return True