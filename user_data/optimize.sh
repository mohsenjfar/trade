#!/bin/bash

service="atlas_engine"
func="SharpeHyperOptLossDaily"
spaces="buy sell"
strategy="AtlasEngine"
config="atlas_engine_test.json"
epochs=1000
log_file="logs/hyperopt.log"

docker-compose run --rm $service hyperopt --hyperopt-loss $func --spaces $spaces --strategy $strategy --config $config -e $epochs --analyze-per-epoch>> $log_file
git add . && git commit -m "backtest" && git push