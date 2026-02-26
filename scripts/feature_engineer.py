"""
feature_engineer.py — Example script for predictive feature extraction and ranking.

This is a REFERENCE IMPLEMENTATION. It demonstrates the feature engineering
workflow described in quant-models/references/feature-engineering.md.
It is meant to be extended, forked, or called programmatically.

To extend:
  - Add new feature builders: subclass or add build_*_features() functions
  - Add new ranking methods: add to RANKING_METHODS dict
  - Add new sector configs: add to BUILTIN_CONFIGS or pass --config JSON
  - Add new signal types: extend the signals fetching in main()
  - Use as a library: import build_all_features, run_validation, etc.

Built-in ranking methods:
  - gbm: Gradient Boosting (non-linear interactions, threshold effects)
  - rf: Random Forest (robust to outliers, non-linear)
  - l1: L1 Logistic Regression (sparse linear selection)
  - mutual_info: Mutual Information (model-free statistical dependency)
  - all: Run all methods and produce consensus ranking

Usage:
    # Built-in sector config
    uv run python scripts/feature_engineer.py --sector mining

    # Custom config
    uv run python scripts/feature_engineer.py --config path/to/config.json

    # Choose ranking method (default: all)
    uv run python scripts/feature_engineer.py --sector mining --method gbm
    uv run python scripts/feature_engineer.py --sector mining --method all

    # Override output and target horizon
    uv run python scripts/feature_engineer.py --sector auto --output output/auto_features --horizon 10

Config JSON format:
    {
        "name": "Indian Mining",
        "stocks": {"COALINDIA.NS": "Coal India", "NMDC.NS": "NMDC"},
        "cross_assets": {"GC=F": "Gold", "HG=F": "Copper", "^NSEI": "Nifty50", "USDINR=X": "USD_INR", "^VIX": "VIX"},
        "sector_index": "^CNXMETAL",
        "signals": {
            "type": "geo",
            "weather_locations": {"Jharkhand": [23.6, 85.3], "Odisha": [21.5, 84.0]},
            "earthquake_locations": {"Jharkhand": [23.6, 85.3], "Odisha": [21.5, 84.0]},
            "earthquake_min_mag": 3.0,
            "earthquake_radius_km": 500
        },
        "seasons": {
            "monsoon": [6, 7, 8, 9],
            "pre_monsoon": [4, 5],
            "post_monsoon": [10, 11],
            "winter": [12, 1, 2],
            "fiscal_yearend": [3]
        },
        "start": "2023-01-01",
        "target_horizon": 5
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy import stats
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore")


# ── Built-in sector configs ──────────────────────────────────────────────

BUILTIN_CONFIGS = {
    "mining": {
        "name": "Indian Mining",
        "stocks": {
            "COALINDIA.NS": "Coal India",
            "NMDC.NS": "NMDC",
            "VEDL.NS": "Vedanta",
            "TATASTEEL.NS": "Tata Steel",
            "HINDALCO.NS": "Hindalco",
        },
        "cross_assets": {
            "GC=F": "Gold",
            "HG=F": "Copper",
            "ALI=F": "Aluminium",
            "^NSEI": "Nifty50",
            "USDINR=X": "USD_INR",
            "^VIX": "VIX",
        },
        "sector_index": "^CNXMETAL",
        "signals": {
            "type": "geo",
            "weather_locations": {
                "Jharkhand": [23.6, 85.3],
                "Odisha": [21.5, 84.0],
                "Chhattisgarh": [21.3, 81.6],
                "Rajasthan": [25.0, 73.0],
                "Goa": [15.4, 74.0],
                "Karnataka": [15.3, 76.4],
            },
            "earthquake_locations": {
                "Jharkhand": [23.6, 85.3],
                "Odisha": [21.5, 84.0],
                "Chhattisgarh": [21.3, 81.6],
                "Rajasthan": [25.0, 73.0],
                "Goa": [15.4, 74.0],
                "Karnataka": [15.3, 76.4],
            },
            "earthquake_min_mag": 3.0,
            "earthquake_radius_km": 500,
        },
        "seasons": {
            "monsoon": [6, 7, 8, 9],
            "pre_monsoon": [4, 5],
            "post_monsoon": [10, 11],
            "winter": [12, 1, 2],
            "fiscal_yearend": [3],
        },
        "start": "2023-01-01",
        "target_horizon": 5,
    },
    "auto": {
        "name": "Indian Auto",
        "stocks": {
            "MARUTI.NS": "Maruti Suzuki",
            "TATAMOTORS.NS": "Tata Motors",
            "M&M.NS": "Mahindra",
            "BAJAJ-AUTO.NS": "Bajaj Auto",
            "HEROMOTOCO.NS": "Hero MotoCorp",
        },
        "cross_assets": {
            "CL=F": "Crude_Oil",
            "HRC=F": "Steel_HRC",
            "^NSEI": "Nifty50",
            "USDINR=X": "USD_INR",
            "^VIX": "VIX",
        },
        "sector_index": "^CNXAUTO",
        "signals": {
            "type": "geo",
            "weather_locations": {
                "Delhi": [28.6, 77.2],
                "Mumbai": [19.1, 72.9],
                "Chennai": [13.1, 80.3],
                "Pune": [18.5, 73.9],
                "Bangalore": [12.97, 77.6],
            },
            "earthquake_locations": {},
            "earthquake_min_mag": 5.0,
            "earthquake_radius_km": 200,
        },
        "seasons": {
            "festive": [10, 11],
            "budget": [2],
            "monsoon": [6, 7, 8, 9],
            "fiscal_yearend": [3],
        },
        "start": "2023-01-01",
        "target_horizon": 5,
    },
    "it": {
        "name": "Indian IT Services",
        "stocks": {
            "TCS.NS": "TCS",
            "INFY.NS": "Infosys",
            "WIPRO.NS": "Wipro",
            "HCLTECH.NS": "HCL Tech",
            "TECHM.NS": "Tech Mahindra",
        },
        "cross_assets": {
            "^IXIC": "NASDAQ",
            "USDINR=X": "USD_INR",
            "^NSEI": "Nifty50",
            "^VIX": "VIX",
        },
        "sector_index": "^CNXIT",
        "signals": {"type": "none"},
        "seasons": {
            "us_budget_flush": [1, 2, 3],
            "visa_season": [4, 5],
            "fiscal_yearend": [3],
        },
        "start": "2023-01-01",
        "target_horizon": 5,
    },
    "banking": {
        "name": "Indian Banking",
        "stocks": {
            "HDFCBANK.NS": "HDFC Bank",
            "ICICIBANK.NS": "ICICI Bank",
            "SBIN.NS": "SBI",
            "KOTAKBANK.NS": "Kotak Bank",
            "AXISBANK.NS": "Axis Bank",
        },
        "cross_assets": {
            "GC=F": "Gold",
            "^NSEI": "Nifty50",
            "USDINR=X": "USD_INR",
            "^VIX": "VIX",
        },
        "sector_index": "^NSEBANK",
        "signals": {"type": "none"},
        "seasons": {
            "rbi_policy": [2, 4, 6, 8, 10, 12],
            "npa_provisioning": [3],
            "fiscal_yearend": [3],
        },
        "start": "2023-01-01",
        "target_horizon": 5,
    },
}


# ── Data fetching ────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def fetch_earthquakes(locations: dict, start: str, end: str, min_mag: float = 3.0, radius_km: int = 500) -> pd.DataFrame:
    all_quakes = []
    seen = set()
    for name, (lat, lon) in locations.items():
        try:
            resp = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={
                "format": "geojson", "starttime": start, "endtime": end,
                "latitude": lat, "longitude": lon, "maxradiuskm": radius_km, "minmagnitude": min_mag,
            }, timeout=30)
            for feat in resp.json().get("features", []):
                eid = feat["id"]
                if eid in seen:
                    continue
                seen.add(eid)
                p, c = feat["properties"], feat["geometry"]["coordinates"]
                dist = haversine(lat, lon, c[1], c[0])
                all_quakes.append({
                    "date": datetime.fromtimestamp(p["time"] / 1000).strftime("%Y-%m-%d"),
                    "magnitude": p["mag"],
                    "depth_km": c[2],
                    "distance_km": round(dist, 1),
                    "energy": 10 ** (1.5 * p["mag"]),
                    "proximity_weight": 1 / (dist / 100 + 1),
                })
        except Exception:
            pass
    df = pd.DataFrame(all_quakes)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["weighted_energy"] = df["energy"] * df["proximity_weight"]
    return df


def fetch_weather(locations: dict, start: str, end: str) -> pd.DataFrame:
    frames = []
    api_end = min(end, datetime.now().strftime("%Y-%m-%d"))
    for name, (lat, lon) in locations.items():
        try:
            resp = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
                "latitude": lat, "longitude": lon,
                "start_date": start, "end_date": api_end,
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Kolkata",
            }, timeout=30)
            d = resp.json()["daily"]
            frames.append(pd.DataFrame({
                "date": pd.to_datetime(d["time"]),
                "region": name,
                "precip_mm": d["precipitation_sum"],
                "temp_max": d["temperature_2m_max"],
                "temp_min": d["temperature_2m_min"],
            }))
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_prices(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    prices = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                cols = ["Close"]
                if "Volume" in df.columns:
                    cols.append("Volume")
                prices[ticker] = df[cols]
        except Exception:
            pass
    return prices


# ── Feature engineering ──────────────────────────────────────────────────

def build_technical_features(feat: pd.DataFrame, close: pd.Series, vol: pd.Series | None):
    """Universal technical features from price data."""
    ret = close.pct_change()

    # Momentum
    for n in [1, 5, 10, 20, 60]:
        feat[f"ret_{n}d"] = close.pct_change(n)

    # Moving averages
    ma20, ma50, ma200 = close.rolling(20).mean(), close.rolling(50).mean(), close.rolling(200).mean()
    feat["price_vs_ma20"] = close / ma20 - 1
    feat["price_vs_ma50"] = close / ma50 - 1
    feat["price_vs_ma200"] = close / ma200 - 1
    feat["ma20_vs_ma50"] = ma20 / ma50 - 1
    feat["golden_cross"] = (ma50 > ma200).astype(int)

    # Volatility
    feat["vol_10d"] = ret.rolling(10).std() * np.sqrt(252)
    feat["vol_30d"] = ret.rolling(30).std() * np.sqrt(252)
    feat["vol_ratio"] = feat["vol_10d"] / (feat["vol_30d"] + 1e-10)

    # RSI
    delta = ret.copy()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    feat["rsi_14"] = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # Bollinger
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    feat["bb_position"] = (close - bb_mid) / (2 * bb_std + 1e-10)

    # Mean reversion
    feat["mean_rev_20d"] = -(close / ma20 - 1)

    # Drawdown
    feat["drawdown"] = (close - close.cummax()) / close.cummax()
    feat["drawdown_5d"] = feat["drawdown"].rolling(5).min()

    # Volume
    if vol is not None:
        vol_ma20 = vol.rolling(20).mean()
        feat["vol_ratio_price"] = vol / (vol_ma20 + 1)
        feat["vol_spike"] = (vol > vol_ma20 * 2).astype(int)


def build_cross_asset_features(feat: pd.DataFrame, close: pd.Series, prices: dict,
                                cross_assets: dict, sector_index: str | None):
    """Cross-asset features from correlated instruments."""
    for ticker, name in cross_assets.items():
        if ticker not in prices:
            continue
        ca_close = prices[ticker]["Close"].copy()
        ca_close.index = ca_close.index.tz_localize(None) if ca_close.index.tz else ca_close.index
        ca = ca_close.reindex(close.index, method="ffill")
        feat[f"{name}_ret_5d"] = ca.pct_change(5)
        feat[f"{name}_ret_20d"] = ca.pct_change(20)
        if name == "VIX":
            feat["vix_level"] = ca
            feat["vix_high"] = (ca > 25).astype(int)
        elif name == "USD_INR":
            feat["inr_weakening"] = (ca.pct_change(20) > 0.01).astype(int)

    if sector_index and sector_index in prices:
        si_close = prices[sector_index]["Close"].copy()
        si_close.index = si_close.index.tz_localize(None) if si_close.index.tz else si_close.index
        si = si_close.reindex(close.index, method="ffill")
        feat["sector_ret_5d"] = si.pct_change(5)
        feat["sector_ret_20d"] = si.pct_change(20)
        feat["rel_strength_sector"] = close.pct_change(20) - si.pct_change(20)


def build_earthquake_features(feat: pd.DataFrame, close: pd.Series, eq_df: pd.DataFrame):
    """Geological features from earthquake data."""
    if eq_df.empty:
        return
    daily_eq = eq_df.groupby("date").agg(
        eq_count=("magnitude", "count"),
        eq_max_mag=("magnitude", "max"),
        eq_total_energy=("weighted_energy", "sum"),
        eq_min_distance=("distance_km", "min"),
    )
    daily_eq = daily_eq.reindex(close.index).fillna(0)

    feat["eq_count_7d"] = daily_eq["eq_count"].rolling(7).sum()
    feat["eq_count_30d"] = daily_eq["eq_count"].rolling(30).sum()
    feat["eq_max_mag_30d"] = daily_eq["eq_max_mag"].rolling(30).max()
    feat["eq_energy_7d"] = daily_eq["eq_total_energy"].rolling(7).sum()
    feat["eq_energy_30d"] = daily_eq["eq_total_energy"].rolling(30).sum()
    feat["eq_energy_90d"] = daily_eq["eq_total_energy"].rolling(90).sum()

    eq_dates_series = daily_eq["eq_count"].replace(0, np.nan)
    feat["days_since_eq"] = eq_dates_series.groupby(eq_dates_series.notna().cumsum()).cumcount()


def build_weather_features(feat: pd.DataFrame, close: pd.Series, wx_df: pd.DataFrame):
    """Weather features from precipitation and temperature data."""
    if wx_df.empty:
        return
    daily_wx = wx_df.groupby("date").agg(
        precip_mean=("precip_mm", "mean"),
        precip_max=("precip_mm", "max"),
        temp_max=("temp_max", "max"),
        temp_min=("temp_min", "min"),
    )
    daily_wx = daily_wx.reindex(close.index, method="ffill")

    feat["rain_1d"] = daily_wx["precip_mean"]
    feat["rain_7d"] = daily_wx["precip_mean"].rolling(7).sum()
    feat["rain_30d"] = daily_wx["precip_mean"].rolling(30).sum()
    feat["rain_90d"] = daily_wx["precip_mean"].rolling(90).sum()
    feat["rain_max_7d"] = daily_wx["precip_max"].rolling(7).max()

    rain_60d_avg = daily_wx["precip_mean"].rolling(60).mean()
    feat["rain_anomaly"] = daily_wx["precip_mean"] - rain_60d_avg
    feat["rain_anomaly_7d"] = feat["rain_anomaly"].rolling(7).mean()
    feat["heavy_rain_days_30d"] = (daily_wx["precip_mean"] > 20).rolling(30).sum()
    feat["extreme_rain_days_30d"] = (daily_wx["precip_mean"] > 40).rolling(30).sum()
    feat["drought_flag"] = (feat["rain_30d"] < 5).astype(int)

    feat["temp_max_7d"] = daily_wx["temp_max"].rolling(7).mean()
    feat["temp_range"] = daily_wx["temp_max"] - daily_wx["temp_min"]
    feat["heat_wave"] = (daily_wx["temp_max"] > 42).rolling(7).sum()


def build_seasonal_features(feat: pd.DataFrame, close: pd.Series, seasons: dict):
    """Calendar and seasonal features."""
    feat["day_of_week"] = close.index.dayofweek
    feat["is_monday"] = (close.index.dayofweek == 0).astype(int)
    feat["is_friday"] = (close.index.dayofweek == 4).astype(int)

    for season_name, months in seasons.items():
        feat[f"is_{season_name}"] = close.index.month.isin(months).astype(int)


def build_interaction_features(feat: pd.DataFrame):
    """Interaction terms between domain signals and price features."""
    if "rain_30d" in feat.columns:
        if "is_monsoon" in feat.columns:
            feat["rain_x_monsoon"] = feat["rain_30d"] * feat["is_monsoon"]
        if "ret_20d" in feat.columns:
            feat["rain_x_momentum"] = feat["rain_30d"] * feat["ret_20d"]
        if "vol_30d" in feat.columns:
            feat["rain_x_vol"] = feat["rain_30d"] * feat["vol_30d"]

    if "eq_energy_30d" in feat.columns and "vol_30d" in feat.columns:
        feat["eq_x_vol"] = feat["eq_energy_30d"] * feat["vol_30d"]


def build_all_features(ticker: str, prices: dict, config: dict,
                        eq_df: pd.DataFrame, wx_df: pd.DataFrame) -> pd.DataFrame | None:
    """Build complete feature matrix for a single stock.

    This builds the standard feature set. To add custom features:
      1. Write a build_*_features(feat, close, ...) function
      2. Call it here after the existing builders
      3. Or build features externally and merge into the returned DataFrame
    """
    if ticker not in prices:
        return None

    close = prices[ticker]["Close"].copy()
    close.index = close.index.tz_localize(None) if close.index.tz else close.index
    vol = prices[ticker].get("Volume")
    if vol is not None:
        vol.index = vol.index.tz_localize(None) if vol.index.tz else vol.index

    horizon = config.get("target_horizon", 5)
    feat = pd.DataFrame(index=close.index)

    # Target
    feat["fwd_ret"] = close.shift(-horizon) / close - 1
    feat["target"] = (feat["fwd_ret"] > 0).astype(int)

    build_technical_features(feat, close, vol)
    build_cross_asset_features(feat, close, prices, config.get("cross_assets", {}), config.get("sector_index"))
    build_earthquake_features(feat, close, eq_df)
    build_weather_features(feat, close, wx_df)
    build_seasonal_features(feat, close, config.get("seasons", {}))
    build_interaction_features(feat)

    return feat


# ── Ranking methods ──────────────────────────────────────────────────────

EXCLUDE_COLS = {"fwd_ret", "target", "day_of_week"}


def categorize_feature(f: str) -> str:
    if f.startswith("eq_") or f.startswith("days_since"):
        return "GEO"
    if any(f.startswith(p) for p in ["rain", "heavy", "extreme", "drought", "temp", "heat"]):
        return "WEATHER"
    if f.startswith("is_") or f.startswith("monsoon"):
        return "SEASONAL"
    if any(f.startswith(p) for p in ["ret_", "vol_", "rsi", "bb_", "ma", "price_vs", "golden", "mean_rev", "drawdown"]):
        return "TECHNICAL"
    return "CROSS_ASSET"


CATEGORY_FILTERS = {
    "GEO": lambda c: c.startswith("eq_") or c.startswith("days_since"),
    "WEATHER": lambda c: any(c.startswith(p) for p in ["rain", "heavy", "extreme", "drought", "temp", "heat"]),
    "SEASONAL": lambda c: c.startswith("is_") or c.startswith("monsoon"),
    "TECHNICAL": lambda c: any(c.startswith(p) for p in ["ret_", "vol_", "rsi", "bb_", "ma", "price_vs", "golden", "mean_rev", "drawdown"]),
}


def rank_gbm(X_train, y_train, X_test, y_test, feature_cols: list[str]) -> dict:
    """Gradient Boosting: captures non-linear interactions and threshold effects."""
    gb = GradientBoostingClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        min_samples_leaf=20, random_state=42,
    )
    gb.fit(X_train, y_train)
    probs = gb.predict_proba(X_test)[:, 1]
    preds = gb.predict(X_test)
    auc = roc_auc_score(y_test, probs) if len(np.unique(y_test)) > 1 else 0.5
    acc = accuracy_score(y_test, preds)

    # Permutation importance (more reliable than .feature_importances_)
    perm = permutation_importance(gb, X_test, y_test, n_repeats=20, random_state=42)

    return {
        "name": "Gradient Boosting",
        "auc": auc,
        "accuracy": acc,
        "importances": perm.importances_mean,
        "importances_std": perm.importances_std,
        "model": gb,
    }


def rank_rf(X_train, y_train, X_test, y_test, feature_cols: list[str]) -> dict:
    """Random Forest: robust to outliers, handles non-linear patterns.
    Note: native .feature_importances_ splits importance among correlated features.
    Permutation importance is more honest."""
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=5, min_samples_leaf=20, random_state=42,
    )
    rf.fit(X_train, y_train)
    probs = rf.predict_proba(X_test)[:, 1]
    preds = rf.predict(X_test)
    auc = roc_auc_score(y_test, probs) if len(np.unique(y_test)) > 1 else 0.5
    acc = accuracy_score(y_test, preds)

    perm = permutation_importance(rf, X_test, y_test, n_repeats=20, random_state=42)

    return {
        "name": "Random Forest",
        "auc": auc,
        "accuracy": acc,
        "importances": perm.importances_mean,
        "importances_std": perm.importances_std,
        "model": rf,
    }


def rank_l1(X_train, y_train, X_test, y_test, feature_cols: list[str]) -> dict:
    """L1 Logistic Regression: sparse linear selection.
    Features with zero coefficients are irrelevant (under linear assumption).
    Good for identifying which features have ANY linear signal."""
    lr = LogisticRegression(max_iter=1000, C=0.1, penalty="l1", solver="saga", random_state=42)
    lr.fit(X_train, y_train)
    probs = lr.predict_proba(X_test)[:, 1]
    preds = lr.predict(X_test)
    auc = roc_auc_score(y_test, probs) if len(np.unique(y_test)) > 1 else 0.5
    acc = accuracy_score(y_test, preds)

    # Absolute coefficient magnitude as importance
    importances = np.abs(lr.coef_[0])
    nonzero = np.sum(importances > 0.01)

    return {
        "name": f"L1 Logistic ({nonzero}/{len(feature_cols)} non-zero)",
        "auc": auc,
        "accuracy": acc,
        "importances": importances,
        "importances_std": np.zeros(len(feature_cols)),  # No std for coefficients
        "model": lr,
        "nonzero_count": nonzero,
    }


def rank_mutual_info(X_train, y_train, X_test, y_test, feature_cols: list[str]) -> dict:
    """Mutual Information: model-free, captures any statistical dependency.
    No assumptions about linearity or functional form.
    Blind to feature interactions (evaluates each feature independently)."""
    mi_scores = mutual_info_classif(X_train, y_train, random_state=42)

    # MI doesn't produce predictions, so no AUC. Use the best other model for that.
    return {
        "name": "Mutual Information",
        "auc": None,
        "accuracy": None,
        "importances": mi_scores,
        "importances_std": np.zeros(len(feature_cols)),
        "model": None,
    }


# Registry: add new methods here
RANKING_METHODS = {
    "gbm": rank_gbm,
    "rf": rank_rf,
    "l1": rank_l1,
    "mutual_info": rank_mutual_info,
}


# ── Validation ───────────────────────────────────────────────────────────

def run_validation(feat: pd.DataFrame, stock_name: str, methods: list[str]) -> dict:
    """Walk-forward validation with multiple ranking methods.

    Args:
        feat: Feature DataFrame with 'target' column
        stock_name: Display name
        methods: List of method keys from RANKING_METHODS, or ["all"]
    """
    feature_cols = [c for c in feat.columns if c not in EXCLUDE_COLS]
    clean = feat.dropna(subset=feature_cols + ["target"])

    if len(clean) < 200:
        print(f"  {stock_name}: insufficient data ({len(clean)} rows)")
        return {}

    X = StandardScaler().fit_transform(clean[feature_cols].values)
    y = clean["target"].values
    split = int(len(X) * 0.7)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    baseline = max(y_test.mean(), 1 - y_test.mean())

    print(f"\n{'=' * 60}")
    print(f"{stock_name}")
    print(f"{'=' * 60}")
    print(f"Train: {split} | Test: {len(X) - split} | Features: {len(feature_cols)}")
    print(f"Class balance — Train: {y_train.mean():.1%} up | Test: {y_test.mean():.1%} up")

    if "all" in methods:
        methods = list(RANKING_METHODS.keys())

    # Run each ranking method
    method_results = {}
    for method_key in methods:
        if method_key not in RANKING_METHODS:
            print(f"  Unknown method: {method_key}")
            continue
        result = RANKING_METHODS[method_key](X_train, y_train, X_test, y_test, feature_cols)
        method_results[method_key] = result

        auc_str = f"AUC={result['auc']:.3f}" if result["auc"] is not None else "N/A (no predictions)"
        acc_str = f"Acc={result['accuracy']:.1%}" if result["accuracy"] is not None else ""
        print(f"\n  {result['name']}: {auc_str} {acc_str} (baseline {baseline:.1%})")

    # Print consolidated feature ranking
    print(f"\n  {'─' * 70}")
    print(f"  Feature Rankings (top 15 per method):")
    print(f"  {'─' * 70}")

    # Build importance DataFrames per method
    imp_dfs = {}
    for method_key, result in method_results.items():
        imp_df = pd.DataFrame({
            "feature": feature_cols,
            "importance": result["importances"],
            "std": result["importances_std"],
            "category": [categorize_feature(f) for f in feature_cols],
        }).sort_values("importance", ascending=False)
        imp_dfs[method_key] = imp_df

        print(f"\n  [{result['name']}]")
        print(f"  {'Cat':<10} {'Feature':<30} {'Importance':>10} {'Std':>8}")
        for _, row in imp_df.head(15).iterrows():
            print(f"  [{row['category']:<8}] {row['feature']:<30} {row['importance']:>10.4f} {row['std']:>7.4f}")

    # Consensus ranking: average normalized rank across methods
    if len(method_results) > 1:
        print(f"\n  {'─' * 70}")
        print(f"  CONSENSUS RANKING (average rank across {len(method_results)} methods):")
        print(f"  {'─' * 70}")

        rank_df = pd.DataFrame(index=feature_cols)
        for method_key, imp_df in imp_dfs.items():
            # Rank: highest importance = rank 1
            ranked = imp_df.set_index("feature")["importance"].rank(ascending=False)
            rank_df[method_key] = ranked

        rank_df["avg_rank"] = rank_df.mean(axis=1)
        rank_df["category"] = [categorize_feature(f) for f in feature_cols]
        rank_df = rank_df.sort_values("avg_rank")

        print(f"  {'Cat':<10} {'Feature':<30} {'Avg Rank':>10}", end="")
        for mk in method_results:
            print(f" {mk:>8}", end="")
        print()

        for feat_name, row in rank_df.head(20).iterrows():
            print(f"  [{row['category']:<8}] {feat_name:<30} {row['avg_rank']:>10.1f}", end="")
            for mk in method_results:
                print(f" {row[mk]:>8.0f}", end="")
            print()

    # Ablation study (using best predictive model)
    best_method = None
    best_auc = -1
    for mk, res in method_results.items():
        if res["auc"] is not None and res["auc"] > best_auc:
            best_auc = res["auc"]
            best_method = mk

    ablation = {"ALL": best_auc}
    if best_method:
        print(f"\n  Ablation study (using {method_results[best_method]['name']}):")
        for cat_name, cat_filter in CATEGORY_FILTERS.items():
            remaining = [i for i, c in enumerate(feature_cols) if not cat_filter(c)]
            if len(remaining) == len(feature_cols):
                continue
            X_abl_train = X_train[:, remaining]
            X_abl_test = X_test[:, remaining]
            remaining_cols = [feature_cols[i] for i in remaining]

            abl_result = RANKING_METHODS[best_method](X_abl_train, y_train, X_abl_test, y_test, remaining_cols)
            abl_auc = abl_result["auc"] if abl_result["auc"] is not None else 0.5
            ablation[f"Drop {cat_name}"] = abl_auc
            print(f"    Drop {cat_name:<12}: AUC={abl_auc:.3f} (delta: {abl_auc - best_auc:+.3f})")

    return {
        "methods": {mk: {"auc": r["auc"], "accuracy": r["accuracy"], "name": r["name"]}
                    for mk, r in method_results.items()},
        "importances": imp_dfs,
        "consensus": rank_df if len(method_results) > 1 else None,
        "ablation": ablation,
        "baseline": baseline,
    }


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Feature engineering and ranking for stock prediction (example script)",
        epilog="This is a reference implementation. See quant-models/references/feature-engineering.md for the full framework.",
    )
    parser.add_argument("--sector", choices=list(BUILTIN_CONFIGS.keys()), help="Built-in sector config")
    parser.add_argument("--config", help="Path to custom config JSON file")
    parser.add_argument("--output", help="Output directory (default: output/<sector>_features)")
    parser.add_argument("--method", default="all",
                        help=f"Ranking method: {', '.join(RANKING_METHODS.keys())}, or 'all' (default: all)")
    parser.add_argument("--horizon", type=int, help="Override target horizon (days)")
    args = parser.parse_args()

    if args.config:
        config = json.loads(Path(args.config).read_text())
    elif args.sector:
        config = BUILTIN_CONFIGS[args.sector]
    else:
        parser.error("Provide --sector or --config")
        return

    if args.horizon:
        config["target_horizon"] = args.horizon

    methods = [args.method] if args.method != "all" else ["all"]

    sector_name = config["name"]
    start = config.get("start", "2023-01-01")
    end = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(args.output) if args.output else Path(f"output/{sector_name.lower().replace(' ', '_')}_features")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(f"FEATURE ENGINEERING: {sector_name}")
    print(f"Period: {start} — {end}")
    print(f"Methods: {', '.join(methods) if 'all' not in methods else 'all (' + ', '.join(RANKING_METHODS.keys()) + ')'}")
    print(f"Target: {config.get('target_horizon', 5)}-day forward return direction")
    print("=" * 80)

    # Fetch external signals
    signals = config.get("signals", {})
    eq_df = pd.DataFrame()
    wx_df = pd.DataFrame()

    if signals.get("type") == "geo":
        eq_locs = signals.get("earthquake_locations", {})
        wx_locs = signals.get("weather_locations", {})

        if eq_locs:
            print("\nFetching earthquake data...")
            eq_df = fetch_earthquakes(
                eq_locs, start, end,
                min_mag=signals.get("earthquake_min_mag", 3.0),
                radius_km=signals.get("earthquake_radius_km", 500),
            )
            print(f"  {len(eq_df)} earthquakes")

        if wx_locs:
            print("Fetching weather data...")
            wx_df = fetch_weather(wx_locs, start, end)
            print(f"  {len(wx_df)} weather records")

    # Fetch prices
    print("\nFetching stock prices...")
    all_tickers = list(config["stocks"].keys()) + list(config.get("cross_assets", {}).keys())
    si = config.get("sector_index")
    if si:
        all_tickers.append(si)
    prices = fetch_prices(all_tickers, start, end)
    print(f"  {len(prices)} tickers loaded")

    # Build features
    print("\n" + "=" * 80)
    print("BUILDING FEATURES")
    print("=" * 80)

    all_features = {}
    for ticker, name in config["stocks"].items():
        feat = build_all_features(ticker, prices, config, eq_df, wx_df)
        if feat is not None:
            all_features[ticker] = feat
            print(f"  {name}: {feat.shape[1]} features, {feat.shape[0]} observations")

    # Validate
    print("\n" + "=" * 80)
    print("VALIDATION & RANKING")
    print("=" * 80)

    results = {}
    for ticker, name in config["stocks"].items():
        if ticker in all_features:
            results[name] = run_validation(all_features[ticker], name, methods)

    # Save outputs
    print("\n" + "=" * 80)
    print("SAVING OUTPUTS")
    print("=" * 80)

    # Feature matrices
    for ticker, name in config["stocks"].items():
        if ticker in all_features:
            fname = name.replace(" ", "_").replace("&", "and")
            all_features[ticker].to_csv(out_dir / f"features_{fname}.csv")

    # Feature spec (tiered, from consensus ranking)
    for name, res in results.items():
        if res.get("consensus") is not None:
            consensus = res["consensus"]
            n = len(consensus)
            tier1 = consensus[consensus["avg_rank"] <= n * 0.3].index.tolist()
            tier2 = consensus[(consensus["avg_rank"] > n * 0.3) & (consensus["avg_rank"] <= n * 0.7)].index.tolist()
            tier3 = consensus[consensus["avg_rank"] > n * 0.7].index.tolist()

            spec = {"tier1_always_include": tier1, "tier2_adds_lift": tier2, "tier3_marginal": tier3}
            fname = name.replace(" ", "_").replace("&", "and")
            (out_dir / f"feature_spec_{fname}.json").write_text(json.dumps(spec, indent=2))

    # Summary
    summary = {
        "sector": sector_name,
        "period": f"{start} to {end}",
        "target_horizon": config.get("target_horizon", 5),
        "methods": list(RANKING_METHODS.keys()) if "all" in methods else methods,
        "stocks": list(config["stocks"].values()),
        "results": {},
    }
    for name, res in results.items():
        if res:
            summary["results"][name] = {
                "methods": res.get("methods", {}),
                "ablation": res.get("ablation", {}),
                "baseline": res.get("baseline"),
            }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"  Summary: {out_dir / 'summary.json'}")

    for ticker, name in config["stocks"].items():
        if ticker in all_features:
            fname = name.replace(" ", "_").replace("&", "and")
            print(f"  Features: {out_dir / f'features_{fname}.csv'}")
            if (out_dir / f"feature_spec_{fname}.json").exists():
                print(f"  Spec: {out_dir / f'feature_spec_{fname}.json'}")

    print(f"\nDone. Outputs in {out_dir}/")


if __name__ == "__main__":
    main()
