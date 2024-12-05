from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, timedelta, timezone
from typing import Optional
from technical import qtpylib
import pandas as pd
from sklearn.linear_model import LinearRegression
from math import ceil
import numpy as np
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


    def caculate_regression(self, dataframe, kernel=288):
        dataframe_ = dataframe.copy()[-kernel:]
        x = dataframe_.index.values.reshape(-1, 1)
        y = dataframe_.close.values
        model = LinearRegression()
        model.fit(x, y)
        x = dataframe.index.values.reshape(-1, 1)
        dataframe['y'] = model.predict(x)
        dataframe['coef'] = float(model.coef_[0])
        dataframe['upper_band'] = dataframe['y'] + dataframe.high.std()
        dataframe['lower_band'] = dataframe['y'] - dataframe.low.std()
        dataframe['band_dist'] = dataframe['upper_band'] - dataframe['lower_band']
        return dataframe
    

    def calculate_extrema(self, dataframe, kernel=2):
        dataframe["extrema"] = 0
        min_peaks = argrelextrema(dataframe["low"].values, np.less_equal, order=kernel)
        max_peaks = argrelextrema(dataframe["high"].values, np.greater_equal, order=kernel)
        for mp in min_peaks[0]:
            dataframe.at[mp, "extrema"] = -1
        for mp in max_peaks[0]:
            dataframe.at[mp, "extrema"] = 1
        dataframe['last_max'] = dataframe.at[max_peaks[0][-1], "high"]
        dataframe['last_min'] = dataframe.at[min_peaks[0][-1], "low"]
        dataframe['second_last_max'] = dataframe.at[max_peaks[0][-2], "high"]
        dataframe['second_last_min'] = dataframe.at[min_peaks[0][-2], "low"]
        dataframe['short_risk'] = 1 - dataframe['close'] / dataframe['last_max']
        dataframe['long_risk'] = 1 - dataframe['last_min'] / dataframe['close']
        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.caculate_regression(dataframe)
        dataframe = self.calculate_extrema(dataframe)
        dataframe['total_stake'] = self.wallets.get_total_stake_amount()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                # (dataframe['coef'] > 0) & # Guard
                (dataframe['second_last_min'] < dataframe['last_min']) & # Guard
                # (dataframe['close'] > dataframe['last_max']) & # Guard
                # (dataframe['close'] > dataframe['second_last_max']) & # Guard
                qtpylib.crossed_above(dataframe['close'], dataframe['y']) # Trigger
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                # (dataframe['coef'] < 0) & # Guard
                (dataframe['second_last_max'] > dataframe['last_max']) & # Guard
                # (dataframe['close'] < dataframe['last_min']) & # Guard
                # (dataframe['close'] < dataframe['second_last_min']) & # Guard
                qtpylib.crossed_below(dataframe['close'], dataframe['y']) # Trigger
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle['short_risk'] if side == 'short' else candle['long_risk']
        return ceil((self.stoploss / 2) / risk)


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle['short_risk'] if side == 'short' else candle['long_risk']
        if risk > 0.02:
            logger.info(f"High risk ({risk * 100:.2f}%), prevent {side} entry for {pair}.")
            return None
        
        total_stake = candle['total_stake']

        today = datetime.now(timezone.utc).date()
        this_week = (today - timedelta(days=today.weekday()))
        trades = pd.DataFrame([vars(trade) for trade in Trade.get_trades_proxy()])

        if not trades.empty and len(trades) > 1:
            today_loss = trades[
                (trades.close_date >= today.strftime('%Y-%m-%d')) & 
                (trades.close_profit_abs < 0)
            ].close_profit_abs.sum()
            today_profit = trades[
                trades.close_date >= today.strftime('%Y-%m-%d')
            ].close_profit_abs.sum()
            today_starting_balance = total_stake - today_profit
            today_loss_ratio = today_loss / today_starting_balance

            this_week_loss = trades[
                (trades.open_date >= this_week.strftime('%Y-%m-%d')) & 
                (trades.close_profit_abs < 0)
            ].close_profit_abs.sum()
            this_week_profit = trades[
                trades.open_date >= this_week.strftime('%Y-%m-%d')
            ].close_profit_abs.sum()
            this_week_starting_balance = total_stake - this_week_profit
            this_week_loss_ratio = this_week_loss / this_week_starting_balance

            open_trades = not trades[trades.is_open == True].empty

            if open_trades and today_loss_ratio <= self.stoploss / 2:
                logger.info(f"Open trade may result in loss, prevent {side} entry for {pair} till close.")
                return None

            if today_loss_ratio <= self.stoploss:
                logger.info(
                    f"Prevent entering {side} position for {pair} due to max day loss ({today_loss_ratio * 100:.2f}%)")
                return None
            
            if this_week_loss_ratio <= self.stoploss * 3:
                logger.info(
                    f"Prevent entering {side} position for {pair} due to max week loss ({this_week_loss_ratio * 100:.2f}%)")
                return None

            if (trades.iloc[-2:].close_profit_abs < 0).all() :
                if trades.iloc[-2:].is_short.all():
                    if side == 'short':
                        logger.info(f"Two consecutive short position losses, stop entering short.")
                        return None
                if not trades.iloc[-2:].is_short.all():
                    if side == 'long':
                        logger.info(f"Two consecutive long position losses, stop entering long.")
                        return None
                last_close_date = datetime.strptime(trades.iloc[-1].close_date, "%Y-%m-%d %H:%M:%S.%f")
                if (datetime.now() - last_close_date).seconds / 3600 < 12:
                    logger.info(f"Two consecutive losses, stop entering position for 12 hours.")
                    return None
                    
            stake = today_starting_balance * ((abs(self.stoploss) / 2) / (risk * leverage))
            lines = (
                f"Pair: {pair}",
                f"Risk: {risk * 100:.2f}%",
                f"Leverage: {leverage}",
                f"Stop to risk ratio: {((abs(self.stoploss) / 2) / (risk * leverage)) * 100:.2f}%",
                f"Today starting balance: {today_starting_balance:.2f}",
                f"Stake: {stake:.2f}",
                f"Today loss ratio: {today_loss_ratio * 100:.2f}%",
                f"Today profit ratio: {(today_profit / today_starting_balance) * 100:.2f}%",
            )
            self.dp.send_msg('\n'.join(lines))
            return stake
        
        return proposed_stake

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)

        return dataframe["close"].iat[-1]


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):

            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            current_candle = dataframe.iloc[-1].squeeze()
            stop = current_candle.last_max if trade.is_short else current_candle.last_min
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
        last_extrema = current_candle.last_max if trade.is_short else current_candle.last_min
        thresh = abs(last_extrema / trade.open_rate - 1)

        if current_profit >= risk:
            side = -1 if trade.is_short else 1
            stop = trade.open_rate * (1 + 0.001 * side)

        if thresh >= risk * 2:
            stop = last_extrema
            trade.set_custom_data(key='stop', value=stop)
        
        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        dataframe = dataframe[dataframe.date >= trade.open_date_utc].reset_index()
        mean = (dataframe['high'] - dataframe['low']).mean()
        mean_to_open_ratio = mean / trade.open_rate
        risk = trade.get_custom_data(key='risk')

        lines = (
            f"Mean to open ratio {pair}: {mean_to_open_ratio:.2f}",
            f"Candles: {len(dataframe.date >= trade.open_date_utc)}"
        )
        info = "    ".join(lines)
        if pair in self.custom_info:
            if self.custom_info[pair] != info:
                self.custom_info[pair] = info
                logger.info(info)
        else:
            self.custom_info[pair] = info
            logger.info(info)

        conditions = (
            (current_time - timedelta(hours=1) > trade.open_date_utc) and current_profit < risk,
            (current_time - timedelta(hours=2) > trade.open_date_utc) and current_profit < risk * 2
        )

        if any(conditions):
            return 'Trade expired!'

        conditions = (
            current_time - timedelta(minutes=30) > trade.open_date_utc,
            mean_to_open_ratio < 1,
            abs(current_profit) < risk / 2
        )

        if all(conditions):
            return 'High risk trade!'