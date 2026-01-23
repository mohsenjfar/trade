#!/bin/bash

service="atlas_engine"
func="SharpeHyperOptLossDaily"
spaces="buy sell"
strategy="AtlasEngine"
config="user_data/atlas_engine_test.json"
epochs=1000
log_file="hyperopt.log"

docker-compose run --rm $service hyperopt --hyperopt-loss $func --spaces $spaces --strategy $strategy --config $config -e $epochs --analyze-per-epoch>> $log_file
git add . && git commit -m "backtest" && git push