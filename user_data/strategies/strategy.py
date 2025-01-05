# importing freqtrade modules
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_absolute

# importing calculation modules
import pandas as pd
from pandas import DataFrame
import numpy as np
from scipy import stats
from scipy.signal import argrelextrema

# importing other modules
from datetime import datetime, timezone
from typing import Optional
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

    process_only_new_candles = False

    kernel, score = 1, 4

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
        return {
            'bids' : {
                'price': np.array(ob['bids'])[:,0],
                'volume': np.array(ob['bids'])[:,1],
            },
            'asks': {
                'price': np.array(ob['asks'])[:,0],
                'volume': np.array(ob['asks'])[:,1],
            }
        }
    

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '1w') for pair in pairs]


    def add_fraction(self, num, add=True, step=1):
        decimal_places = len(str(float(num)).split('.')[1])
        fraction = float(f"1e-{decimal_places}") * step
        return num + fraction * (1 if add else -1)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1w')
        ob = self.dp.orderbook(metadata['pair'], maximum=200)

        min_peaks = argrelextrema(informative["low"].values, np.less_equal, order=self.kernel)
        max_peaks = argrelextrema(informative["high"].values, np.greater_equal, order=self.kernel)
        informative.loc[(informative.index.isin(min_peaks[0])),'extrema'] = informative.low
        informative.loc[(informative.index.isin(max_peaks[0])),'extrema'] = informative.high
        bins = informative.extrema.dropna().sort_values().values
        dataframe['boundaries'] = pd.cut(dataframe.close, bins=bins)
        dataframe['left'] = dataframe.boundaries.apply(lambda x: x.left).astype(float)
        dataframe['right'] = dataframe.boundaries.apply(lambda x: x.right).astype(float)
    
        bids = pd.DataFrame(np.array(ob['bids']), columns=['price','volume'])
        short_price = bids[abs(stats.zscore(bids.volume)) > self.score].price.values[-1]
        dataframe['short_price'] = self.add_fraction(short_price, add=False)
        dataframe['short_stop'] = self.add_fraction(short_price)
        dataframe['short_risk'] = abs(1 - dataframe['short_stop'] / dataframe['short_price'])
        dataframe['bids_max'] = bids.price.max()
        dataframe['bids_min'] = bids.price.min()
        
        asks = pd.DataFrame(np.array(ob['asks']), columns=['price','volume'])
        long_price = asks[abs(stats.zscore(asks.volume)) > self.score].price.values[-1]
        dataframe['long_price'] = self.add_fraction(long_price)
        dataframe['long_stop'] = self.add_fraction(long_price, add=False)
        dataframe['long_risk'] = abs(1 - dataframe['long_price'] / dataframe['long_stop'])
        dataframe['asks_max'] = asks.price.max()
        dataframe['asks_min'] = asks.price.min()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['left'] > dataframe['bids_min']) &
                (dataframe['left'] < dataframe['bids_max'])
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['right'] > dataframe['asks_min']) &
                (dataframe['right'] < dataframe['asks_max'])
            ),
            'enter_short'
        ] = 1

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['right'] > dataframe['asks_min']) &
                (dataframe['right'] < dataframe['asks_max'])
            ),
            'exit_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['left'] > dataframe['bids_min']) &
                (dataframe['left'] < dataframe['bids_max'])
            ),
            'exit_short'
        ] = 1

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            current_candle = dataframe.iloc[-1].squeeze()
            risk = current_candle.short_risk if side == 'short' else current_candle.long_risk
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
            self.dp.send_msg(e)
            return None
    

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        return current_candle.short_price if side == "short" else current_candle.long_price


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
            current_candle = dataframe.iloc[-1].squeeze()
            stop = current_candle.short_stop if trade.is_short else current_candle.long_stop
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair, maximum=200))
    

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        stop = trade.get_custom_data(key='stop')
        return stoploss_from_absolute(
                stop,
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )