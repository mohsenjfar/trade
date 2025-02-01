# importing freqtrade modules
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute, stoploss_from_open

# importing calculation modules
import pandas as pd
from pandas import DataFrame
import numpy as np
from technical import qtpylib
import talib.abstract as ta
from scipy.signal import argrelextrema

# importing other modules
from datetime import datetime, timezone
from typing import Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class Strategy(IStrategy):

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'
    informative_timeframe = '4h'
    window = 4

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 48

    process_only_new_candles = True

    position_adjustment_enable = True

    notifications = defaultdict(None)

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
    

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, self.informative_timeframe) for pair in pairs]


    def shift_fraction(self, num, add=True, step=1):
        decimal_places = len(str(float(num)).split('.')[1])
        fraction = float(f"1e-{decimal_places}") * step
        return num + fraction * (1 if add else -1)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe=self.informative_timeframe)
        min_peaks = argrelextrema(informative["low"].values, np.less_equal, order=1)
        max_peaks = argrelextrema(informative["high"].values, np.greater_equal, order=1)
        informative.loc[(informative.index.isin(min_peaks[0])),'extrema'] = informative.low
        informative.loc[(informative.index.isin(max_peaks[0])),'extrema'] = informative.high
        bins = informative.extrema.dropna().drop_duplicates().values[-self.window:]
        bins = np.sort(np.append(bins, [-np.inf,np.inf]))
        
        dataframe['boundaries'] = pd.cut(dataframe.close, bins=bins, precision=4)
    
        dataframe['left'] = dataframe.boundaries.apply(lambda x: x.left).astype(float)
        dataframe['long_stop'] = dataframe.left.apply(self.shift_fraction, add=False)
        dataframe['long_trigger'] = dataframe['left'] * (1 + abs(self.stoploss)/2)
        dataframe['long_distance'] = dataframe['long_trigger'] - dataframe['long_stop']
        dataframe['long_risk'] = dataframe['long_distance'] / dataframe['long_stop']

        dataframe['right'] = dataframe.boundaries.apply(lambda x: x.right).astype(float)
        dataframe['short_stop'] = dataframe.right.apply(self.shift_fraction)
        dataframe['short_trigger'] = dataframe['right'] * (1 - abs(self.stoploss)/2)
        dataframe['short_distance'] = dataframe['short_stop'] - dataframe['short_trigger']
        dataframe['short_risk'] = dataframe['short_distance'] / dataframe['short_stop']

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe['close'], dataframe['long_trigger']))
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe['close'], dataframe['short_trigger']))
            ),
            'enter_short'
        ] = 1

        dataframe.to_csv('user_data/notebooks/out.csv', index=False)
                
        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            risk = last_candle.short_risk if side == 'short' else last_candle.long_risk
            today = datetime.now(timezone.utc).date()
            closed_trades = Trade.get_trades_proxy(close_date=today)
            today_loss = sum(trade.close_profit_abs for trade in closed_trades if trade.close_profit_abs < 0)
            stake_in_use = Trade.total_open_trades_stakes()
            total_stake = stake_in_use + max_stake
            today_loss_ratio = today_loss / total_stake

            if today_loss_ratio < self.stoploss:
                logger.info(f"Max day loss ({today_loss_ratio * 100:.2f}%), stop entering {side} position for {pair}")
                return None
            
            return min((proposed_stake * abs(self.stoploss)) / (risk * leverage), proposed_stake)
        
        except Exception as e:
            logger.warning(e)
            return None


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe.short_trigger.iat[-1] if side == 'short' else dataframe.long_trigger.iat[-1]
    

    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            risk = last_candle.short_risk if trade.is_short else last_candle.long_risk
            trade.set_custom_data(key='risk', value=risk)
            
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair, maximum=200))
    

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        if (current_profit > abs(self.stoploss)/2) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        stop = last_candle.short_stop if trade.is_short else last_candle.long_stop
        trigger = last_candle.short_trigger if trade.is_short else last_candle.long_trigger
        risk = trade.get_custom_data(key='risk')

        if current_rate > trigger:
            reward = abs(1 - trade.open_rate / stop)
            if reward > 5 * risk:
                return stoploss_from_absolute(
                        stop,
                        current_rate,
                        is_short=trade.is_short,
                        leverage=trade.leverage
                    )
        
        return stoploss_from_open(
            -risk, 
            current_profit, 
            is_short=trade.is_short, 
            leverage=trade.leverage
        )