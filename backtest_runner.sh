#!/bin/bash

# Adaptive Entropy Strategy Backtest Script
# Version: 2.0.0 (با پشتیبانی از فایل‌های تست)
# Author: Freqtrade Custom Strategy Developer

# ============================================
# تنظیمات اولیه
# ============================================

# رنگ‌بندی برای خروجی زیباتر
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# مسیرها و نام فایل‌ها
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_DATA_DIR="${SCRIPT_DIR}/user_data"
STRATEGY_NAME="AdaptiveEntropySimpleStrategy"
CONFIG_FILE="config_test.json"
DOCKER_COMPOSE_FILE="docker-compose-test.yml"
RESULTS_DIR="${USER_DATA_DIR}/backtest_results"
LOG_FILE="${USER_DATA_DIR}/logs/backtest_$(date +%Y%m%d_%H%M%S).log"

# ایجاد دایرکتوری لاگ (فقط دایرکتوری لاگ رو ایجاد کن، بقیه وجود دارن)
mkdir -p "${USER_DATA_DIR}/logs"
mkdir -p "${RESULTS_DIR}"

# ============================================
# توابع کمکی
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
    echo -e "${YELLOW}شروع اجرا: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${GREEN}فایل پیکربندی: ${CONFIG_FILE}${NC}"
    echo -e "${GREEN}فایل داکر کامپوز: ${DOCKER_COMPOSE_FILE}${NC}"
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
    log "STEP" "بررسی نصب Docker..."
    
    if ! command -v docker &> /dev/null; then
        log "ERROR" "Docker نصب نیست!"
        log "INFO" "برای نصب Docker دستور زیر را اجرا کنید:"
        log "INFO" "curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log "WARN" "docker-compose یافت نشد، از docker compose استفاده می‌کنیم"
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
    
    # اضافه کردن گزینه -f برای استفاده از فایل خاص
    DOCKER_COMPOSE="${DOCKER_COMPOSE} -f ${DOCKER_COMPOSE_FILE}"
    
    log "INFO" "Docker آماده است ✓"
    log "INFO" "دستور داکر: ${DOCKER_COMPOSE}"
}

check_strategy() {
    log "STEP" "بررسی فایل استراتژی..."
    
    STRATEGY_FILE="${USER_DATA_DIR}/strategies/${STRATEGY_NAME}.py"
    
    if [ ! -f "$STRATEGY_FILE" ]; then
        log "ERROR" "فایل استراتژی یافت نشد: $STRATEGY_FILE"
        log "INFO" "لطفاً فایل استراتژی را در مسیر user_data/strategies/ قرار دهید"
        
        echo -e "\n${YELLOW}آیا می‌خواهید فایل استراتژی نمونه ایجاد شود؟ (y/n)${NC}"
        read -p "> " create_sample
        if [[ "$create_sample" =~ ^[Yy]$ ]]; then
            create_sample_strategy
        else
            exit 1
        fi
    else
        log "INFO" "استراتژی ${STRATEGY_NAME} یافت شد ✓"
    fi
}

create_sample_strategy() {
    log "INFO" "ایجاد فایل استراتژی نمونه..."
    
    cat > "$STRATEGY_FILE" << 'EOF'
# strategy_adaptive_entropy.py
import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame

class AdaptiveEntropySimpleStrategy(IStrategy):
    """
    استراتژی تطبیقی ساده برای تشخیص رژیم بازار با آنتروپی
    """
    INTERFACE_VERSION = 3
    timeframe = '1h'
    can_short = True
    stoploss = -0.05
    trailing_stop = True
    
    # پارامترهای قابل بهینه‌سازی
    window_size = IntParameter(20, 100, default=30, space="buy")
    entropy_threshold_low = IntParameter(10, 30, default=20, space="buy")
    rsi_buy_threshold = IntParameter(25, 45, default=30, space="buy")
    rsi_sell_threshold = IntParameter(55, 75, default=70, space="sell")
    
    def calculate_entropy(self, returns, bins=10):
        """محاسبه آنتروپی یک سری بازدهی"""
        if len(returns) < 5:
            return 0
        
        hist, _ = np.histogram(returns, bins=bins, density=True)
        hist = hist[hist > 0]
        
        if len(hist) == 0:
            return 0
        
        entropy = -np.sum(hist * np.log2(hist))
        return entropy
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # محاسبه بازدهی
        dataframe['returns'] = dataframe['close'].pct_change()
        
        # محاسبه آنتروپی در پنجره مشخص
        dataframe['entropy'] = 0.0
        
        # استفاده از window_size فعلی
        current_window = self.window_size.value
        
        for i in range(current_window, len(dataframe)):
            window_returns = dataframe['returns'].iloc[i-current_window:i]
            window_returns = window_returns.dropna()
            
            if len(window_returns) > 5:
                entropy = self.calculate_entropy(window_returns)
                dataframe.loc[dataframe.index[i], 'entropy'] = entropy
        
        # اندیکاتورهای تکنیکال
        dataframe['rsi'] = ta.RSI(dataframe, length=14)
        
        # باند بولینگر
        bb = ta.BBANDS(dataframe, length=20)
        dataframe['bb_lowerband'] = bb['bb_lowerband']
        dataframe['bb_upperband'] = bb['bb_upperband']
        dataframe['bb_middleband'] = bb['bb_middleband']
        
        # میانگین متحرک
        dataframe['ema_50'] = ta.EMA(dataframe, length=50)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # سیگنال خرید در رژیم روندی (آنتروپی پایین)
        dataframe.loc[
            (
                (dataframe['entropy'] < self.entropy_threshold_low.value) &
                (dataframe['rsi'] < self.rsi_buy_threshold.value) &
                (dataframe['close'] < dataframe['bb_lowerband']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        
        # سیگنال فروش در رژیم رنج (آنتروپی بالا)
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
        # خروج از معامله
        dataframe.loc[
            (dataframe['rsi'] > 75),
            'exit_long'] = 1
        
        dataframe.loc[
            (dataframe['rsi'] < 25),
            'exit_short'] = 1
        
        return dataframe
EOF
    
    log "INFO" "فایل استراتژی نمونه ایجاد شد ✓"
}

check_config() {
    log "STEP" "بررسی فایل پیکربندی..."
    
    if [ ! -f "${SCRIPT_DIR}/${CONFIG_FILE}" ]; then
        log "WARN" "فایل ${CONFIG_FILE} یافت نشد."
        
        echo -e "\n${YELLOW}آیا می‌خواهید فایل پیکربندی نمونه ایجاد شود؟ (y/n)${NC}"
        read -p "> " create_config
        if [[ "$create_config" =~ ^[Yy]$ ]]; then
            create_sample_config
        else
            log "ERROR" "فایل پیکربندی برای ادامه کار ضروری است!"
            exit 1
        fi
    else
        log "INFO" "فایل پیکربندی ${CONFIG_FILE} یافت شد ✓"
    fi
}

create_sample_config() {
    log "INFO" "ایجاد فایل پیکربندی نمونه..."
    
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
            "BTC/USDT",
            "ETH/USDT",
            "BNB/USDT"
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
    
    log "INFO" "فایل پیکربندی نمونه ایجاد شد ✓"
    log "WARN" "لطفاً بعداً API Key خود را در فایل ${CONFIG_FILE} وارد کنید"
}

run_download_data() {
    local pairs=$1
    local timeframe=$2
    local days=$3
    
    log "STEP" "دانلود داده‌های تاریخی برای ${pairs} (تایم‌فریم: ${timeframe})..."
    
    # تبدیل رشته کاما-مجزا به آرایه
    IFS=',' read -ra PAIR_ARRAY <<< "$pairs"
    
    for pair in "${PAIR_ARRAY[@]}"; do
        log "INFO" "در حال دانلود ${pair}..."
        
        $DOCKER_COMPOSE run --rm freqtrade download-data \
            --exchange binance \
            -t "$timeframe" \
            -p "$pair" \
            --days "$days" \
            --userdir /freqtrade/user_data
        
        if [ $? -ne 0 ]; then
            log "WARN" "خطا در دانلود ${pair}، ادامه می‌دهیم..."
        fi
    done
    
    log "INFO" "دانلود داده‌ها با موفقیت انجام شد ✓"
}

run_backtest() {
    local timerange=$1
    local pairs=$2
    local timeframe=$3
    local result_file="${RESULTS_DIR}/backtest_${timerange//:/_}_$(date +%Y%m%d_%H%M%S).json"
    
    log "STEP" "اجرای بکتست برای بازه زمانی ${timerange}..."
    
    $DOCKER_COMPOSE run --rm freqtrade backtesting \
        --strategy "$STRATEGY_NAME" \
        --config "/freqtrade/user_data/../${CONFIG_FILE}" \
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
        log "INFO" "بکتست با موفقیت انجام شد ✓"
        echo "$result_file"
    else
        log "ERROR" "خطا در اجرای بکتست! کد خطا: $backtest_exit_code"
        return 1
    fi
}

run_hyperopt() {
    local epochs=$1
    local loss_function=$2
    local timerange=$3
    local result_file="${RESULTS_DIR}/hyperopt_${loss_function}_$(date +%Y%m%d_%H%M%S).json"
    
    log "STEP" "اجرای Hyperopt با تابع زیان ${loss_function} (${epochs} دوره)..."
    
    $DOCKER_COMPOSE run --rm freqtrade hyperopt \
        --strategy "$STRATEGY_NAME" \
        --config "/freqtrade/user_data/../${CONFIG_FILE}" \
        --hyperopt-loss "$loss_function" \
        --epochs "$epochs" \
        --timerange "$timerange" \
        --spaces buy sell \
        --print-all \
        --export-json "$result_file" \
        --userdir /freqtrade/user_data 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        log "INFO" "Hyperopt با موفقیت انجام شد ✓"
        echo "$result_file"
        
        # نمایش بهترین نتیجه
        log "INFO" "بهترین پارامترهای یافت شده:"
        grep "Best result" -A 5 "$LOG_FILE" | tail -6
    else
        log "ERROR" "خطا در اجرای Hyperopt!"
        return 1
    fi
}

plot_results() {
    local timerange=$1
    local pairs=$2
    local timeframe=$3
    
    log "STEP" "ایجاد نمودارهای تحلیلی..."
    
    IFS=',' read -ra PAIR_ARRAY <<< "$pairs"
    
    for pair in "${PAIR_ARRAY[@]}"; do
        log "INFO" "ایجاد نمودار برای ${pair}..."
        
        $DOCKER_COMPOSE run --rm freqtrade plot-dataframe \
            --strategy "$STRATEGY_NAME" \
            --config "/freqtrade/user_data/../${CONFIG_FILE}" \
            --timerange "$timerange" \
            --timeframe "$timeframe" \
            --pair "$pair" \
            --export-filename "${USER_DATA_DIR}/plot_${pair//\//_}_$(date +%Y%m%d).html" \
            --userdir /freqtrade/user_data
        
        if [ $? -eq 0 ]; then
            log "INFO" "نمودار ${pair} با موفقیت ایجاد شد"
        fi
    done
    
    log "INFO" "تمام نمودارها با موفقیت ایجاد شدند ✓"
}

show_backtest_results() {
    log "STEP" "نمایش آخرین نتایج بکتست..."
    
    # پیدا کردن آخرین فایل JSON
    latest_file=$(ls -t "${RESULTS_DIR}"/*.json 2>/dev/null | head -1)
    
    if [ -z "$latest_file" ]; then
        log "WARN" "هیچ فایل نتیجه‌ای یافت نشد!"
        return
    fi
    
    log "INFO" "فایل: $(basename "$latest_file")"
    
    # نمایش خلاصه نتایج
    if command -v jq &> /dev/null; then
        echo -e "\n${CYAN}════════════════════════════════════════════${NC}"
        echo -e "${YELLOW}            خلاصه نتایج بکتست${NC}"
        echo -e "${CYAN}════════════════════════════════════════════${NC}"
        
        # استخراج آمار با jq
        total_trades=$(jq '.total_trades // "نامشخص"' "$latest_file" 2>/dev/null)
        profit_total=$(jq '.profit_total // 0' "$latest_file" 2>/dev/null)
        profit_total_pct=$(echo "$profit_total * 100" | bc 2>/dev/null || echo "0")
        win_rate=$(jq '.win_rate // 0' "$latest_file" 2>/dev/null)
        win_rate_pct=$(echo "$win_rate * 100" | bc 2>/dev/null || echo "0")
        max_drawdown=$(jq '.max_drawdown // 0' "$latest_file" 2>/dev/null)
        max_drawdown_pct=$(echo "$max_drawdown * 100" | bc 2>/dev/null || echo "0")
        
        echo -e "${GREEN}تعداد کل معاملات:${NC} $total_trades"
        echo -e "${GREEN}سود کل:${NC} ${profit_total_pct}%"
        echo -e "${GREEN}وین‌ریت:${NC} ${win_rate_pct}%"
        echo -e "${GREEN}حداکثر Drawdown:${NC} ${max_drawdown_pct}%"
        
        # محاسبه فاکتور سود
        if [ "$total_trades" != "نامشخص" ] && [ "$total_trades" -gt 0 ]; then
            avg_profit=$(echo "scale=2; $profit_total_pct / $total_trades" | bc 2>/dev/null)
            echo -e "${GREEN}میانگین سود هر معامله:${NC} ${avg_profit}%"
        fi
        
        echo -e "${CYAN}════════════════════════════════════════════${NC}"
    else
        log "WARN" "jq نصب نیست، نمایش فایل خام:"
        cat "$latest_file" | head -20
        echo -e "\n${YELLOW}... (ادامه فایل)${NC}"
    fi
}

# ============================================
# منوی اصلی
# ============================================

show_menu() {
    echo -e "\n${CYAN}════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}            منوی اصلی استراتژی تطبیقی${NC}"
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}1)${NC} 📥 دانلود داده‌های تاریخی"
    echo -e "  ${GREEN}2)${NC} 📊 اجرای بکتست ساده"
    echo -e "  ${GREEN}3)${NC} 🔄 دانلود داده + بکتست"
    echo -e "  ${GREEN}4)${NC} 🎯 اجرای Hyperopt (بهینه‌سازی)"
    echo -e "  ${GREEN}5)${NC} 📈 ایجاد نمودار"
    echo -e "  ${GREEN}6)${NC} 📋 نمایش آخرین نتایج بکتست"
    echo -e "  ${GREEN}7)${NC} 🔧 تنظیمات پیشرفته"
    echo -e "  ${GREEN}8)${NC} 🚀 اجرای بکتست روی چند تایم‌فریم"
    echo -e "  ${GREEN}9)${NC} 📊 بکتست کامل با تحلیل"
    echo -e "  ${GREEN}0)${NC} ❌ خروج"
    echo -e "${CYAN}════════════════════════════════════════════${NC}"
}

show_advanced_menu() {
    echo -e "\n${PURPLE}════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}            تنظیمات پیشرفته${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
    echo -e "  ${GREEN}1)${NC} تغییر نام استراتژی"
    echo -e "  ${GREEN}2)${NC} تغییر فایل پیکربندی"
    echo -e "  ${GREEN}3)${NC} تغییر فایل داکر کامپوز"
    echo -e "  ${GREEN}4)${NC} پاک کردن کش"
    echo -e "  ${GREEN}5)${NC} نمایش لاگ‌ها"
    echo -e "  ${GREEN}6)${NC} بازگشت به منوی اصلی"
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
}

handle_advanced_menu() {
    while true; do
        show_advanced_menu
        read -p "انتخاب شما [1-6]: " adv_choice
        
        case $adv_choice in
            1)
                read -p "نام جدید استراتژی: " STRATEGY_NAME
                log "INFO" "نام استراتژی به ${STRATEGY_NAME} تغییر یافت"
                ;;
            2)
                read -p "نام فایل پیکربندی جدید: " CONFIG_FILE
                log "INFO" "فایل پیکربندی به ${CONFIG_FILE} تغییر یافت"
                check_config
                ;;
            3)
                read -p "نام فایل داکر کامپوز جدید: " DOCKER_COMPOSE_FILE
                log "INFO" "فایل داکر کامپوز به ${DOCKER_COMPOSE_FILE} تغییر یافت"
                DOCKER_COMPOSE="docker-compose -f ${DOCKER_COMPOSE_FILE}"
                ;;
            4)
                log "STEP" "پاک کردن کش..."
                rm -rf "${USER_DATA_DIR}/hyperopt_results"/*
                rm -rf "${USER_DATA_DIR}/backtest_results"/*
                log "INFO" "کش پاک شد"
                ;;
            5)
                log "STEP" "نمایش آخرین لاگ‌ها..."
                tail -50 "$LOG_FILE"
                ;;
            6)
                break
                ;;
            *)
                log "ERROR" "گزینه نامعتبر!"
                ;;
        esac
        
        echo -e "\n${BLUE}Enter را بزنید...${NC}"
        read
    done
}

# ============================================
# اجرای اصلی
# ============================================

main() {
    print_banner
    check_docker
    check_strategy
    check_config
    
    # تنظیمات پیش‌فرض
    DEFAULT_PAIRS="BTC/USDT,ETH/USDT"
    DEFAULT_TIMEFRAME="1h"
    DEFAULT_TIMERANGE="20240101-"
    
    while true; do
        show_menu
        read -p "انتخاب شما [0-9]: " choice
        
        case $choice in
            1)
                # دانلود داده
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "تایم‌فریم [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "تعداد روز [30]: " DAYS
                DAYS=${DAYS:-30}
                run_download_data "$PAIRS" "$TIMEFRAME" "$DAYS"
                ;;
            2)
                # بکتست ساده
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "تایم‌فریم [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "بازه زمانی [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                run_backtest "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                ;;
            3)
                # دانلود + بکتست
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "تایم‌فریم [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "تعداد روز برای دانلود [30]: " DAYS
                DAYS=${DAYS:-30}
                read -p "بازه زمانی بکتست [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                run_download_data "$PAIRS" "$TIMEFRAME" "$DAYS"
                run_backtest "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                ;;
            4)
                # Hyperopt
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "تایم‌فریم [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "بازه زمانی [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                
                echo -e "\n${YELLOW}توابع زیان موجود:${NC}"
                echo "  1) SharpeHyperOptLoss"
                echo "  2) SortinoHyperOptLoss"
                echo "  3) CalmarHyperOptLoss"
                echo "  4) ProfitDrawDownHyperOptLoss"
                read -p "انتخاب تابع زیان [1]: " LOSS_CHOICE
                
                case $LOSS_CHOICE in
                    2) LOSS_FUNC="SortinoHyperOptLoss" ;;
                    3) LOSS_FUNC="CalmarHyperOptLoss" ;;
                    4) LOSS_FUNC="ProfitDrawDownHyperOptLoss" ;;
                    *) LOSS_FUNC="SharpeHyperOptLoss" ;;
                esac
                
                read -p "تعداد دوره‌های Hyperopt [100]: " EPOCHS
                EPOCHS=${EPOCHS:-100}
                
                run_hyperopt "$EPOCHS" "$LOSS_FUNC" "$TIMERANGE"
                ;;
            5)
                # ایجاد نمودار
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "تایم‌فریم [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "بازه زمانی [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                plot_results "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                ;;
            6)
                # نمایش نتایج
                show_backtest_results
                ;;
            7)
                # تنظیمات پیشرفته
                handle_advanced_menu
                ;;
            8)
                # بکتست روی چند تایم‌فریم
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "بازه زمانی [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                
                for tf in "15m" "1h" "4h"; do
                    log "INFO" "اجرای بکتست روی تایم‌فریم $tf"
                    run_backtest "$TIMERANGE" "$PAIRS" "$tf"
                done
                ;;
            9)
                # بکتست کامل
                read -p "جفت‌ارزها [${DEFAULT_PAIRS}]: " PAIRS
                PAIRS=${PAIRS:-$DEFAULT_PAIRS}
                read -p "تایم‌فریم [${DEFAULT_TIMEFRAME}]: " TIMEFRAME
                TIMEFRAME=${TIMEFRAME:-$DEFAULT_TIMEFRAME}
                read -p "تعداد روز برای دانلود [30]: " DAYS
                DAYS=${DAYS:-30}
                read -p "بازه زمانی بکتست [${DEFAULT_TIMERANGE}]: " TIMERANGE
                TIMERANGE=${TIMERANGE:-$DEFAULT_TIMERANGE}
                
                # دانلود داده
                run_download_data "$PAIRS" "$TIMEFRAME" "$DAYS"
                
                # بکتست
                BACKTEST_FILE=$(run_backtest "$TIMERANGE" "$PAIRS" "$TIMEFRAME")
                
                # نمایش نتایج
                if [ -n "$BACKTEST_FILE" ]; then
                    show_backtest_results
                    
                    # ایجاد نمودار
                    echo -e "\n${YELLOW}آیا می‌خواهید نمودار ایجاد شود؟ (y/n)${NC}"
                    read -p "> " create_plot
                    if [[ "$create_plot" =~ ^[Yy]$ ]]; then
                        plot_results "$TIMERANGE" "$PAIRS" "$TIMEFRAME"
                    fi
                fi
                ;;
            0)
                log "INFO" "خروج از برنامه"
                echo -e "\n${GREEN}با تشکر از استفاده از اسکریپت بکتست خودکار${NC}"
                echo -e "${BLUE}لاگ‌ها در فایل زیر ذخیره شدند:${NC}"
                echo -e "${YELLOW}$LOG_FILE${NC}"
                exit 0
                ;;
            *)
                log "ERROR" "گزینه نامعتبر! لطفاً عدد بین ۰ تا ۹ را وارد کنید"
                ;;
        esac
        
        echo -e "\n${BLUE}برای ادامه Enter را بزنید...${NC}"
        read
    done
}

# اجرای تابع اصلی
main "$@"