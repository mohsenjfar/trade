import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    # informative
)
from datetime import datetime
from typing import Optional

class RSIBreak(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    position_adjustment_enable = True

    def analyze_extrema(self, dataframe):

        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        dataframe.loc[dataframe['max_high'] == dataframe['high'],"cat"] = 'H'
        dataframe.loc[dataframe['min_low'] == dataframe['low'],"cat"] = 'L'
        dataframe['cat'] = ''.join(dataframe[dataframe.cat.notna()].cat.values)[-2:]

        last_min_index = dataframe[dataframe['min_low'] == dataframe['low']].index.max()
        last_max_index = dataframe[dataframe['max_high'] == dataframe['high']].index.max()

        dataframe['slb'] = dataframe.loc[last_max_index:].low.min()
        dataframe['ssb'] = dataframe.loc[last_min_index:].high.max()

        dataframe['slr'] = dataframe.loc[last_min_index:].low.min()
        dataframe['ssr'] = dataframe.loc[last_max_index:].high.max()

        return dataframe

    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe = self.analyze_extrema(dataframe)

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['cat'] == "LH") & # Guard
                (qtpylib.crossed_below(dataframe['rsi'], 70)) # Trigger
            ), ["enter_short" , "enter_tag"]] = (1, "reaction")

        dataframe.loc[
            (
                (dataframe['cat'] == "LH") & # Guard
                (qtpylib.crossed_above(dataframe['close'], dataframe['max_high'])) # Trigger
            ), ["enter_long" , "enter_tag"]] = (1, "break")
        
        dataframe.loc[
            (
                (dataframe['cat'] == "HL") & # Guard
                (qtpylib.crossed_above(dataframe['rsi'], 30)) # Trigger
            ), ["enter_long" , "enter_tag"]] = (1, "reaction")

        dataframe.loc[
            (
                (dataframe['cat'] == "HL") & # Guard
                (qtpylib.crossed_below(dataframe['close'], dataframe['min_low'])) # Trigger
            ), ["enter_short" , "enter_tag"]] = (1, "break")

        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        total_stake = max_stake + Trade.total_open_trades_stakes()
        if entry_tag == 'reaction': stop = last_candle.ssr if side == "short" else last_candle.slr
        else: stop = last_candle.ssb if side == "short" else last_candle.slb
        risk = abs(stop / last_candle.close - 1)
        return min(total_stake * self.trade_max_loss_allowed / risk, max_stake)


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        closed_trades = Trade.get_trades_proxy(pair=pair, is_open=False)
        if closed_trades and closed_trades[-1].enter_tag == "break": return False
        return True
    

    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]
        

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        stop = trade.get_custom_data(key='stop')
        if stop is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            if trade.enter_tag == 'reaction':
                stop = last_candle.ssr if trade.is_short else last_candle.slr
            elif trade.enter_tag == 'break':
                stop = last_candle.ssb if trade.is_short else last_candle.slb
            trade.set_custom_data(key='stop', value=stop)
            risk = abs(stop / last_candle.close - 1)
            trade.set_custom_data(key='risk', value=risk)
            self.dp.send_msg(f"Trade risk ({pair}): {risk * 100:.2f} %") 

        return stoploss_from_absolute(
            stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )


    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: float | None, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs
                              ) -> float | None | tuple[float | None, str | None]:

        risk = trade.get_custom_data(key='risk')
        if (current_profit > risk) and (trade.nr_of_successful_exits == 0):
            return - trade.stake_amount / 2
        
    
    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk')
        trade_duration = (current_time - trade.open_date_utc).seconds / 60
        conditions = (
            (trade_duration > 1440) and (current_profit < 4 * risk),
        )
        if any(conditions): return "Trade expired!"

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        conditions = (
            (trade.is_short and last_candle['rsi'] > 70),
            (not trade.is_short and last_candle['rsi'] < 30)
        )
        if any(conditions): return "Target Hit!"
