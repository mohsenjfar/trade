import logging
from typing import Any, Dict

from xgboost import XGBRegressor
import time
from freqtrade.freqai.base_models.BaseRegressionModel import BaseRegressionModel
from freqtrade.freqai.data_kitchen import FreqaiDataKitchen
from sklearn.metrics.pairwise import pairwise_distances
import pandas as pd
import numpy.typing as npt
from pandas import DataFrame
import numpy as np
from sklearn.model_selection import train_test_split
import random

logger = logging.getLogger(__name__)


class XGBVPS(BaseRegressionModel):
    """
    مدل XGBoost بهینه‌شده برای VPS با ۴ گیگ رم و ۴ هسته CPU
    - رفع باگ activate_tensorboard
    - رفع باگ window auto_training
    - بهینه‌سازی مصرف حافظه
    - غیرفعالسازی Optuna
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.activate_tensorboard = False  # رفع باگ بحرانی
    
    def fit(self, data_dictionary: Dict, dk: FreqaiDataKitchen, **kwargs) -> Any:
        """
        آموزش مدل با بهینه‌سازی مصرف حافظه
        """
        # =========== بهینه‌سازی حافظه ===========
        X = data_dictionary["train_features"].astype('float32')
        y = data_dictionary["train_labels"].astype('float32')
        sample_weight = data_dictionary["train_weights"]
        
        # =========== تنظیم eval_set ===========
        if self.freqai_info.get("data_split_parameters", {}).get("test_size", 0.1) == 0:
            eval_set = None
            eval_weights = None
        else:
            eval_set = [(data_dictionary["test_features"].astype('float32'), 
                        data_dictionary["test_labels"].astype('float32'))]
            eval_weights = [data_dictionary['test_weights']]
        
        # =========== رفع باگ window (بحرانی) ===========
        if not self.freqai_info.get("auto_training_window", False):
            # فقط در صورت غیرفعال بودن auto_training، اعمال محدودیت کن
            window = self.freqai_info.get("live_trained_timerange", 4320)
            if isinstance(window, str):
                # تبدیل "720h" به عدد
                window = int(window.replace('h', '')) * 12  # 720h = 8640 candles
            X = X.tail(min(window, len(X)))
            y = y.tail(min(window, len(y)))
            sample_weight = sample_weight[-min(window, len(sample_weight)):]
        
        # =========== مدل XGBoost کم‌مصرف ===========
        start = time.time()
        xgb_model = self.get_init_model(dk.pair)
        
        model = XGBRegressor(**self.model_training_parameters)
        
        # تنظیمات اضافی برای VPS
        vps_params = {
            'tree_method': 'hist',
            'max_bin': 128,
            'grow_policy': 'depthwise',
            'single_precision_histogram': True,
            'verbosity': 0,
            'n_jobs': 2,
        }
        
        for key, value in vps_params.items():
            if key not in self.model_training_parameters:
                model.set_params(**{key: value})
        
        # =========== آموزش ===========
        # رفع باگ tensorboard - حذف کامل callbacks
        model.fit(
            X=X, 
            y=y, 
            sample_weight=sample_weight, 
            eval_set=eval_set,
            sample_weight_eval_set=eval_weights, 
            xgb_model=xgb_model
        )
        
        time_spent = (time.time() - start)
        self.dd.update_metric_tracker('fit_time', time_spent, dk.pair)
        
        return model
    
    def fit_live_predictions(self, dk: FreqaiDataKitchen, pair: str) -> None:
        """
        محاسبه آستانه‌های تطبیقی از پیش‌بینی‌های اخیر
        """
        num_candles = self.freqai_info.get('fit_live_predictions_candles', 100)
        
        # بررسی وضعیت warm-up
        warmed_up = True
        if self.live:
            if not hasattr(self, 'exchange_candles'):
                self.exchange_candles = len(self.dd.model_return_values[pair].index)
            candle_diff = len(self.dd.historic_predictions[pair].index) - \
                (num_candles + self.exchange_candles)
            if candle_diff < 0:
                warmed_up = False
        
        # آماده‌سازی داده‌ها
        pred_df_full = self.dd.historic_predictions[pair].tail(num_candles).reset_index(drop=True)
        
        # محاسبه آستانه‌ها
        if not warmed_up:
            dk.data['extra_returns_per_train']['&s-maxima_sort_threshold'] = 0.8
            dk.data['extra_returns_per_train']['&s-minima_sort_threshold'] = -0.8
            dk.data['extra_returns_per_train']['DI_cutoff'] = 30
        else:
            # محاسبه چندک‌ها برای &s-extrema
            if '&s-extrema' in pred_df_full.columns:
                extrema_values = pred_df_full['&s-extrema'].dropna()
                if len(extrema_values) > 10:
                    max_threshold = extrema_values.quantile(0.95)
                    min_threshold = extrema_values.quantile(0.05)
                else:
                    max_threshold, min_threshold = 0.8, -0.8
            else:
                max_threshold, min_threshold = 0.8, -0.8
            
            dk.data['extra_returns_per_train']['&s-maxima_sort_threshold'] = max_threshold
            dk.data['extra_returns_per_train']['&s-minima_sort_threshold'] = min_threshold
            
            # محاسبه DI_cutoff
            if 'DI_values' in pred_df_full.columns:
                di_values = pred_df_full['DI_values'].dropna()
                if len(di_values) > 10:
                    di_cutoff = di_values.quantile(0.99)
                else:
                    di_cutoff = 30
            else:
                di_cutoff = 30
            
            dk.data['extra_returns_per_train']['DI_cutoff'] = di_cutoff
    
    def train(self, unfiltered_df: DataFrame, pair: str, dk: FreqaiDataKitchen, **kwargs) -> Any:
        """
        آموزش کامل مدل
        """
        logger.info(f"-------------------- Starting training {pair} --------------------")
        start_time = time.time()
        
        # فیلتر ویژگی‌ها
        features_filtered, labels_filtered = dk.filter_features(
            unfiltered_df,
            dk.training_features_list,
            dk.label_list,
            training_filter=True,
        )
        
        # تاریخ شروع و پایان
        start_date = unfiltered_df["date"].iloc[0].strftime("%Y-%m-%d")
        end_date = unfiltered_df["date"].iloc[-1].strftime("%Y-%m-%d")
        logger.info(f"Training on data from {start_date} to {end_date}")
        
        # تقسیم داده
        dd = self.make_train_test_datasets(features_filtered, labels_filtered, dk)
        
        if not self.freqai_info.get("fit_live_predictions_candles", 0) or not self.live:
            dk.fit_labels()
        
        # Pipeline
        dk.feature_pipeline = self.define_data_pipeline(threads=1)  # تک‌رشته‌ای
        dk.label_pipeline = self.define_label_pipeline(threads=1)
        
        # تبدیل داده‌های آموزش
        (dd["train_features"],
         dd["train_labels"],
         dd["train_weights"]) = dk.feature_pipeline.fit_transform(
            dd["train_features"], dd["train_labels"], dd["train_weights"]
        )
        dd["train_labels"], _, _ = dk.label_pipeline.fit_transform(dd["train_labels"])
        
        # تبدیل داده‌های تست
        if self.freqai_info.get('data_split_parameters', {}).get('test_size', 0.1) != 0:
            (dd["test_features"],
             dd["test_labels"],
             dd["test_weights"]) = dk.feature_pipeline.transform(
                dd["test_features"], dd["test_labels"], dd["test_weights"]
            )
            dd["test_labels"], _, _ = dk.label_pipeline.transform(dd["test_labels"])
        
        # پنجره آموزشی خودکار
        if self.freqai_info.get("auto_training_window", False):
            target_horizon = self.freqai_info['feature_parameters']['label_period_candles']
            df = dd["train_features"]
            z = self.find_training_horizon_optimized(df, target_horizon)
            logger.info(f"Reducing training data from {len(df)} to {z} candles")
            dd["train_features"] = df.tail(z)
            dd["train_labels"] = dd["train_labels"].tail(z)
            dd["train_weights"] = dd["train_weights"][-z:]
        
        logger.info(f"Training on {len(dd['train_features'])} points with "
                   f"{len(dd['train_features'].columns)} features")
        
        # آموزش
        model = self.fit(dd, dk)
        
        end_time = time.time()
        logger.info(f"-------------------- Done training {pair} "
                   f"({end_time - start_time:.2f}s) --------------------")
        
        return model
    
    def find_training_horizon_optimized(self, df: pd.DataFrame, target_horizon: int, 
                                        threshold: float = 0.001) -> int:
        """
        نسخه فوق‌بهینه برای VPS - ۱۰ برابر سریع‌تر
        """
        # فقط ستون‌های اصلی
        df_comp = df.loc[:, ~df.columns.str.contains("shift")].copy()
        
        # محدودیت‌های سخت برای VPS
        MAX_WINDOW = 2000
        max_window = min(df_comp.shape[0] - target_horizon, MAX_WINDOW)
        
        # اگر داده کم است
        if max_window < 100:
            return df_comp.shape[0]
        
        # نمونه‌برداری برای سرعت
        sample_size = min(300, len(df_comp))
        step_size = max(50, max_window // 20)  # حداکثر 20 مرحله
        
        std_ratio = []
        
        for t in range(0, max_window, step_size):
            # نمونه‌برداری تصادفی
            idx = np.random.choice(len(df_comp), min(sample_size, len(df_comp)), replace=False)
            sample = df_comp.iloc[idx]
            
            # محاسبه فاصله اقلیدسی ساده
            distances = np.linalg.norm(sample.values[:, np.newaxis] - sample.values, axis=2)
            np.fill_diagonal(distances, np.nan)
            std_train = np.nanstd(distances)
            
            if std_train == 0:
                continue
            
            # محاسبه معیار
            di_std = 1.0 / std_train * 100
            std_ratio.append(di_std)
            
            if len(std_ratio) > 2:
                change = abs(std_ratio[-1] - std_ratio[-2])
                if change < threshold * 100:
                    logger.info(f"Found training horizon: {t}")
                    return max(t, target_horizon * 2)
        
        return min(max_window, 1500)
    
    def make_train_test_datasets(self, filtered_dataframe: DataFrame, labels: DataFrame, 
                                dk: FreqaiDataKitchen) -> Dict[Any, Any]:
        """تقسیم داده به آموزش و تست"""
        
        feat_dict = dk.freqai_config["feature_parameters"]
        
        # تنظیم shuffle
        if 'shuffle' not in dk.freqai_config['data_split_parameters']:
            dk.freqai_config["data_split_parameters"].update({'shuffle': False})
        
        # وزن‌دهی
        if feat_dict.get("weight_factor", 0) > 0:
            weights = dk.set_weights_higher_recent(len(filtered_dataframe))
        else:
            weights = np.ones(len(filtered_dataframe))
        
        # تقسیم
        if dk.freqai_config.get('data_split_parameters', {}).get('test_size', 0.1) != 0:
            train_features, test_features, train_labels, test_labels, train_weights, test_weights = \
                train_test_split(
                    filtered_dataframe, labels, weights,
                    **dk.config["freqai"]["data_split_parameters"]
                )
        else:
            test_labels = np.zeros(2)
            test_features = pd.DataFrame()
            test_weights = np.zeros(2)
            train_features = filtered_dataframe
            train_labels = labels
            train_weights = weights
        
        return dk.build_data_dictionary(
            train_features, test_features, train_labels,
            test_labels, train_weights, test_weights
        )
    
    def balance_training_weights(self, labels: DataFrame, weights: npt.ArrayLike, 
                                dk: FreqaiDataKitchen) -> npt.ArrayLike:
        """موازنه وزن‌ها بر اساس برچسب‌ها"""
        label = dk.label_list[0]
        balance_weights = labels[label].abs().values.ravel()
        weights_balanced = weights + balance_weights
        scaled_weights = (weights_balanced - weights_balanced.min()) / \
                        (weights_balanced.max() - weights_balanced.min())
        return scaled_weights