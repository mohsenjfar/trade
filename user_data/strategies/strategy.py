from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone
from typing import Optional
from technical import qtpylib
import pandas as pd
import math
import os
from typing import Dict
import numpy as np
import talib.abstract as ta
from scipy.signal import argrelextrema
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_open,
    stoploss_from_absolute,
    timeframe_to_prev_date
)
import logging

logger = logging.getLogger(__name__)


class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 48

    process_only_new_candles = True

    kernel = 1

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


    def ob_dataframe(self, pair):
        ob = self.dp.orderbook(pair, maximum=200)
        bid_values = {
            'price': np.array(ob['bids'])[:,0],
            'volume': np.array(ob['bids'])[:,1],
            'side':'bid'
        }
        ask_values = {
            'price': np.array(ob['asks'])[:,0],
            'volume': np.array(ob['asks'])[:,1],
            'side':'ask'
        }
        bid_dataframe = pd.DataFrame(bid_values)
        ask_dataframe = pd.DataFrame(ask_values)
        return pd.concat((bid_dataframe,ask_dataframe))
    

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '1w') for pair in pairs]


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1w')
        min_peaks = argrelextrema(informative["low"].values, np.less_equal, order=self.kernel)
        max_peaks = argrelextrema(informative["high"].values, np.greater_equal, order=self.kernel)
        informative.loc[(informative.index.isin(min_peaks[0])),'extrema'] = informative.low
        informative.loc[(informative.index.isin(max_peaks[0])),'extrema'] = informative.high
        dataframe['last_peak'] = informative.extrema.dropna().iloc[-1]
        dataframe['last_peak_diff'] = informative.extrema.dropna().pct_change().iloc[-1]
        bins = informative.extrema.dropna().sort_values().values
        dataframe['boundries'] = pd.cut(dataframe.close, bins=bins)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['last_peak_diff'] < 0) &
                (dataframe['close'] > dataframe['last_peak'])
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['last_peak_diff'] > 0) &
                (dataframe['close'] < dataframe['last_peak'])
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        candle_open_date = timeframe_to_prev_date(self.timeframe, current_time)
        if candle_open_date + timedelta(seconds=5) < current_time:
            return None
        
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            limit = last_candle.boundries.right if side == 'short' else last_candle.boundries.left
            risk = abs(1 - last_candle.close / limit)
            today = datetime.now(timezone.utc).date()
            closed_trades = Trade.get_trades_proxy(close_date=today)
            today_loss = sum(trade.close_profit_abs for trade in closed_trades if trade.close_profit_abs < 0)
            stake_in_use = Trade.total_open_trades_stakes()
            total_stake = stake_in_use + max_stake
            today_loss_ratio = today_loss / total_stake

            if today_loss_ratio < self.stoploss:
                logger.info(f"Max day loss ({today_loss_ratio * 100:.2f}%), stop entering {side} position for {pair}")
                return None
            
            return min((proposed_stake * (abs(self.stoploss)) / 2) / (risk * leverage), proposed_stake)
        
        except Exception as e:
            logger.info(e)
            return None
    

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe["close"].iat[-1]


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            trade.set_custom_data(key='OB', value=self.ob_dataframe(pair).to_dict())

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        limit = last_candle.boundries.right if trade.is_short else last_candle.boundries.left

        return stoploss_from_absolute(
                limit,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )