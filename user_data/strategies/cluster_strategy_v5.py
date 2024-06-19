from pandas import DataFrame
from freqtrade.persistence import Trade
from sklearn.cluster import KMeans
from datetime import datetime, timedelta, date
# import api
from typing import Optional
from technical import qtpylib
import talib.abstract as ta

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    stoploss_from_absolute,
    informative,
    timeframe_to_prev_date
)

class ClusterStrategyV5(IStrategy):
    
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

    custom_info = {
        'max_day_not_notified': True,
        'max_week_not_notified': True,
        'total_daily_risk': 0.02
    }

    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sma_300'] = ta.SMA(dataframe, 300)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['sma_300'] = ta.SMA(dataframe, 300)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['reward'] = dataframe['atr'] * 3

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['close'] > dataframe['sma_300_1h']) &
                (qtpylib.crossed_above(dataframe['close'], dataframe['sma_300']))
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                (dataframe['close'] < dataframe['sma_300_1h']) &
                (qtpylib.crossed_below(dataframe['close'], dataframe['sma_300']))
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

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        current_candle = dataframe.iloc[-1].squeeze()
        risk = current_candle.atr / current_rate
        self.custom_info['max_stake'] = max_stake
        return max(max_stake - max_stake * risk / self.custom_info['total_daily_risk'], min_stake)
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        today_trades = Trade.get_trades_proxy(open_date = date.today())
        today_profit = sum(trade.close_profit * (trade.stake_amount / trade.get_custom_data(key='max_stake'))  for trade in today_trades)

        week_day = date.weekday(date.today())
        this_week_trades = Trade.get_trades_proxy(open_date = date.today() - timedelta(days=week_day))
        this_week_profit = sum(trade.close_profit * (trade.stake_amount / trade.get_custom_data(key='max_stake'))  for trade in this_week_trades)

        if (today_profit <= self.custom_info['total_daily_risk']):
            if self.custom_info.get('max_day_not_notified'):
                self.dp.send_msg(f"Max day's loss ({today_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_day_not_notified'] = False
            return False
        
        if this_week_profit <= self.custom_info['total_daily_risk'] * 3:
            if self.custom_info.get('max_week_not_notified'):
                self.dp.send_msg(f"Max week's loss ({this_week_profit:.2f}) is reached, stop trade entry ...")
                self.custom_info['max_week_not_notified'] = False
            return False
        
        self.custom_info['max_week_not_notified'] = True
        self.custom_info['max_day_not_notified'] = True

        return True

    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        if self.dp.runmode.value in ('live'):
            api.update_task(trade, current_time)
        
        return stoploss_from_absolute(
            trade.get_custom_data(key='stop'),
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:

        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if (trade.nr_of_successful_entries == 1) and (order.ft_order_side == trade.entry_side):
            side = 1 if trade.is_short else -1
            stop = trade.open_rate + side * last_candle.atr
            reward = trade.open_rate + side * last_candle.reward
            trade.set_custom_data(key='stop', value=stop)
            trade.set_custom_data(key='reward', value=reward)
            trade.set_custom_data(key='OB', value=self.dp.orderbook(pair=pair, maximum=200))
            trade.set_custom_data(key='max_stake', value=self.custom_info['max_stake'])
            
            if self.dp.runmode.value in ('live'):
                task = api.create_task(trade, __class__.__name__)
                trade.set_custom_data(key='task_id', value=task.get('id'))
                self.dp.send_msg(f"Task {task.get('summary')} created")

        if trade.nr_of_successful_entries == 2 and self.dp.runmode.value in ('live'):
            task = api.complete(trade)
            self.dp.send_msg(f"Task {task.get('summary')} completed")

        return None
    
    def bot_start(self, **kwargs) -> None:
        if self.dp.runmode.value in ('live'):
            res = api.create_parent(__class__.__name__)
            self.dp.send_msg(f"Parent {res.get('title')} created")