for i in $(seq 1 10);
do
    freqtrade hyperopt -c user_data/cluster_strategy_v4_config.json -s ClusterStrategyV4 --timerange 20240501- --hyperopt-loss SharpeHyperOptLossDaily --spaces buy stoploss roi -e 500 >> ./hyperopt.log
    freqtrade backtesting -c user_data/cluster_strategy_v4_config.json -s ClusterStrategyV4 --timerange 20240501- >> ./hyperopt.log
done
