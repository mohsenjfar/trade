import json
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from datetime import datetime
from math import ceil

import numpy as np
import pandas as pd
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

from freqtrade.strategy import (
    IStrategy,
    stoploss_from_absolute,
    stoploss_from_open,
    IntParameter,
    DecimalParameter,
    informative
)
from freqtrade.persistence import Trade

# Import custom indicators
from user_data.utils.custom_indicators import CustomIndicators


class AtlasEngine(IStrategy):
    """
    Atlas Engine Strategy - Optimized for Crypto Bear Markets
    
    Features:
    - ATR-based dynamic stop loss
    - Support/Resistance level detection
    - Market regime detection
    - CVD volume analysis
    - Whale activity detection
    - Composite momentum
    """
    
    INTERFACE_VERSION = 3
    
    # =========================================================================
    # Strategy Configuration
    # =========================================================================
    
    # Timeframes
    timeframe = '5m'
    inf_tf = '1h'
    
    # Trading settings
    can_short: bool = True
    process_only_new_candles = True
    use_exit_signal = True
    use_custom_stoploss = True
    position_adjustment_enable = False
    exit_profit_only = False
    
    # Risk management
    stoploss = -0.05  # 5% default stop
    trailing_stop = False  # We use custom trailing stop
    allowed_loss = 0.015  # 1.5% risk per trade
    max_leverage = 3.0
    
    # Order types
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }
    
    # =========================================================================
    # Hyperopt Parameters
    # =========================================================================
    
    # EMA periods
    ema_short_period = IntParameter(5, 50, default=21, space='buy')
    ema_long_period = IntParameter(50, 200, default=100, space='buy')
    
    # ATR stop multipliers
    atr_stop_multiplier = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space='sell')
    atr_trail_multiplier = DecimalParameter(1.0, 3.0, default=2.0, decimals=1, space='sell')
    
    # RSI thresholds
    rsi_oversold = IntParameter(20, 40, default=30, space='buy')
    rsi_overbought = IntParameter(60, 80, default=70, space='sell')
    
    # Volume threshold
    volume_threshold = DecimalParameter(1.0, 2.0, default=1.2, decimals=1, space='buy')
    
    # Cluster multipliers
    cluster_mult_0 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, space='buy')
    cluster_mult_1 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, space='buy')
    cluster_mult_2 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, space='buy')
    cluster_mult_3 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, space='buy')
    cluster_mult_4 = DecimalParameter(0.5, 2.0, default=1.0, decimals=2, space='buy')
    
    # =========================================================================
    # Initialization
    # =========================================================================
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        
        # Initialize custom indicators
        self.custom_indicators = CustomIndicators(
            btc_dominance_pair="BTC.D",
            use_onchain_data=False
        )
        
        # Load token clusters
        self._pair_to_cluster: Dict[str, int] = {}
        self._stop_cache: Dict[str, float] = {}
        self._support_cache: Dict[str, List[float]] = {}
        
        clusters_path = Path(__file__).parent / "token_clusters.json"
        if clusters_path.exists():
            try:
                data = json.loads(clusters_path.read_text(encoding="utf-8"))
                for cluster_str, pairs in data.items():
                    cid = int(cluster_str)
                    for p in pairs:
                        self._pair_to_cluster[p] = cid
                        # Normalize for Freqtrade format
                        norm = p.replace("/USDT/USDT:", "/USDT:")
                        if norm != p:
                            self._pair_to_cluster[norm] = cid
            except Exception as e:
                print(f"Error loading clusters: {e}")
    
    # =========================================================================
    # Cluster Helpers
    # =========================================================================
    
    def _get_cluster_id(self, pair: str) -> Optional[int]:
        """Get cluster ID for a pair"""
        cid = self._pair_to_cluster.get(pair)
        if cid is not None:
            return cid
        alt = pair.replace("/USDT:", "/USDT/USDT:")
        return self._pair_to_cluster.get(alt)
    
    def _ema_period_for_cluster(self, base: int, cluster_id: Optional[int]) -> int:
        """Get EMA period adjusted for cluster"""
        if cluster_id is None:
            return base
        mult = (self.cluster_mult_0, self.cluster_mult_1, self.cluster_mult_2,
                self.cluster_mult_3, self.cluster_mult_4)[cluster_id]
        return max(1, round(base * mult.value))
    
    # =========================================================================
    # Informative Pair (Higher Timeframe)
    # =========================================================================
    
    @informative(inf_tf)
    def populate_indicators_inf(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Higher timeframe indicators for trend confirmation"""
        pair = metadata.get("pair", "")
        cid = self._get_cluster_id(pair)
        
        # EMA trend
        period = self._ema_period_for_cluster(self.ema_long_period.value * 2, cid)
        dataframe['ema_trend'] = ta.EMA(dataframe["close"], timeperiod=period)
        dataframe['ema_trend_slope'] = np.gradient(dataframe['ema_trend'])
        
        # ADX for trend strength
        dataframe['adx'] = ta.ADX(dataframe)
        dataframe['di_plus'] = ta.PLUS_DI(dataframe)
        dataframe['di_minus'] = ta.MINUS_DI(dataframe)
        
        # Volume trend
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        return dataframe
    
    # =========================================================================
    # Populate Indicators (Main Timeframe)
    # =========================================================================
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Populate all indicators"""
        pair = metadata.get("pair", "")
        cid = self._get_cluster_id(pair)
        
        # =====================================================================
        # 1. EMA Indicators
        # =====================================================================
        
        # Short EMA (for entry timing)
        period_short = self._ema_period_for_cluster(self.ema_short_period.value, cid)
        dataframe['ema_short'] = ta.EMA(dataframe["close"], timeperiod=period_short)
        dataframe['ema_short_slope'] = np.gradient(dataframe['ema_short'])
        dataframe['ema_short_accel'] = np.gradient(dataframe['ema_short_slope'])
        
        # Long EMA (for trend)
        period_long = self._ema_period_for_cluster(self.ema_long_period.value, cid)
        dataframe['ema_long'] = ta.EMA(dataframe["close"], timeperiod=period_long)
        dataframe['ema_long_slope'] = np.gradient(dataframe['ema_long'])
        
        # EMA cross signals
        dataframe['ema_cross_up'] = qtpylib.crossed_above(dataframe['ema_short'], dataframe['ema_long'])
        dataframe['ema_cross_down'] = qtpylib.crossed_below(dataframe['ema_short'], dataframe['ema_long'])
        
        # =====================================================================
        # 2. Custom Crypto Indicators
        # =====================================================================
        
        # Add all custom indicators
        dataframe = self.custom_indicators.add_all_indicators(
            dataframe=dataframe,
            pair=pair,
            btc_dom_data=None  # You can add BTC dominance data here
        )
        
        # =====================================================================
        # 3. Additional TA Indicators
        # =====================================================================
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_width'] = (dataframe['bb_upperband'] - dataframe['bb_lowerband']) / dataframe['bb_middleband']
        
        # Volume
        dataframe['volume_mean'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_mean']
        
        # =====================================================================
        # 4. Extrema Extraction
        # =====================================================================
        
        # Extract swing highs and lows
        dataframe['swing_high'] = (
            (dataframe['high'] > dataframe['high'].shift(1)) &
            (dataframe['high'] > dataframe['high'].shift(-1)) &
            (dataframe['high'] > dataframe['high'].shift(2)) &
            (dataframe['high'] > dataframe['high'].shift(-2))
        ).astype(int)
        
        dataframe['swing_low'] = (
            (dataframe['low'] < dataframe['low'].shift(1)) &
            (dataframe['low'] < dataframe['low'].shift(-1)) &
            (dataframe['low'] < dataframe['low'].shift(2)) &
            (dataframe['low'] < dataframe['low'].shift(-2))
        ).astype(int)
        
        # Store swing points
        dataframe.loc[dataframe['swing_high'] == 1, 'swing_high_price'] = dataframe['high']
        dataframe.loc[dataframe['swing_low'] == 1, 'swing_low_price'] = dataframe['low']
        
        return dataframe
    
    # =========================================================================
    # Entry Signals
    # =========================================================================
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate entry signals"""
        pair = metadata.get("pair", "")
        
        # Detect market regime
        regime = self.custom_indicators.detect_market_regime(dataframe)
        adjustments = self.custom_indicators.get_regime_adjustments(regime)
        
        # Get nearest support
        support_levels = self.custom_indicators.identify_support_levels(dataframe)
        nearest_support = support_levels[-1] if support_levels else None
        
        # =====================================================================
        # Long Entry Conditions
        # =====================================================================
        
        long_conditions = (
            # EMA cross trigger
            (dataframe['ema_cross_up'] == 1) &
            
            # Higher timeframe confirmation
            (dataframe[f'ema_trend_slope_{self.inf_tf}'] > 0) &
            (dataframe[f'adx_{self.inf_tf}'] > 20) &
            (dataframe[f'di_plus_{self.inf_tf}'] > dataframe[f'di_minus_{self.inf_tf}']) &
            
            # Volume confirmation
            (dataframe['volume_ratio'] > self.volume_threshold.value) &
            
            # Momentum confirmation
            (dataframe['composite_momentum'] > -2) &
            (dataframe['cvd_slope'] > 0) &
            
            # RSI not overbought
            (dataframe['rsi'] < self.rsi_overbought.value) &
            
            # Whale activity (optional)
            (dataframe['whale_accumulation'] >= 0) &
            
            # Price near support (in bear market)
            ((regime in ['bear_run', 'distribution']) & 
             (nearest_support is not None) & 
             (abs(dataframe['close'] - nearest_support) / dataframe['close'] < 0.02)) |
            
            # Bull market - more aggressive
            ((regime in ['bull_run', 'accumulation']) & 
             (dataframe['ema_short'] > dataframe['ema_long']))
        )
        
        # =====================================================================
        # Short Entry Conditions
        # =====================================================================
        
        short_conditions = (
            # EMA cross trigger
            (dataframe['ema_cross_down'] == 1) &
            
            # Higher timeframe confirmation
            (dataframe[f'ema_trend_slope_{self.inf_tf}'] < 0) &
            (dataframe[f'adx_{self.inf_tf}'] > 20) &
            (dataframe[f'di_plus_{self.inf_tf}'] < dataframe[f'di_minus_{self.inf_tf}']) &
            
            # Volume confirmation
            (dataframe['volume_ratio'] > self.volume_threshold.value) &
            
            # Momentum confirmation
            (dataframe['composite_momentum'] < 2) &
            (dataframe['cvd_slope'] < 0) &
            
            # RSI not oversold
            (dataframe['rsi'] > self.rsi_oversold.value) &
            
            # Whale activity (optional)
            (dataframe['whale_accumulation'] <= 0) &
            
            # Prefer short in bear markets
            ((regime in ['bear_run', 'distribution']) & 
             (dataframe['ema_short'] < dataframe['ema_long']))
        )
        
        # Apply conditions with regime preferences
        if adjustments.get('prefer_long', True):
            dataframe.loc[long_conditions, 'enter_long'] = 1
        
        if adjustments.get('prefer_short', False):
            dataframe.loc[short_conditions, 'enter_short'] = 1
        
        # Store entry info
        dataframe.loc[dataframe['enter_long'] == 1, 'entry_tag'] = 'long_signal'
        dataframe.loc[dataframe['enter_short'] == 1, 'entry_tag'] = 'short_signal'
        
        return dataframe
    
    # =========================================================================
    # Exit Signals
    # =========================================================================
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Generate exit signals"""
        
        # Long exit
        dataframe.loc[
            (
                (qtpylib.crossed_below(dataframe["ema_short"], dataframe['ema_long'])) |
                (dataframe['rsi'] > self.rsi_overbought.value) |
                (dataframe['composite_momentum'] > 5)
            ),
            "exit_long"
        ] = 1
        
        # Short exit
        dataframe.loc[
            (
                (qtpylib.crossed_above(dataframe["ema_short"], dataframe['ema_long'])) |
                (dataframe['rsi'] < self.rsi_oversold.value) |
                (dataframe['composite_momentum'] < -5)
            ),
            "exit_short"
        ] = 1
        
        return dataframe
    
    # =========================================================================
    # Custom Stop Loss - ATR Based Dynamic Stop
    # =========================================================================
    
    def custom_stoploss(self,
                       pair: str,
                       trade: Trade,
                       current_time: datetime,
                       current_rate: float,
                       current_profit: float,
                       after_fill: bool,
                       **kwargs) -> Optional[float]:
        """
        Dynamic ATR-based stoploss with trailing
        """
        # Get current dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return -0.05  # Default stop
        
        # Get or calculate initial stop
        stop_key = f"{pair}_stop"
        initial_stop = trade.get_custom_data(stop_key)
        
        if initial_stop is None:
            # Calculate dynamic stop using ATR
            side = 'short' if trade.is_short else 'long'
            initial_stop = self.custom_indicators.calculate_dynamic_stop(
                dataframe=dataframe,
                entry_price=trade.open_rate,
                side=side,
                current_profit=current_profit
            )
            trade.set_custom_data(stop_key, initial_stop)
            
            # Calculate and store risk
            risk = abs(initial_stop / trade.open_rate - 1) * trade.leverage
            trade.set_custom_data("risk", risk)
            
            # Send alert
            self.dp.send_msg(f"🛑 {pair} - Initial Stop: {initial_stop:.2f}, Risk: {risk:.2%}")
        
        # Trailing stop for profitable trades
        if current_profit > 0.01:  # 1% profit
            # Get market regime adjustments
            regime = self.custom_indicators.detect_market_regime(dataframe)
            adjustments = self.custom_indicators.get_regime_adjustments(regime)
            
            # Dynamic trailing based on profit and regime
            if current_profit > 0.05:  # 5% profit
                trail_percent = 0.5  # Lock 50% of profit
            elif current_profit > 0.03:  # 3% profit
                trail_percent = 0.6  # Lock 40% of profit
            else:
                trail_percent = adjustments.get('trail_percent', 0.7)  # Lock 30% of profit
            
            return stoploss_from_open(trail_percent * current_profit, current_profit)
        
        # Convert absolute stop to relative
        return stoploss_from_absolute(
            initial_stop,
            current_rate,
            is_short=trade.is_short,
            leverage=trade.leverage
        )
    
    # =========================================================================
    # Position Sizing and Leverage
    # =========================================================================
    
    def leverage(self,
                pair: str,
                current_time: datetime,
                current_rate: float,
                proposed_leverage: float,
                max_leverage: float,
                entry_tag: Optional[str],
                side: str,
                **kwargs) -> float:
        """
        Dynamic leverage based on market conditions
        """
        # Get market regime
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.inf_tf)
        if dataframe is not None and len(dataframe) > 0:
            regime = self.custom_indicators.detect_market_regime(dataframe)
            adjustments = self.custom_indicators.get_regime_adjustments(regime)
            max_allowed = adjustments.get('max_leverage', 3)
        else:
            max_allowed = 3
        
        # Calculate risk-based leverage
        stop = self.custom_indicators.calculate_dynamic_stop(
            dataframe=dataframe if dataframe is not None else DataFrame(),
            entry_price=current_rate,
            side=side
        )
        
        if stop is not None and not np.isnan(stop):
            risk = abs(stop / current_rate - 1)
            if risk > 0:
                lev = self.allowed_loss / risk
                return float(max(1, min(ceil(lev), max_allowed, max_leverage)))
        
        return 1.0
    
    def custom_stake_amount(self,
                           pair: str,
                           current_time: datetime,
                           current_rate: float,
                           proposed_stake: float,
                           min_stake: Optional[float],
                           max_stake: float,
                           leverage: float,
                           entry_tag: Optional[str],
                           side: str,
                           **kwargs) -> float:
        """
        Dynamic position sizing based on risk
        """
        # Get market regime adjustments
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.inf_tf)
        if dataframe is not None and len(dataframe) > 0:
            regime = self.custom_indicators.detect_market_regime(dataframe)
            adjustments = self.custom_indicators.get_regime_adjustments(regime)
            risk_multiplier = adjustments.get('risk_multiplier', 1.0)
            max_position_size = adjustments.get('max_position_size', 0.8)
        else:
            risk_multiplier = 1.0
            max_position_size = 0.8
        
        # Calculate stop-based risk
        stop = self.custom_indicators.calculate_dynamic_stop(
            dataframe=dataframe if dataframe is not None else DataFrame(),
            entry_price=current_rate,
            side=side
        )
        
        if stop is not None and not np.isnan(stop):
            risk = abs(stop / current_rate - 1)
            if risk > 0:
                # Calculate stake based on risk
                total_stake = max_stake + Trade.total_open_trades_stakes()
                stake = total_stake * self.allowed_loss * risk_multiplier / (risk * leverage)
                
                # Apply position size limits
                max_allowed_stake = max_stake * max_position_size
                stake = min(stake, max_allowed_stake)
                
                return float(max(stake, min_stake if min_stake else 0))
        
        return 0
    
    # =========================================================================
    # Trade Position Adjustment (DCA)
    # =========================================================================
    
    def adjust_trade_position(self,
                             trade: Trade,
                             current_time: datetime,
                             current_rate: float,
                             current_profit: float,
                             min_stake: float | None,
                             max_stake: float,
                             current_entry_rate: float,
                             current_exit_rate: float,
                             current_entry_profit: float,
                             current_exit_profit: float,
                             **kwargs) -> float | None | Tuple[float | None, str | None]:
        """
        DCA at support levels
        """
        # Only DCA in bear market at support levels
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        
        regime = self.custom_indicators.detect_market_regime(dataframe)
        
        # Only DCA in accumulation or bear markets
        if regime not in ['bear_run', 'accumulation']:
            return None
        
        # Check if price is at support
        support_levels = self.custom_indicators.identify_support_levels(dataframe)
        if not support_levels:
            return None
        
        nearest_support = support_levels[-1]
        distance_to_support = abs(current_rate - nearest_support) / current_rate
        
        # If price is within 1% of support and we have less than 3 entries
        if distance_to_support < 0.01 and trade.nr_of_successful_entries < 3:
            # Add 50% of initial stake
            return trade.stake_amount * 0.5
        
        return None
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def get_btc_dominance_data(self) -> Optional[DataFrame]:
        """
        Get BTC dominance data for altcoin analysis
        """
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe("BTC.D/1H", '1h')
            return dataframe
        except:
            return None
    
    def confirm_trade_entry(self,
                           pair: str,
                           current_time: datetime,
                           current_rate: float,
                           proposed_stake: float,
                           min_stake: Optional[float],
                           max_stake: float,
                           leverage: float,
                           entry_tag: Optional[str],
                           side: str,
                           **kwargs) -> bool:
        """
        Final trade confirmation
        """
        # Get market summary
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) < 10:
            return False
        
        summary = self.custom_indicators.get_indicator_summary(dataframe)
        
        # Log trade attempt
        self.dp.send_msg(
            f"📝 Attempting {side} entry for {pair}\n"
            f"Price: {current_rate:.2f}\n"
            f"Regime: {summary.get('market_regime', 'unknown')}\n"
            f"Momentum: {summary.get('momentum', 0):.2f}\n"
            f"CVD: {summary.get('cvd_status', 'neutral')}"
        )
        
        return True