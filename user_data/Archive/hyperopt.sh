#!/bin/bash

config="user_data/cluster_strategy_v4_config.json"
log_file="user_data/hyperopt.log"
strat="ClusterStrategyV4"
range="20240413-"
loss="ShortTradeDurHyperOptLoss"
spaces="roi"
timeframes="15m 1h 5m"

freqtrade download-data -c $config -t $timeframes

for i in {1..10};
do
    echo "---------------------------------------- Period #${i} `date` ----------------------------------------" >> $log_file
    freqtrade hyperopt -c $config -s $strat --timerange $range --hyperopt-loss $loss --spaces $spaces -e 1000 >> $log_file
    freqtrade backtesting -c $config -s $strat --timerange $range  >> $log_file
done

# ShortTradeDurHyperOptLoss
# SharpeHyperOptLossDaily
# freqtrade hyperopt -c $config -s $strat --freqaimodel $model --timerange $range --hyperopt-loss $loss --spaces $spaces -e 1000 >> $log_file
# freqtrade backtesting -c $config -s $strat --freqaimodel $model --timerange $range  >> $log_file
# model="XGBoostClassifier"