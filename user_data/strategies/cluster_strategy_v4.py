from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta
# import api

from freqtrade.strategy import (
    IStrategy,
    IntParameter
)

# server_url = 'http://127.0.0.1:8080'
# username = ''
# password = "a88923695f80935a17b99e51df8275bc3440b92defa52106c0cea26ca1bf1ce1"
# client = FtRestClient(server_url, username, password)

class ClusterStrategyV4(IStrategy):
    
    ''' Specs:
    - Use 4h timeframe as cluster timeframe using 3m candles
    - Use 1m timeframe as main timeframe
    - Split cluster timeframe into 6 clusters
    - Enter long when price crosses above max price (the highest cluster border)
    - Enter short when price crosses below min price (the lowest cluster border)
    - Trail from second custer border 
    '''

    INTERFACE_VERSION = 3

    can_short: bool = True

    stoploss = -0.02

    timeframe = '15m'

    use_exit_signal = True

    use_custom_stoploss = True

    startup_candle_count: int = 2000

    cluster_timeframe = '1d'

    cluster_size = IntParameter(20, 40, default=30, space="buy")

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

    def cluster_borders(self, pair, n_clusters):
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=self.cluster_timeframe)
        dataframe = dataframe[dataframe.date >= '2024-03-13'].reset_index()
        X = dataframe.close.values.reshape(-1,1)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(X)
        dataframe['cluster'] = kmeans.predict(X)
        return dataframe.groupby(['cluster']).min().close.sort_values().values

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [
            (pair, self.cluster_timeframe, "futures")
            for pair in pairs
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        for val in self.cluster_size.range:
            borders = self.cluster_borders(metadata['pair'], n_clusters=val)
            for c, border in enumerate(borders):
                dataframe.loc[(dataframe.close >= border),f'cluster_{val}'] = c

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                dataframe[f'cluster_{self.cluster_size.value}'].shift(1) < dataframe[f'cluster_{self.cluster_size.value}']
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                dataframe[f'cluster_{self.cluster_size.value}'].shift(1) > dataframe[f'cluster_{self.cluster_size.value}']
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe

    # def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
    #                 current_profit: float, **kwargs):
        
    #     max_t = max(int(key) for  key in self.minimal_roi)
    #     if (current_time > trade.open_date + timedelta(minutes=max_t)) and current_profit < 0:
    #         return "Trade expired!"

    #     return None
    
    # def position_size(self, max_stake, risk, min_stake):
    #     return max(max_stake - max_stake * risk * 100 / abs(self.custom_info["total_risk"] * 100), min_stake)

    # def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
    #                         proposed_stake: float, min_stake: Optional[float], max_stake: float,
    #                         leverage: float, entry_tag: Optional[str], side: str,
    #                         **kwargs) -> float:


    #     stake = self.position_size(max_stake, abs(self.stoploss), min_stake)

    #     return stake

    # def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
    #                         time_in_force: str, current_time: datetime, entry_tag: Optional[str],
    #                         side: str, **kwargs) -> bool:

    #     trades = Trade.get_trades_proxy(pair=pair, is_open=False)
    #     if trades:
    #         return trades[-1].is_short != (side == 'short')
    #     return True

    # def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
    #                     current_rate: float, current_profit: float, after_fill: bool, 
    #                     **kwargs) -> Optional[float]:

    #     # if self.dp.runmode.value in ('live'):
    #     #     api.update_task(trade, current_time)

    #     side = -1 if trade.is_short else 1
        
    #     if current_profit > 0.01:
    #         return stoploss_from_absolute(
    #             trade.open_rate * (1 + side * (trade.fee_open + trade.fee_close)),
    #             current_rate,
    #             is_short=trade.is_short,
    #             leverage=trade.leverage
    #         )

    # def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

    #     if trade.nr_of_successful_entries == 1:
    #         trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            
    #         if self.dp.runmode.value in ('live'):
    #             task = api.create_task(trade, __class__.__name__)
    #             trade.set_custom_data(key='task_id', value=task.get('id'))
    #             self.dp.send_msg(f"Task {task.get('summary')} created")

    #     if trade.nr_of_successful_entries == 2 and self.dp.runmode.value in ('live'):
    #         task = api.complete(trade)
    #         self.dp.send_msg(f"Task {task.get('summary')} completed")

    #     return None
    
    # def bot_start(self, **kwargs) -> None:
    #     if self.dp.runmode.value in ('live'):
    #         res = api.create_parent(__class__.__name__)
    #         self.dp.send_msg(f"Parent {res.get('title')} created")