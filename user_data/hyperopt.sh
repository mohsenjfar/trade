#!/bin/bash

config=user_data/cluster_strategy_v4_config.json
log_file=user_data/hyperopt.log
strat=ClusterStrategyV4

freqtrade download-data -c $config -t 1h 15m

for i in {1..10};
do
    echo "---------------------------------------- Period #${i} ----------------------------------------" >> $log_file
    freqtrade hyperopt -c $config -s $strat --timerange 20240501- --hyperopt-loss SharpeHyperOptLossDaily --spaces buy stoploss roi -e 1000 >> $log_file
    freqtrade backtesting -c $config -s $strat --timerange 20240501- >> $log_file
done
