import freqtrade.vendor.qtpylib.indicators as qtpylib
from pandas import DataFrame
import talib.abstract as ta
from freqtrade.persistence import Trade
from freqtrade.strategy import (
    IStrategy,
    timeframe_to_prev_date,
    stoploss_from_absolute,
    stoploss_from_open,
    informative
)
from datetime import datetime, timedelta, date
from typing import Optional

class RSICrossStrategyV3(IStrategy):

    INTERFACE_VERSION = 3

    stoploss = -1

    trade_max_loss_allowed = 0.005

    multiplexer = 1

    timeframe = '5m'

    can_short: bool = True

    process_only_new_candles = True

    use_exit_signal = True

    use_custom_stoploss = True

    position_adjustment_enable = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe['atr'] = ta.ATR(dataframe, timeperiod=4)
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['above_group'] = (dataframe['rsi'] >= 70).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] >= 70)
        dataframe['below_group'] = (dataframe['rsi'] <= 30).astype(int).diff().ne(0).cumsum() * (dataframe['rsi'] <= 30)
        dataframe['max_high'] = dataframe.groupby('above_group')['high'].transform('max')
        dataframe['min_low'] = dataframe.groupby('below_group')['low'].transform('min')
        dataframe.loc[dataframe['above_group'] == 0, 'max_high'] = None
        dataframe.loc[dataframe['below_group'] == 0, 'min_low'] = None
        dataframe = dataframe.ffill()

        return dataframe


    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        trades = Trade.get_trades_proxy(pair=metadata['pair'],is_open=False)
        if trades:
            trade = trades[-1]
            if trade.enter_tag == "break" and trade.close_profit_abs < 0:
                if trade.is_short:
                    dataframe[["enter_long" , "enter_tag"]] = (1, "reaction")
                else:
                    dataframe[["enter_short" , "enter_tag"]] = (1, "reaction")
                return dataframe

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['close'], dataframe['max_high'])
            ), ["enter_long" , "enter_tag"]] = (1, "break")

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe['close'], dataframe['min_low'])
            ), ["enter_short" , "enter_tag"]] = (1, "break")


        return dataframe


    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        return dataframe


    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:

        today_trades = Trade.get_trades_proxy(open_date = date.today(),is_open=False)
        max_loss = len(trade.close_profit_abs < 0 for trade in today_trades)
        if max_loss == 2: return False


    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        risk = dataframe['atr'].iat[-1] * self.multiplexer / current_rate
        return max(min(max_stake * self.trade_max_loss_allowed / risk, max_stake), min_stake)


    def custom_entry_price(self, pair: str, trade: Trade | None, current_time: datetime, proposed_rate: float,
                           entry_tag: str | None, side: str, **kwargs) -> float:

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        return dataframe['close'].iat[-1]


    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool, 
                        **kwargs) -> Optional[float]:

        risk = trade.get_custom_data(key='risk', default=None)
        if risk is None:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            trade_date = timeframe_to_prev_date(self.timeframe, trade.open_date_utc)
            pre_trade_date = timeframe_to_prev_date(self.timeframe, trade_date - timedelta(seconds=10))
            pre_trade_candle = dataframe.loc[dataframe['date'] == pre_trade_date].squeeze()
            risk = pre_trade_candle["atr"] * self.multiplexer / trade.open_rate
            self.dp.send_msg(f"Trade risk: {risk * 100:.2f} %")
            trade.set_custom_data(key='risk', value=risk)

        if current_profit > risk * 3:
            return stoploss_from_open(
                0,
                current_profit,
                is_short=trade.is_short,
                leverage=trade.leverage
            )
        
        return stoploss_from_open(
            -risk,
            current_profit,
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

        risk = trade.get_custom_data(key='risk', default=None)
        conditions = (
            trade.enter_tag == "break",
            current_profit > 4 * risk,
            trade.nr_of_successful_exits == 0
        )
        if all(conditions): return - trade.stake_amount / 2


    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, 
                    current_rate: float, current_profit: float, **kwargs) -> str:

        risk = trade.get_custom_data(key='risk', default=None)
        conditions = (
            trade.enter_tag == "reaction",
            current_profit > risk * 2
        )
        if all(conditions): return 'Reaction target hit'

        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        conditions = (
            trade.enter_tag == "break" and not trade.is_short and dataframe['rsi'].iat[-1] < 30,
            trade.enter_tag == "break" and trade.is_short and dataframe['rsi'].iat[-1] > 70
        )
        if any(conditions): return 'Break target hit'


    def bot_loop_start(self, **kwargs) -> None:
        pairs = self.dp.current_whitelist()
        for pair in pairs:
            if self.is_pair_locked(pair):
                self.unlock_pair(pair)
