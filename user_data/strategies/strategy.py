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
    stoploss_from_absolute,
    stoploss_from_open
)
import logging

logger = logging.getLogger(__name__)


class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 288

    process_only_new_candles = True

    price_kernel = 2
    rsi_kernel = 2

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

    custom_info = {}

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


    def correlated_pair(self, pair, thresh=0.9):
        pairs = self.dp.current_whitelist()
        tickers = {p:self.dp.get_pair_dataframe(pair=p, timeframe=self.timeframe).close for p in pairs}
        dataframe = pd.DataFrame(tickers).ffill()
        dataframe.to_csv(f'user_data/notebooks/corr_df.csv', index=False)
        series = dataframe.corr()[pair].drop(pair)
        series = series[(series == series.max()) & (series > thresh)]
        return series.index[0] if series.size > 0 else np.nan


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["corr_pair"] = self.correlated_pair(metadata['pair'], thresh=0.8)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)

        min_peaks = argrelextrema(dataframe["rsi"].values, np.less_equal, order=self.rsi_kernel)
        max_peaks = argrelextrema(dataframe["rsi"].values, np.greater_equal, order=self.rsi_kernel)

        dataframe['rsi_second_last_max'] = dataframe.at[max_peaks[0][-2], "rsi"]
        dataframe['rsi_last_max'] = dataframe.at[max_peaks[0][-1], "rsi"]
        dataframe['rsi_second_last_min'] = dataframe.at[min_peaks[0][-2], "rsi"]
        dataframe['rsi_last_min'] = dataframe.at[min_peaks[0][-1], "rsi"]

        dataframe['price_second_last_max'] = dataframe.at[max_peaks[0][-2], "high"]
        dataframe['price_last_max'] = dataframe.at[max_peaks[0][-1], "high"]
        dataframe['price_second_last_min'] = dataframe.at[min_peaks[0][-2], "low"]
        dataframe['price_last_min'] = dataframe.at[min_peaks[0][-1], "low"]

        dataframe['long_risk'] = abs(1 - dataframe['close'] / dataframe['price_second_last_min'])
        dataframe['short_risk'] = abs(1 - dataframe['close'] / dataframe['price_second_last_max'])

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        open_trade = Trade.get_trades_proxy(is_open=True)
        if open_trade:
            trade = open_trade[-1]
            if trade.get_custom_data(key='corr_pair') == metadata['pair']:
                if trade.is_short:
                    dataframe['enter_long'] = 1
                    dataframe['enter_short'] = 0
                    return dataframe
                dataframe['enter_short'] = 1
                dataframe['enter_long'] = 0
                return dataframe
            dataframe['enter_short'] = 0
            dataframe['enter_long'] = 0
            return dataframe

        dataframe.loc[
            (
                (dataframe['price_second_last_min'] < dataframe['price_last_min']) & # Guard
                (dataframe['rsi_second_last_min'] < dataframe['rsi_last_min']) & # Guard
                (dataframe['rsi_second_last_min'] < 50) & # Guard
                (dataframe['rsi_last_min'] < 50) & # Guard
                (dataframe["corr_pair"].notna()) & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['tema'])) # Trigger
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['price_second_last_max'] > dataframe['price_last_max']) & # Guard
                (dataframe['rsi_second_last_max'] > dataframe['rsi_last_max']) & # Guard
                (dataframe['rsi_second_last_max'] > 50) & # Guard
                (dataframe['rsi_last_max'] > 50) & # Guard
                (dataframe["corr_pair"].notna()) & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['tema'])) # Trigger
            ),
            'enter_short'
        ] = 1

        dataframe.to_csv(f'user_data/notebooks/{metadata['pair'][:-10]}_df.csv', index=False)

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle['short_risk'] if side == 'short' else candle['long_risk']

        today = datetime.now(timezone.utc).date()
        filters = [
            Trade.is_open.is_(False),
            Trade.close_date >= today,
            Trade.close_profit_abs < 0
        ]
        today_loss = Trade.get_trades(trade_filter=filters, include_orders=False)
        if today_loss:
            f"Prevent entering {side} position for {pair} due to max day loss"
            return None

        lines = (
            f"Pair: {pair}",
            f"Side: {side}",
            f"Risk: {risk * 100:.2f}%",
            f"Proposed stake: {proposed_stake:.2f}$",
            f"Stake: {(proposed_stake * abs(self.stoploss)) / (risk * leverage):.2f}$"
        )
        self.dp.send_msg("\n".join(lines))
        
        return min((proposed_stake * abs(self.stoploss)) / (risk * leverage), proposed_stake)
    

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)

        return dataframe["close"].iat[-1]


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):

            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            current_candle = dataframe.iloc[-1].squeeze()
            risk = current_candle.short_risk if trade.is_short else current_candle.long_risk
            trade.set_custom_data(key='risk', value=risk)
            trade.set_custom_data(key='corr_pair', value=current_candle.corr_pair)

            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
            self.ob_dataframe(pair).to_csv(f'user_data/notebooks/{pair[:-10]}_{trade.id}_ob.csv', index=False)
            dataframe.to_csv(f'user_data/notebooks/{pair[:-10]}_{trade.id}_df.csv', index=False)
            pd.DataFrame([vars(trade) for trade in Trade.get_trades_proxy()]).to_csv(f'user_data/notebooks/trades.csv', index=False)

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk')

        risk_thresh = current_profit // risk
        if risk_thresh >= 2:
            return stoploss_from_open(
                risk * (risk_thresh - 1),
                current_profit, 
                is_short=trade.is_short, 
                leverage=trade.leverage
            )

        if current_profit >= risk:
            side = -1 if trade.is_short else 1
            return stoploss_from_absolute(
                trade.open_rate * (1 + side * 0.001),
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        
        return risk


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        
        conditions = (
            current_time - timedelta(hours = 2) > trade.open_date_utc, 
            risk * 2 < current_profit < risk * 3
        )

        if all(conditions):
            return 'Trade expired!'