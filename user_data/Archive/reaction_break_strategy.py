# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime, timedelta, timezone
from freqtrade.persistence import Trade

from freqtrade.strategy import (
    BooleanParameter, 
    CategoricalParameter, 
    DecimalParameter,
    IStrategy, 
    IntParameter,
    stoploss_from_absolute,
    timeframe_to_prev_date
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


# This class is a sample. Feel free to customize it.
class ReactionBreakStrategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.10

    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    timeframe = '15m'

    total_risk = 0.01

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    # Hyperoptable parameters
    # buy_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)
    # sell_rsi = IntParameter(low=50, high=100, default=70, space='sell', optimize=True, load=True)
    # short_rsi = IntParameter(low=51, high=100, default=70, space='sell', optimize=True, load=True)
    # exit_short_rsi = IntParameter(low=1, high=50, default=30, space='buy', optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': True
    }

    # Optional order time in force.
    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    plot_config = {
        'main_plot': {
            'tema': {},
            'sar': {'color': 'white'},
        },
        'subplots': {
            "MACD": {
                'macd': {'color': 'blue'},
                'macdsignal': {'color': 'orange'},
            },
            "RSI": {
                'rsi': {'color': 'red'},
            }
        }
    }


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

    def informative_pairs(self):

        return [
            # ("ETH/USDT", "15m"),
            # ("BTC/USDT", "15m"),
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['open'] < dataframe['close'])
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['open'] > dataframe['close'])
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

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

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        previous_candle = dataframe.iloc[-1].squeeze()
        if previous_candle['date'] + timedelta(seconds=910) > current_time:
            return True

        return False

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
        prev_trade_dataframe = dataframe.loc[dataframe['date'] < trade_date]
        prev_trade_candle = prev_trade_dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.is_short:
            open_stop = stoploss_from_absolute(
                prev_trade_candle['high'],
                prev_trade_candle['close'],
                is_short=trade.is_short,
                leverage=trade.leverage
            )
            current_stop = stoploss_from_absolute(
                prev_trade_candle['high'],
                prev_candle['high'],
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        else:
            open_stop = stoploss_from_absolute(
                prev_trade_candle['low'],
                prev_trade_candle['close'],
                is_short=trade.is_short,
                leverage=trade.leverage
            )
            current_stop = stoploss_from_absolute(
                prev_trade_candle['low'],
                prev_candle['low'],
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        
        if abs(current_stop * 2) > abs(open_stop):
            self.dp.send_msg(f"Reward just reached for {pair}! trailing stop to {current_stop}")
            return current_stop

        return open_stop