#!/bin/bash

# Adaptive Entropy Strategy Backtest Script
# Version: 2.0.0 (with test file support)
# Author: Freqtrade Custom Strategy Developer

# ============================================
# Initial Settings
# ============================================

# Color codes for beautiful output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Paths and file names
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_DATA_DIR="${SCRIPT_DIR}/user_data"
STRATEGY_NAME="AdaptiveEntropySimpleStrategy"
CONFIG_FILE="config_test.json"
DOCKER_COMPOSE_FILE="docker-compose.yml"
RESULTS_DIR="${USER_DATA_DIR}/backtest_results"
LOG_FILE="${USER_DATA_DIR}/logs/backtest_$(date +%Y%m%d_%H%M%S).log"

# Create only log directory (other directories already exist)
mkdir -p "${USER_DATA_DIR}/logs"
mkdir -p "${RESULTS_DIR}"

# ============================================
# Helper Functions
# ============================================

print_banner() {
    clear
    echo -e "${CYAN}"
    cat << "EOF"
    ╔══════════════════════════════════════════════════════════╗
    ║     Adaptive Entropy Strategy - Backtest Automation      ║
    ║         Advanced Market Regime Detection System          ║
    ║                    (Test Mode)                           ║
    ╚══════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
    echo -e "${YELLOW}Start time: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${GREEN}Config file: ${CONFIG_FILE}${NC}"
    echo -e "${GREEN}Docker compose file: ${DOCKER_COMPOSE_FILE}${NC}"
    echo -e "${BLUE}=========================================${NC}\n"
}

log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "INFO") echo -e "${GREEN}[INFO]${NC} ${message}" ;;
        "WARN") echo -e "${YELLOW}[WARN]${NC} ${message}" ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} ${message}" ;;
        "DEBUG") echo -e "${PURPLE}[DEBUG]${NC} ${message}" ;;
        "STEP") echo -e "${CYAN}[STEP]${NC} ${message}" ;;
        "MENU") echo -e "${BLUE}[MENU]${NC} ${message}" ;;
        *) echo -e "${message}" ;;
    esac
    
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

check_docker() {
    log "STEP" "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        log "ERROR" "Docker is not installed!"
        log "INFO" "To install Docker, run:"
        log "INFO" "curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log "WARN" "docker-compose not found, using docker compose instead"
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
    
    # Add -f flag to use specific file
    DOCKER_COMPOSE="${DOCKER_COMPOSE} -f ${DOCKER_COMPOSE_FILE}"
    
    log "INFO" "Docker is ready ✓"
    log "INFO" "Docker command: ${DOCKER_COMPOSE}"
}

check_strategy() {
    log "STEP" "Checking strategy file..."
    
    STRATEGY_FILE="${USER_DATA_DIR}/strategies/${STRATEGY_NAME}.py"
    
    if [ ! -f "$STRATEGY_FILE" ]; then
        log "ERROR" "Strategy file not found: $STRATEGY_FILE"
        log "INFO" "Please place your strategy file in user_data/strategies/"
        
        echo -e "\n${YELLOW}Do you want to create a sample strategy file? (y/n)${NC}"
        read -p "> " create_sample
        if [[ "$create_sample" =~ ^[Yy]$ ]]; then
            create_sample_strategy
        else
            exit 1
        fi
    else
        log "INFO" "Strategy ${STRATEGY_NAME} found ✓"
    fi
}

create_sample_strategy() {
    log "INFO" "Creating sample strategy file..."
    
    cat > "$STRATEGY_FILE" << 'EOF'
# strategy_adaptive_entropy.py
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame

class AdaptiveEntropySimpleStrategy(IStrategy):
    """
    Simple adaptive strategy for market regime detection using entropy
    """
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True
    stoploss = -0.05
    trailing_stop = True
    
    # Optimizable parameters
    window_size = IntParameter(20, 100, default=30, space="buy")
    entropy_threshold_low = IntParameter(10, 30, default=20, space="buy")
    rsi_buy_threshold = IntParameter(25, 45, default=30, space="buy")
    rsi_sell_threshold = IntParameter(55, 75, default=70, space="sell")
    
    def calculate_entropy(self, returns, bins=10):
        """Calculate entropy of a returns series"""
        if len(returns) < 5:
            return 0
        
        hist, _ = np.histogram(returns, bins=bins, density=True)
        hist = hist[hist > 0]
        
        if len(hist) == 0:
            return 0
        
        entropy = -np.sum(hist * np.log2(hist))
        return entropy
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate returns
        dataframe['returns'] = dataframe['close'].pct_change()
        
        # Calculate entropy for the specified window
        dataframe['entropy'] = 0.0
        
        # Use current window_size
        current_window = self.window_size.value
        
        for i in range(current_window, len(dataframe)):
            window_returns = dataframe['returns'].iloc[i-current_window:i]
            window_returns = window_returns.dropna()
            
            if len(window_returns) > 5:
                entropy = self.calculate_entropy(window_returns)
                dataframe.loc[dataframe.index[i], 'entropy'] = entropy
        
        # Technical indicators
        dataframe['rsi'] = ta.RSI(dataframe, length=14)
        
        # Bollinger Bands
        bb = ta.BBANDS(dataframe, length=20)
        dataframe['bb_lowerband'] = bb['bb_lowerband']
        dataframe['bb_upperband'] = bb['bb_upperband']
        dataframe['bb_middleband'] = bb['bb_middleband']
        
        # Moving average
        dataframe['ema_50'] = ta.EMA(dataframe, length=50)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Buy signal in trending regime (low entropy)
        dataframe.loc[
            (
                (dataframe['entropy'] < self.entropy_threshold_low.value) &
                (dataframe['rsi'] < self.rsi_buy_threshold.value) &
                (dataframe['close'] < dataframe['bb_lowerband']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        
        # Sell signal in ranging regime (high entropy)
        dataframe.loc[
            (
                (dataframe['entropy'] >= self.entropy_threshold_low.value) &
                (dataframe['rsi'] > self.rsi_sell_threshold.value) &
                (dataframe['close'] > dataframe['bb_upperband']) &
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit signals
        dataframe.loc[
            (dataframe['rsi'] > 75),
            'exit_long'] = 1
        
        dataframe.loc[
            (dataframe['rsi'] < 25),
            'exit_short'] = 1
        
        return dataframe
EOF
    
    log "INFO" "Sample strategy file created ✓"
}

check_config() {
    log "STEP" "Checking configuration file..."
    
    if [ ! -f "${SCRIPT_DIR}/${CONFIG_FILE}" ]; then
        log "WARN" "Configuration file ${CONFIG_FILE} not found."
        
        echo -e "\n${YELLOW}Do you want to create a sample config file? (y/n)${NC}"
        read -p "> " create_config
        if [[ "$create_config" =~ ^[Yy]$ ]]; then
            create_sample_config
        else
            log "ERROR" "Configuration file is required to continue!"
            exit 1
        fi
    else
        log "INFO" "Configuration file ${CONFIG_FILE} found ✓"
    fi
}

create_sample_config() {
    log "INFO" "Creating sample configuration file..."
    
    cat > "${SCRIPT_DIR}/${CONFIG_FILE}" << EOF
{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.99,
    "timeframe": "1h",
    "dry_run": true,
    "dry_run_wallet": 10000,
    "cancel_open_orders_on_exit": false,
    "exchange": {
        "name": "binance",
        "key": "your-api-key",
        "secret": "your-api-secret",
        "ccxt_config": {
            "enableRateLimit": true
        },
        "pair_whitelist": [
            "BTC/USDT:USDT",
            "ETH/USDT:USDT",
            "BNB/USDT:USDT"
        ]
    },
    "pairlists": [
        {"method": "StaticPairList"}
    ],
    "telegram": {
        "enabled": false,
        "token": "",
        "chat_id": ""
    }
}
EOF
    
    log "INFO" "Sample configuration file created ✓"
    log "WARN" "Please add your API Key to ${CONFIG_FILE} later"
}

run_download_data() {
    local pairs=$1
    local timeframe=$2
    local days=$3
    
    log "STEP" "Downloading historical data for ${pairs} (timeframe: ${timeframe})..."
    
    # Convert comma-separated string to array
    IFS=',' read -ra PAIR_ARRAY <<< "$pairs"
    
    for pair in "${PAIR_ARRAY[@]}"; do
        log "INFO" "Downloading ${pair}..."
        
        $DOCKER_COMPOSE run --rm freqtrade download-data \
            --exchange bybit \
            -t "$timeframe" \
            -p "$pair" \
            --days "$days" \
            --userdir /freqtrade/user_data
        
        if [ $? -ne 0 ]; then
            log "WARN" "Error downloading ${pair}, continuing..."
        fi
    done
    
    log "INFO" "Data download completed successfully ✓"
}

run_backtest() {
    local timerange=$1
    local pairs=$2
    local timeframe=$3
    local result_file="${RESULTS_DIR}/backtest_${timerange//:/_}_$(date +%Y%m%d_%H%M%S).json"
    
    log "STEP" "Running backtest for timerange ${timerange}..."
    
    $DOCKER_COMPOSE run --rm freqtrade backtesting \
        --strategy "$STRATEGY_NAME" \
        --config "/freqtrade/user_data/${CONFIG_FILE}" \
        --timerange "$timerange" \
        --timeframe "$timeframe" \
        --pairs "$pairs" \
        --export trades \
        --export-filename "$result_file" \
        --cache none \
        --breakdown day week month \
        --userdir /freqtrade/user_data 2>&1 | tee -a "$LOG_FILE"
    
    local backtest_exit_code=${PIPESTATUS[0]}
    
    if [ $backtest_exit_code -eq 0 ]; then
        log "INFO" "Backtest completed successfully ✓"
        echo "$result_file"
    else
        log "ERROR" "Error running backtest! Exit code: $backtest_exit_code"
        return 1
    fi
}

run_hyperopt() {
    local epochs=$1
    local loss_function=$2
    local timerange=$3
    local result_file="${RESULTS_DIR}/hyperopt_${loss_function}_$(date +%Y%m%d_%H%M%S).json"
    
    log "STEP" "Running Hyperopt with ${loss_function} loss function (${epochs} epochs)..."
    
    $DOCKER_COMPOSE run --rm freqtrade hyperopt \
        --strategy "$STRATEGY_NAME" \
        --config "/freqtrade/user_data/${CONFIG_FILE}" \
        --hyperopt-loss "$loss_function" \
        --epochs "$epochs" \
        --timerange "$timerange" \
        --spaces buy sell \
        --print-all \
        --export-json "$result_file" \
        --userdir /freqtrade/user_data 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        log "INFO" "Hyperopt completed successfully ✓"
        echo "$result_file"
        
        # Display best result
        log "INFO" "Best parameters found:"
        grep "Best result" -A 5 "$LOG_FILE" | tail -6
    else
        log "ERROR" "Error running Hyperopt!"
        return 1
    fi
}

plot_results() {
    local timerange=$1
    local pairs=$2
    local timeframe=$3
    
    log "STEP" "Creating analysis charts..."
    
    IFS=',' read -ra PAIR_ARRAY <<< "$pairs"
    
    for pair in "${PAIR_ARRAY[@]}"; do
        log "INFO" "Creating chart for ${pair}..."
        
        $DOCKER_COMPOSE run --rm freqtrade plot-dataframe \
            --strategy "$STRATEGY_NAME" \
            --config "/freqtrade/user_data/../${CONFIG_FILE}" \
            --timerange "$timerange" \
            --timeframe "$timeframe" \
            --pair "$pair" \
            --export-filename "${USER_DATA_DIR}/plot_${pair//\//_}_$(date +%Y%m%d).html" \
            --userdir /freqtrade/user_data
        
        if [ $? -eq 0 ]; then
            log "INFO" "Chart for ${pair} created successfully"
        fi
    done
    
    log "INFO" "All charts created successfully ✓"
}

show_backtest_results() {
    log "STEP" "Displaying latest backtest results..."
    
    # Find the latest JSON file
    latest_file=$(ls -t "${RESULTS_DIR}"/*.json 2>/dev/null | head -1)
    
    if [ -z "$latest_file" ]; then
        log "WARN" "No result files found!"
        return
    fi
    
    log "INFO" "File: $(basename "$latest_file")"
    
    # Display results summary
    if command -v jq &> /dev/null; then
        echo -e "\n${CYAN}════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}           Backtest Results Summary${NC}"
        echo -e "${CYAN}════════════════════════════════════════════${NC}"
        
        # Extract statistics with jq
        total_trades=$(jq '.total_trades // "N/A"' "$latest_file" 2>/dev/null)
        profit_total=$(jq '.profit_total // 0' "$latest_file" 2>/dev/null)
        profit_total_pct=$(echo "$profit_total * 100" | bc 2>/dev/null || echo "0")
        win_rate=$(jq '.win_rate // 0' "$latest_file" 2>/dev/null)
        win_rate_pct=$(echo "$win_rate * 100" | bc 2>/dev/null || echo "0")
        max_drawdown=$(jq '.max_drawdown // 0' "$latest_file" 2>/dev/null)
        max_drawdown_pct=$(echo "$max_drawdown * 100" | bc 2>/dev/null || echo "0")
        
        echo -e "${GREEN}Total Trades:${NC} $total_trades"
        echo -e "${GREEN}Total Profit:${NC} ${profit_total_pct}%"
        echo -e "${GREEN}Win Rate:${NC} ${win_rate_pct}%"
        echo -e "${GREEN}Max Drawdown:${NC} ${max_drawdown_pct}%"
        
        # Calculate profit factor
        if [ "$total_trades" != "N/A" ] && [ "$total_trades" -gt 0 ]; then
            avg_profit=$(echo "scale=2; $profit_total_pct / $total_trades" | bc 2>/dev/null)
            echo -e "${GREEN}Avg Profit per Trade:${NC} ${avg_profit}%"
        fi
        
        echo -e "${CYAN}════════════════════════════════════════════${NC}"
    else
        log "WARN" "jq is not installed, showing raw file:"
        cat "$latest_file" | head -20
        echo -e "\n${YELLOW}... (file continues)${NC}"
    fi
}

# ============================================
# Main Menu
# ============================================

show_menu() {
    echo -e "\n${CYAN}════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}        Adaptive Strategy Main Menu${NC}"
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}1)${NC} 📥 Download Historical Data"
    echo -e "  ${GREEN}2)${NC} 📊 Run Simple Backtest"
    echo -e "  ${GREEN}3)${NC} 🔄 Download Data + Backtest"
    echo -e "  ${GREEN}4)${NC} 🎯 Run Hyperopt (Optimization)"
    echo -e "  ${GREEN}5)${NC} 📈 Create Charts"
    echo -e "  ${GREEN}6)${NC} 📋 Show Latest Backtest Results"
    echo -e "  ${GREEN}7)${NC} 🔧 Advanced Settings"
    echo -e "  ${GREEN}8)${NC} 🚀 Run Backtest on Multiple Timeframes"
    echo -e "  ${GREEN}9)${NC} 📊 Complete Backtest with Analysis"
    echo -e "  ${GREEN}0)${NC} ❌ Exit"
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
}

show_advanced_menu() {
    echo -e "\n${PURPLE}════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}           Advanced Settings${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}1)${NC} Change Strategy Name"
    echo -e "  ${GREEN}2)${NC} Change Config File"
    echo -e "  ${GREEN}3)${NC} Change Docker Compose File"
    echo -e "  ${GREEN}4)${NC} Clear Cache"
    echo -e "  ${GREEN}5)${NC} Show Logs"
    echo -e "  ${GREEN}6)${NC} Return to Main Menu"
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
}

handle_advanced_menu() {
    while true; do
        show_advanced_menu
        read -p "Your choice [1-6]: " adv_choice
        
        case $adv_choice in
            1)
                read -p "New strategy name: " STRATEGY_NAME
                log "INFO" "Strategy name changed to ${STRATEGY_NAME}"
                ;;
            2)
                read -p "New config file name: " CONFIG_FILE
                log "INFO" "Config file changed to ${CONFIG_FILE}"
                check_config
                ;;
            3)
                read -p "New docker compose file name: " DOCKER_COMPOSE_FILE
                log "INFO" "Docker compose file changed to ${DOCKER_COMPOSE_FILE}"
                DOCKER_COMPOSE="docker-compose -f ${DOCKER_COMPOSE_FILE}"
                ;;
            4)
                log "STEP" "Clearing cache..."
                rm -rf "${USER_DATA_DIR}/hyperopt_results"/*
                rm -rf "${USER_DATA_DIR}/backtest_results"/*
                log "INFO" "Cache cleared"
                ;;
            5)
                log "STEP" "Showing latest logs..."
                tail -50 "$LOG_FILE"
                ;;
            6)
                break
                ;;
            *)
                log "ERROR" "Invalid choice!"
                ;;
        esac
        
        echo -e "\n${BLUE}Press Enter to continue...${NC}"
        read
    done
}

# ============================================
# Main Execution
# ============================================

main() {
    print_banner
    check_docker
    check_strategy
    check_config
    
    # Default settings
    DEFAULT_PAIRS="BTC/USDT:USDT,ETH/USDT:USDT"
    DEFAULT_TIMEFRAME="1h"
    DEFAULT_TIMERANGE="20250101-"
    
    while true; do
        show_menu
        read -p "Your choice [0-9]: " choice
        
        case $choice in
            1)
                # Download data
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timeframe [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "Number of days [30]: " DAYS
                DAYS=${DAYS:-30}
                run_download_data "$PAIRS" "$TIMEFRAME" "$DAYS"
                ;;
            2)
                # Simple backtest
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timeframe [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "Timerange [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                run_backtest "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                ;;
            3)
                # Download + backtest
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timeframe [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "Days to download [30]: " DAYS
                DAYS=${DAYS:-30}
                read -p "Backtest timerange [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                run_download_data "$PAIRS" "$TIMEFRAME" "$DAYS"
                run_backtest "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                ;;
            4)
                # Hyperopt
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timeframe [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "Timerange [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                
                echo -e "\n${YELLOW}Available Loss Functions:${NC}"
                echo "  1) SharpeHyperOptLoss"
                echo "  2) SortinoHyperOptLoss"
                echo "  3) CalmarHyperOptLoss"
                echo "  4) ProfitDrawDownHyperOptLoss"
                read -p "Choose loss function [1]: " LOSS_CHOICE
                
                case $LOSS_CHOICE in
                    2) LOSS_FUNC="SortinoHyperOptLoss" ;;
                    3) LOSS_FUNC="CalmarHyperOptLoss" ;;
                    4) LOSS_FUNC="ProfitDrawDownHyperOptLoss" ;;
                    *) LOSS_FUNC="SharpeHyperOptLoss" ;;
                esac
                
                read -p "Number of Hyperopt epochs [100]: " EPOCHS
                EPOCHS=${EPOCHS:-100}
                
                run_hyperopt "$EPOCHS" "$LOSS_FUNC" "$TIMERANGE"
                ;;
            5)
                # Create charts
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timeframe [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "Timerange [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                plot_results "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                ;;
            6)
                # Show results
                show_backtest_results
                ;;
            7)
                # Advanced settings
                handle_advanced_menu
                ;;
            8)
                # Backtest on multiple timeframes
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timerange [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                
                for tf in "15m" "1h" "4h"; do
                    log "INFO" "Running backtest on timeframe $tf"
                    run_backtest "$TIMERANGE" "$PAIRS" "$tf"
                done
                ;;
            9)
                # Complete backtest
                read -p "Pairs [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "Timeframe [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "Days to download [30]: " DAYS
                DAYS=${DAYS:-30}
                read -p "Backtest timerange [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                
                # Download data
                run_download_data "$PAIRS" "$TIMEFRAME" "$DAYS"
                
                # Run backtest
                BACKTEST_FILE=$(run_backtest "$TIMERANGE" "$PAIRS" "$TIMEFRAME")
                
                # Show results
                if [ -n "$BACKTEST_FILE" ]; then
                    show_backtest_results
                    
                    # Create charts
                    echo -e "\n${YELLOW}Do you want to create charts? (y/n)${NC}"
                    read -p "> " create_plot
                    if [[ "$create_plot" =~ ^[Yy]$ ]]; then
                        plot_results "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                    fi
                fi
                ;;
            0)
                log "INFO" "Exiting program"
                echo -e "\n${GREEN}Thank you for using the backtest automation script${NC}"
                echo -e "${BLUE}Logs saved to:${NC}"
                echo -e "${YELLOW}$LOG_FILE${NC}"
                exit 0
                ;;
            *)
                log "ERROR" "Invalid choice! Please enter a number between 0 and 9"
                ;;
        esac
        
        echo -e "\n${BLUE}Press Enter to continue...${NC}"
        read
    done
}

# Run main function
main "$@"