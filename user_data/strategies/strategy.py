from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone
from typing import Optional
from technical import qtpylib
import pandas as pd
from sklearn.linear_model import LinearRegression
from math import ceil
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

    timeframe = '5m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 288

    process_only_new_candles = True

    price_kernel = 2
    rsi_kernel = 2
    coef_kernel = 48

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


    def close_price_coef(self, dataframe):
        dataframe_ = dataframe.copy()[-self.coef_kernel:]
        x = dataframe_.index.values.reshape(-1, 1)
        y = dataframe_.close.values
        model = LinearRegression()
        model.fit(x, y)
        return model.coef_[0]


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        
        dataframe['coef'] = self.close_price_coef(dataframe)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

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

        dataframe['short_risk'] = abs(1 - dataframe['close'] / dataframe['price_second_last_max'])
        dataframe['long_risk'] = abs(1 - dataframe['close'] / dataframe['price_second_last_min'])

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['coef'] > 0) & # Guard
                (dataframe['price_second_last_min'] < dataframe['price_last_min']) & # Guard
                (dataframe['rsi_second_last_min'] < dataframe['rsi_last_min']) & # Guard
                (dataframe['rsi_second_last_min'] < 50) & # Guard
                (dataframe['rsi_last_min'] < 50) & # Guard
                (dataframe['close'] > dataframe['close'].shift(1)) # Trigger
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['coef'] < 0) & # Guard
                (dataframe['price_second_last_max'] > dataframe['price_last_max']) & # Guard
                (dataframe['rsi_second_last_max'] > dataframe['rsi_last_max']) & # Guard
                (dataframe['rsi_second_last_max'] > 50) & # Guard
                (dataframe['rsi_last_max'] > 50) & # Guard
                (dataframe['close'] < dataframe['close'].shift(1)) # Trigger
            ),
            'enter_short'
        ] = 1

        ticker = metadata['pair'].replace('/USDT:USDT','')
        dataframe.to_csv(f'user_data/notebooks/{ticker}_df.csv', index=False)

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    # def leverage(self, pair: str, current_time: datetime, current_rate: float,
    #              proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
    #              **kwargs) -> float:
        
    #     dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
    #     candle = dataframe.iloc[-1].squeeze()
    #     risk = candle['short_risk'] if side == 'short' else candle['long_risk']
    #     return ceil(abs(self.stoploss) / risk)


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle['short_risk'] if side == 'short' else candle['long_risk']

        trades = pd.DataFrame([vars(trade) for trade in Trade.get_trades_proxy()])
        total_stake = Trade.total_open_trades_stakes() + max_stake

        if not trades.empty and len(trades) > 1:

            today = datetime.now(timezone.utc).date()
            today_loss = trades[
                (trades.close_date >= today.strftime('%Y-%m-%d')) & 
                (trades.close_profit_abs < 0)
            ].close_profit_abs.sum() / total_stake

            open_trades = not trades[trades.is_open == True].empty
            if open_trades:
                trade = Trade.get_trades_proxy(is_open=True)[0]
                open_trade_risk = trade.get_custom_data(key='risk')
                conditions = (
                    current_time - timedelta(minutes=50) > trade.open_date_utc,
                    trade.current_profit < open_trade_risk,
                    trade.is_short != (side == 'short')
                )
                if all(conditions):
                    logger.info(f"Reverse trade, enter {side} position for {pair}")
                    return True

            if open_trades and today_loss < 0:
                logger.info(f"Open trade may result in loss, prevent {side} entry for {pair} till close.")
                return None
            
            if today_loss < self.stoploss * 0.7:
                logger.info(
                    f"Prevent entering {side} position for {pair} due to max day loss ({today_loss * 100:.2f}%)")
                return None
            
            this_week = (today - timedelta(days=today.weekday()))
            this_week_loss = trades[
                (trades.open_date >= this_week.strftime('%Y-%m-%d')) & 
                (trades.close_profit_abs < 0)
            ].close_profit_abs.sum() / total_stake

            if this_week_loss < (self.stoploss * 3):
                logger.info(
                    f"Prevent entering {side} position for {pair} due to max week loss ({this_week_loss * 100:.2f}%)")
                return None
        lines = (
            f"Pair: {pair}",
            f"Side: {side}",
            f"Risk: {risk * 100:.2f}%",
            f"Today loss: {today_loss * 100:.2f}%",
            f"This week loss: {this_week_loss * 100:.2f}%",
            f"Total stake: {total_stake:.2f}$",
            f"Proposed stake: {proposed_stake:.2f}$",
            f"Stake: {(proposed_stake * abs(self.stoploss)) / (risk * leverage):.2f}$"
        )
        self.dp.send_msg("\n".join(lines))
        
        return min((proposed_stake * abs(self.stoploss)) / (risk * leverage), proposed_stake)


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        first_close = dataframe['close'].iat[-1]
        second_close = dataframe['close'].iat[-2]
        third_close = dataframe['close'].iat[-3]

        condition_1 = (
            first_close < second_close < third_close,
            side == 'short'
        )

        condition_2 = (
            first_close > second_close > third_close,
            side == 'long'
        )

        if any((all(condition_1), all(condition_2))):
            logger.info(f"Late {side} entry for {pair}")
            return False

        return True
    

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)

        return dataframe["close"].iat[-1]


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):

            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            current_candle = dataframe.iloc[-1].squeeze()
            stop = current_candle.price_second_last_max if trade.is_short else current_candle.price_second_last_min
            trade.set_custom_data(key='stop', value=stop)
            risk = current_candle.short_risk if trade.is_short else current_candle.long_risk
            trade.set_custom_data(key='risk', value=risk)

            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
            ticker = pair.replace('/USDT:USDT','')
            self.ob_dataframe(pair).to_csv(f'user_data/notebooks/{ticker}_{trade.id}_ob.csv', index=False)
            dataframe.to_csv(f'user_data/notebooks/{ticker}_{trade.id}_df.csv', index=False)
            pd.DataFrame([vars(trade) for trade in Trade.get_trades_proxy()]).to_csv(f'user_data/notebooks/trades.csv', index=False)

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        risk = trade.get_custom_data(key='risk')
        stop = trade.get_custom_data(key='stop')
        last_extrema = current_candle.price_last_max if trade.is_short else current_candle.price_last_min
        thresh = abs(last_extrema / trade.open_rate - 1)

        if thresh >= risk * 2:
            stop = last_extrema
            trade.set_custom_data(key='stop', value=stop)

        if current_profit >= risk:
            side = -1 if trade.is_short else 1
            stop = trade.open_rate * (1 + side * 0.001)
            trade.set_custom_data(key='stop', value=stop)

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')

        conditions = (
            current_time - timedelta(minutes=60) > trade.open_date_utc,
            current_profit > 0
        )

        if all(conditions):
            return 'High risk trade!'
        
        conditions = (
            current_time - timedelta(minutes=30) > trade.open_date_utc, 
            risk * 2 < current_profit < risk * 3
        )

        if all(conditions):
            return 'Trade expired!'