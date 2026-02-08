"""
ماژول کلاسترینگ توکن‌ها بر اساس داده‌های OHLCV از data/bybit/futures (قالب Feather).
توکن‌ها با استفاده از KMeans به ۵ گروه تقسیم می‌شوند.
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


# مسیر پیش‌فرض نسبت به ریشه پروژه (پوشه trade)
DEFAULT_DATA_DIR = "data/bybit/futures"


def _find_project_root() -> Path:
    """پیدا کردن ریشه پروژه (پوشه‌ای که user_data یا data در آن است)."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "user_data").is_dir() or (parent / "data").is_dir():
            return parent
    return current.parent


def load_token_data(
    data_dir: Optional[Path] = None,
    timeframe: str = "1h",
    extensions: tuple = (".feather",),
) -> dict[str, pd.DataFrame]:
    """
    خواندن داده‌های OHLCV همه توکن‌ها از data/bybit/futures (قالب Feather).

    Args:
        data_dir: مسیر پوشه داده (پیش‌فرض: پروژه/data/bybit/futures)
        timeframe: تایم‌فریم مورد نظر (مثلاً 1h, 4h)
        extensions: پسوند فایل‌های مجاز (پیش‌فرض: .feather)

    Returns:
        دیکشنری {symbol: DataFrame} با ستون‌های date, open, high, low, close, volume
    """
    if data_dir is None:
        root = _find_project_root()
        data_dir = root / DEFAULT_DATA_DIR

    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        return {}

    result: dict[str, pd.DataFrame] = {}
    # فایل‌های Feather معمولاً: BTC_USDT-1h.feather یا مشابه
    pattern = f"*{timeframe}*"
    for path in data_dir.glob(pattern):
        if path.suffix.lower() not in extensions:
            continue
        try:
            if path.suffix.lower() == ".feather":
                df = pd.read_feather(path)
            elif path.suffix.lower() == ".csv":
                df = pd.read_csv(path)
            else:
                df = pd.read_json(path)
            # نرمال‌سازی نام ستون‌ها
            df.columns = [c.lower().strip() for c in df.columns]
            required = {"date", "open", "high", "low", "close", "volume"}
            if not required.issubset(df.columns):
                continue
            df["date"] = pd.to_datetime(df["date"], utc=True)
            df = df.sort_values("date").dropna(subset=["close"])
            symbol = path.stem.replace(".gz", "").split("-")[0].replace("_", "/")
            if "USDT" not in symbol.upper():
                symbol = f"{symbol}/USDT:USDT"
            elif ":" not in symbol:
                symbol = f"{symbol}:USDT"
            result[symbol] = df
        except Exception:
            continue
    return result


def _btc_returns_series(tokens_data: dict[str, pd.DataFrame]) -> Optional[pd.Series]:
    """برگرداندن سری بازده بیت‌کوین با ایندکس date برای هم‌راستاسازی."""
    for sym, df in tokens_data.items():
        if "BTC" in sym.upper() and "USDT" in sym.upper():
            out = df.set_index("date")["close"].astype(float).pct_change().dropna()
            return out
    return None


def extract_features(tokens_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    استخراج ویژگی‌هایی که «نوع» توکن را مشخص می‌کنند: نوسان، اندازه بازار، همبستگی با BTC.
    تا توکن‌های شبیه هم (مثلاً بیت‌کوین با اتریوم، نه با مِم‌کوین‌ها) در یک گروه بیایند.
    """
    btc_ret = _btc_returns_series(tokens_data)
    rows = []
    for symbol, df in tokens_data.items():
        if len(df) < 2:
            continue
        close = df["close"].astype(float)
        returns = close.pct_change().dropna()
        volume = df["volume"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol_std = returns.std()
        vol_std = vol_std if vol_std > 0 else 1e-10
        # نوسان: انحراف معیار بازده‌ها (هرچه بالاتر = توکن پرنوسان‌تر مثل مِم)
        volatility = vol_std
        # اندازه بازار: حجم میانگین روی مقیاس لگ (بیت‌کوین بزرگ، مِم‌کوین‌ها کوچک‌تر)
        log_volume = np.log1p(volume.mean())
        # دامنهٔ high-low نسبی (نوعی نوسان روزانه)
        hl_pct = (high - low).mean() / close.mean() if close.mean() else 0
        row = {
            "symbol": symbol,
            "volatility": volatility,
            "log_volume": log_volume,
            "hl_range_pct": hl_pct,
        }
        # همبستگی با BTC: توکن‌های هم‌حرکت با بیت‌کوین (بلوچیپ) از مِم‌کوین‌ها جدا می‌شوند
        if btc_ret is not None and "BTC" not in symbol.upper():
            tok_ret = df.set_index("date")["close"].astype(float).pct_change().dropna()
            common_idx = tok_ret.index.intersection(btc_ret.index)
            if len(common_idx) > 10:
                a = tok_ret.reindex(common_idx).ffill().bfill().dropna()
                b = btc_ret.reindex(common_idx).ffill().bfill().reindex(a.index).dropna()
                idx = a.index.intersection(b.index)
                if len(idx) > 10:
                    c = np.corrcoef(a.loc[idx], b.loc[idx])[0, 1]
                    row["corr_btc"] = float(c) if not np.isnan(c) else 0.0
                else:
                    row["corr_btc"] = 0.0
            else:
                row["corr_btc"] = 0.0
        elif "BTC" in symbol.upper():
            row["corr_btc"] = 1.0
        else:
            row["corr_btc"] = 0.0
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    feat = pd.DataFrame(rows).set_index("symbol").fillna(0)
    # همبستگی را به [0,1] نگه می‌داریم؛ مقادیر منفی = ضد هم‌حرکت
    feat["corr_btc"] = (feat["corr_btc"] + 1) / 2
    # تبدیل به رتبهٔ درصدی (۰ تا ۱) تا فاصله‌ها بر اساس «تشابه نوع» باشد
    for col in feat.columns:
        feat[col] = feat[col].rank(pct=True, method="average")
    return feat


def cluster_tokens(
    n_clusters: int = 5,
    data_dir: Optional[Path] = None,
    timeframe: str = "1h",
    random_state: int = 42,
) -> dict[str, int]:
    """
    تقسیم‌بندی توکن‌ها به n_clusters گروه با KMeans.

    Args:
        n_clusters: تعداد خوشه‌ها (پیش‌فرض ۵)
        data_dir: مسیر پوشه داده
        timeframe: تایم‌فریم
        random_state: برای تکرارپذیری

    Returns:
        دیکشنری {symbol: cluster_id} که cluster_id از 0 تا n_clusters-1 است.
    """
    tokens_data = load_token_data(data_dir=data_dir, timeframe=timeframe)
    if not tokens_data:
        return {}

    features = extract_features(tokens_data)
    if len(features) < n_clusters:
        # اگر توکن‌ها کمتر از تعداد خوشه باشند، هر کدام یک خوشه
        return {sym: i for i, sym in enumerate(features.index)}

    scaler = StandardScaler()
    X = scaler.fit_transform(features)
    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = kmeans.fit_predict(X)
    return dict(zip(features.index, labels.tolist()))


def get_token_groups(
    n_clusters: int = 5,
    data_dir: Optional[Path] = None,
    timeframe: str = "1h",
    random_state: int = 42,
) -> dict[int, list[str]]:
    """
    همان cluster_tokens ولی خروجی به صورت گروه‌بندی: {cluster_id: [symbol, ...]}.

    Returns:
        دیکشنری {cluster_id: [symbol1, symbol2, ...]}
    """
    symbol_to_cluster = cluster_tokens(
        n_clusters=n_clusters,
        data_dir=data_dir,
        timeframe=timeframe,
        random_state=random_state,
    )
    groups: dict[int, list[str]] = {i: [] for i in range(n_clusters)}
    for sym, cid in symbol_to_cluster.items():
        if cid not in groups:
            groups[cid] = []
        groups[cid].append(sym)
    return groups


def save_clusters_json(
    output_path: Path,
    n_clusters: int = 5,
    data_dir: Optional[Path] = None,
    timeframe: str = "1h",
    random_state: int = 42,
) -> dict[str, list[str]]:
    """
    کلاسترینگ توکن‌ها و ذخیرهٔ خروجی در یک فایل JSON.
    کلیدها: "0", "1", ... و مقدار هر کلید لیست symbolهاست.

    Returns:
        دیکشنری {"0": [symbol, ...], "1": [...], ...} (همان دادهٔ ذخیره‌شده)
    """
    groups = get_token_groups(
        n_clusters=n_clusters,
        data_dir=data_dir,
        timeframe=timeframe,
        random_state=random_state,
    )
    # کلیدها به صورت رشته تا در JSON عدد نباشند؛ بدون استفاده از کلمهٔ گروه
    out: dict[str, list[str]] = {str(k): sorted(v) for k, v in sorted(groups.items())}
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    root = _find_project_root()
    out_file = root / "strategies" / "token_clusters.json"
    result = save_clusters_json(out_file, n_clusters=5)
    if not result:
        print("پوشه data/bybit/futures یافت نشد یا خالی است. مسیر را بررسی کنید.")
    else:
        print(f"خروجی در {out_file} ذخیره شد.")
