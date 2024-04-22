from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta, date
from typing import Optional
from freqtrade.persistence import Trade

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute
)

class ClusterStrategyV1(IStrategy):
    
    ''' Specs:
    - Use 4h timeframe as cluster timeframe
    - Use 1m timeframe as main timeframe
    - Split cluster timeframe to 6 clusters
    - When price crosses above one cluster border open long position and put stop second border below
    - When price crosses below one cluster border open short position and put stop second border above
    - Trail after each border
    '''

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.01

    timeframe = '1m'

    max_risk = 0.02

    process_only_new_candles = False

    use_exit_signal = True

    exit_profit_only = False

    ignore_roi_if_entry_signal = False

    use_custom_stoploss = True

    position_adjustment_enable = False

    startup_candle_count: int = 240

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': True
    }

    order_time_in_force = {
        'entry': 'GTC',
        'exit': 'GTC'
    }

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 60,
                "trade_limit": 2,
                "stop_duration_candles": 60,
                "required_profit": 0.0,
                "only_per_pair": True,
                "only_per_side": False
            }
        ]

    def cluster_borders(self, pair):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe="5m")
        dataframe = dataframe[-48:]
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=6, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        return [
            ("WIF/USDT:USDT", "5m", "futures"),
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        borders = self.cluster_borders(metadata['pair'])

        for c, border in enumerate(borders):
            dataframe.loc[(dataframe.close >= border),'cluster'] = c

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) == 0) &
                (dataframe.cluster == 1)
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe.cluster.shift(1) == 5) &
                (dataframe.cluster == 4)
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    def position_size(self, max_stake, risk):

        if risk > self.max_risk:
            size = (max_stake * self.max_risk) / (risk * self.config['max_open_trades'])
        else:
            size = max_stake / self.config['max_open_trades']

        return size

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        today_trades = Trade.get_trades_proxy(
            open_date = date.today(),
            is_open=False
        ).all()
        today_losses = len(trade.realized_profit for trade in today_trades if trade.realized_profit < 0)

        week_day = date.weekday(datetime.date.today())
        this_week_trades = Trade.get_trades_proxy(
            open_date = date.today() - timedelta(days=week_day),
            is_open=False
        ).all()
        this_week_losses = len(trade.realized_profit for trade in this_week_trades if trade.realized_profit < 0)

        if (today_losses >= self.config['max_open_trades']) or (this_week_losses >= 3 * self.config['max_open_trades']):
            return None

        borders = self.cluster_borders(pair)

        if side == 'long':
            risk = 1 - borders[-1] / current_rate
        else:
            risk = borders[0] / current_rate - 1
        
        stake = self.position_size(max_stake, risk)

        return stake

    
    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        prev_candle = dataframe.iloc[-2].squeeze()

        if trade.is_short:
            if (last_candle['cluster'] == 0) & (prev_candle['cluster'] == 1):
                return 'Short exit signal'
        
        if (last_candle['cluster'] == 4) & (prev_candle['cluster'] == 5):
            return 'Long exit signal'
        
        
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        borders = self.cluster_borders(pair)

        if trade.is_short:
            return stoploss_from_absolute(
                borders[0],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        return stoploss_from_absolute(
                borders[-1],
                current_rate,
                is_short=trade.is_short,
                leverage=trade.leverage
            )

    def order_filled(self, pair: str, trade: Trade, order: 'Order', current_time: datetime, **kwargs) -> None:

        if trade.nr_of_successful_entries == 1:
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            trade.set_custom_data(key='borders', value=list(self.cluster_borders(pair)))

        return None
    
    def bot_loop_start(self, **kwargs) -> None:
        for trade in Trade.get_open_trades():
            current_borders = self.cluster_borders(trade.pair)
            borders = trade.get_custom_data(key='borders')
            if borders[-1] != list(current_borders):
                borders.append(list(current_borders))