import logging
from typing import Dict

import numpy as np  # noqa
import pandas as pd  # noqa
import talib.abstract as ta
from pandas import DataFrame
from technical import qtpylib
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone
from freqtrade.strategy import IntParameter, IStrategy, stoploss_from_absolute, timeframe_to_prev_date  # noqa
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
    timeframe = '15m'

    custom_info = {}

    @property
    def protections(self):
        trades = Trade.get_trades_proxy(
            open_date=datetime.now(timezone.utc).today(),
        )
        curdayprofit = sum(trade.close_profit for trade in trades)
        self.dp.send_msg(f"Today profit {curdayprofit}")
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "stop_duration_candles": 4,
                "required_profit": 0.0,
                "only_per_pair": False,
                "only_per_side": False
            }
        ]

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
        dataframe['&s-up_or_down'] = np.where(dataframe["close"].shift(-4) >
                                              dataframe["close"], 'up', 'down')

        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:  # noqa: C901


        dataframe = self.freqai.start(dataframe, metadata, self)

        return dataframe
    
    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        df.loc[
            (
                (df['open'] < df['close']) &
                (df['&s-up_or_down'] == 'up')
            ),
            'enter_long'] = 1

        df.loc[
            (
                (df['open'] > df['close']) &
                (df['&s-up_or_down'] == 'down')
            ),
            'enter_short'] = 1
        
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:

        return df

    def position_size(self, total_asset, risk, leverage):
        if risk > self.total_risk:
            return (total_asset * self.total_risk) / (leverage * risk * self.config['max_open_trades'])
        else:
            return total_asset / (leverage * self.config['max_open_trades'])

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        previous_candle = dataframe.iloc[-2].squeeze()

        if side == 'long':
            risk = previous_candle['high'] / previous_candle['close'] - 1
        elif side == 'short':
            risk = 1 - previous_candle['low'] / previous_candle['close']
        
        stake = self.position_size(max_stake, risk, leverage)

        return stake

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        prev_trade_dataframe = dataframe.loc[dataframe['date'] < trade_date]
        prev_trade_candle = prev_trade_dataframe.iloc[-1].squeeze()

        start = prev_trade_candle['high'] if trade.is_short else prev_trade_candle['low']

        return stoploss_from_absolute(
            start,
            prev_trade_candle['close'],
            is_short=trade.is_short,
            leverage=trade.leverage
        )
    
    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        prev_trade_dataframe = dataframe.loc[dataframe['date'] < trade_date]
        prev_trade_candle = prev_trade_dataframe.iloc[-1].squeeze()

        start = prev_trade_candle['high'] if trade.is_short else prev_trade_candle['low']

        risk = stoploss_from_absolute(
            start,
            prev_trade_candle['close'],
            is_short=trade.is_short,
            leverage=trade.leverage
        )

        if current_profit > abs(risk) * 2:
            return f"Reward for pair {pair}, exiting trade..."