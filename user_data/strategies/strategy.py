from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from technical import qtpylib
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
from scipy.signal import argrelextrema
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '5m'

    use_exit_signal = False

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
    

    def calculate_extrema(self, dataframe, kernel=6):
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
        
        return 1

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        candle = dataframe.iloc[-1].squeeze()
        risk = candle['short_risk'] if side == 'short' else candle['long_risk']

        return max(min(abs(self.stoploss) / 2 * max_stake / risk, max_stake), min_stake)
        

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        
        total_stake = self.wallets.get_total_stake_amount()
        today = datetime.now(timezone.utc).date()
        this_week = today - timedelta(days=today.weekday())
        this_week_trades = Trade.get_trades_proxy(open_date=this_week, is_open=False)
        today_trades = [trade for trade in this_week_trades if trade.close_date.date() == today]
        this_week_loss = sum(trade.close_profit_abs for trade in this_week_trades if trade.close_profit_abs < 0)
        today_loss = sum(trade.close_profit_abs for trade in today_trades if trade.close_profit_abs < 0)
        today_profit = sum(trade.close_profit_abs for trade in today_trades)
        this_week_profit = sum(trade.close_profit_abs for trade in this_week_trades)
        today_starting_balance = total_stake - today_profit
        this_week_starting_balance = total_stake - this_week_profit
        today_loss_ratio = today_loss / today_starting_balance
        this_week_loss_ratio = this_week_loss / this_week_starting_balance
        open_trades = Trade.get_open_trade_count()

        if open_trades > 0 and (today_loss_ratio + self.stoploss / 2 < self.stoploss):
            self.dp.send_msg(f"Open trade may result in loss, prevent {side} entry for {pair} till close.")
            return False

        if (today_loss_ratio <= self.stoploss):
            self.dp.send_msg(f"Max day's loss ({today_loss_ratio * 100:.2f} %) is reached, stop trade entry ...")
            return False

        if open_trades > 0 and (this_week_loss_ratio + self.stoploss / 2 < self.stoploss * 3):
            self.dp.send_msg(f"Open trade may result in loss, prevent {side} entry for {pair} till close.")
            return False
        
        if this_week_loss_ratio <= self.stoploss * 3:
            self.dp.send_msg(f"Max week's loss ({this_week_loss_ratio * 100:.2f} %) is reached, stop trade entry ...")
            return False

        if len(this_week_trades) > 1:
            last_two_trades = this_week_trades[-2:]
            if all(trade.close_profit_abs < 0 for trade in last_two_trades):
                if all(trade.is_short for trade in last_two_trades):
                    if side == 'short':
                        self.dp.send_msg(f"Two consecutive short position losses, stop entering short.")
                        return False
                if not all(trade.is_short for trade in last_two_trades):
                    if side == 'long':
                        self.dp.send_msg(f"Two consecutive long position losses, stop entering long.")
                        return False
                last_trade_close_date = last_two_trades[-1].close_date
                if ((datetime.datetime.now() - last_trade_close_date).seconds / 3600) < 12:
                    self.dp.send_msg(f"Two consecutive losses, stop entering position for 12 hours.")
                    return False
        return True


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):

            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            current_candle = dataframe.iloc[-1].squeeze()

            stop = current_candle.last_max if trade.is_short else current_candle.last_min
            trade.set_custom_data(key='stop', value=stop)

            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
            risk = current_candle['short_risk'] if trade.is_short else current_candle['long_risk']
            trade.set_custom_data(key='risk', value=risk)

            ticker = pair.replace('/USDT:USDT','')
            self.ob_dataframe(pair).to_csv(f'user_data/notebooks/{ticker}_{trade.id}_ob.csv', index=False)
            dataframe.to_csv(f'user_data/notebooks/{ticker}_{trade.id}_df.csv', index=False)

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        risk, stop = trade.get_custom_data(key='risk'), trade.get_custom_data(key='stop')

        if trade.is_short:
            max_peaks = dataframe[dataframe.last_max < stop].last_max.values
            if current_rate < current_candle.lower_band:
                stop = trade.open_rate * (1 - 0.001)
            if current_time - timedelta(minutes=240) > trade.open_date_utc:
                if (1 - current_rate / trade.open_rate) >= risk * 2:
                    stop = trade.open_rate * (1 - risk * 2)
            if max_peaks.size > 0 and (1 - max_peaks[0] / trade.open_rate) >= risk * 2:
                stop = max_peaks[0]
                trade.set_custom_data(key='stop', value=stop)
        else:
            min_peaks = dataframe[dataframe.last_min > stop].last_min.values
            if current_rate > current_candle.upper_band:
                stop = trade.open_rate * (1 + 0.001)
            if current_time - timedelta(minutes=240) > trade.open_date_utc:
                if (1 - trade.open_rate / min_peaks[0]) >= risk * 2:
                    stop = trade.open_rate * (1 + risk * 2)
            if min_peaks.size > 0 and (1 - trade.open_rate / min_peaks[0]) >= risk * 2:
                stop = min_peaks[0]
                trade.set_custom_data(key='stop', value=stop)
        
        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )