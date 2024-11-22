from pandas import DataFrame
from freqtrade.persistence import Trade
from datetime import datetime, date, timedelta
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
from freqtrade_client import FtRestClient
server_url = 'http://127.0.0.1:8080'
username = ''
password = ""
client = FtRestClient(server_url, username, password)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    use_exit_signal = False

    use_custom_stoploss = True

    startup_candle_count: int = 1440

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


    def caculate_regression(self, dataframe, kernel=1440):
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
        dataframe['last_min_peak'] = dataframe.at[min_peaks[0][-1], "low"]
        dataframe['last_max_peak'] = dataframe.at[max_peaks[0][-1], "high"]
        dataframe['h_dist'] = np.where(dataframe.extrema == 1, (dataframe.high - dataframe.upper_band), 0)
        dataframe['l_dist'] = np.where(dataframe.extrema == -1, (dataframe.lower_band - dataframe.low), 0)
        dataframe['h_ratio'] = dataframe['h_dist'] / dataframe['band_dist']
        dataframe['l_ratio'] = dataframe['l_dist'] / dataframe['band_dist']
        dataframe['l_h_ratio'] = dataframe.at[max_peaks[0][-1], "h_ratio"]
        dataframe['l_l_ratio'] = dataframe.at[min_peaks[0][-1], "l_ratio"]
        dataframe['last_max'] = dataframe.at[max_peaks[0][-1], "close"]
        dataframe['last_min'] = dataframe.at[min_peaks[0][-1], "close"]
        return dataframe


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.caculate_regression(dataframe)
        dataframe = self.calculate_extrema(dataframe)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['coef'] > 0) & # Guard
                (dataframe['close'] > dataframe['last_min']) & # Guard
                qtpylib.crossed_above(dataframe['close'], dataframe['lower_band']) # Trigger
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['coef'] < 0) & # Guard
                (dataframe['close'] < dataframe['last_max']) & # Guard
                qtpylib.crossed_below(dataframe['close'], dataframe['upper_band']) # Trigger
            ),
            'enter_short'
        ] = 1

        dataframe.to_csv('user_data/notebooks/df.csv', index=False)

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
        current_candle = dataframe.iloc[-1].squeeze()

        if side == 'short':
            risk = 1 - current_rate / current_candle.last_max
        else:
            risk = 1 - current_candle.last_min / current_rate

        if risk > (abs(self.stoploss) / 2):
            self.dp.send_msg(f"High risk trade ({risk:.2f}), stop entering {side} position")
            return None
        
        return max_stake
        

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        
        starting_balance = client.daily(1).get('data')[0].get('starting_balance')
        trades = pd.DataFrame(client.trades().get('trades'))
        if trades:
            today_loss = trades[
                (trades.close_profit_abs < 0) & 
                (trades.close_date > date.today().strftime('%Y-%m-%d'))
            ].close_profit_abs.sum().item() / starting_balance

            if (today_loss <= self.stoploss):
                self.dp.send_msg(f"Max day's loss ({today_loss:.2f}) is reached, stop trade entry ...")
                return False
            
            week_day = date.weekday(date.today())
            open_date = (date.today() - timedelta(days=week_day))
            starting_balance = client.weekly(1).get('data')[0].get('starting_balance')
            this_week_loss = trades[
                (trades.close_profit_abs < 0) & 
                (trades.close_date > open_date.strftime('%Y-%m-%d'))
            ].close_profit_abs.sum().item() / starting_balance

            if this_week_loss <= (self.stoploss * 3):
                self.dp.send_msg(f"Max week's loss ({this_week_loss:.2f}) is reached, stop trade entry ...")
                return False

            last_two_trades = trades.iloc[-2:]
            if all(last_two_trades.close_profit_abs.values < 0):
                if all(last_two_trades.is_short.values):
                    if side == 'short':
                        self.dp.send_msg(f"Two consecutive short position losses, stop entering short.")
                        return False
                if not all(last_two_trades.is_short.values):
                    if side == 'long':
                        self.dp.send_msg(f"Two consecutive long position losses, stop entering long.")
                        return False
                last_trade_close_date_str = last_two_trades.iloc[-1].squeeze().close_date
                last_trade_close_date = datetime.strptime(last_trade_close_date_str, '%Y-%m-%d %H:%M:%S')
                if ((datetime.datetime.now() - last_trade_close_date).seconds / 3600) < 12:
                    self.dp.send_msg(f"Two consecutive losses, stop entering position for 12 hours.")
                    return False
                
        return True


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            self.ob_dataframe(pair).to_csv(f'user_data/notebooks/{trade.id}_ob.csv', index=False)

        return None
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()

        if trade.is_short:
            conditions = (
                current_candle['last_max'] > current_candle['upper_band'],
                current_candle['close'] < current_candle['lower_band']
            )
            if any(conditions):
                return stoploss_from_absolute(
                    current_candle['last_max'],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            if current_candle['close'] < current_candle['middle_band']:
                return stoploss_from_absolute(
                    trade.open_rate * (1 - 0.001),
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
        else:
            conditions = (
                current_candle['last_min'] < current_candle['lower_band'],
                current_candle['close'] > current_candle['upper_band']
            )
            if any(conditions):
                return stoploss_from_absolute(
                    current_candle['last_min'],
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            if current_candle['close'] > current_candle['y']:
                return stoploss_from_absolute(
                    trade.open_rate * (1 + 0.001),
                    current_rate,
                    is_short=trade.is_short,
                    leverage=trade.leverage
                )
            
        return None