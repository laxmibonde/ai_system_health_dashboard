"""
ai_model/predictor.py
ML models for resource prediction and anomaly detection.
Models:
  1. Linear Regression  — baseline trend predictor
  2. Random Forest      — higher-accuracy predictor
  3. Isolation Forest   — unsupervised anomaly detector
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings("ignore")

from database.db_manager import fetch_all_metrics
from alerts.alert_manager import check_prediction_alert

# ── Minimum rows required before training ─────────────────────────────────────
MIN_ROWS_FOR_TRAINING = 10
PREDICT_STEPS_AHEAD = 20      # How many steps ahead to forecast


class SystemPredictor:
    """
    Trains Linear Regression and Random Forest on historical system metrics,
    then forecasts CPU, Memory, and Disk usage for the next N time steps.
    """

    def __init__(self):
        self.lr_models: dict[str, LinearRegression] = {}
        self.rf_models: dict[str, RandomForestRegressor] = {}
        self.scaler = StandardScaler()
        self.is_trained = False
        self.metrics_used = ["cpu", "memory", "disk"]
        self.last_index = 0
        self.train_errors: dict = {}

    # ── Feature Engineering ────────────────────────────────────────────────────
    @staticmethod
    def _build_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Create time-based and lag features for supervised learning.
        OS Concept: Historical usage patterns reflect OS scheduling behaviour.
        """
        feat = pd.DataFrame()
        feat["t"] = np.arange(len(df))
        feat["t2"] = feat["t"] ** 2          # capture non-linear trends
        for col in ["cpu", "memory", "disk"]:
            feat[f"{col}_lag1"] = df[col].shift(1).fillna(df[col].mean())
            feat[f"{col}_lag2"] = df[col].shift(2).fillna(df[col].mean())
            feat[f"{col}_roll3"] = df[col].rolling(3, min_periods=1).mean()
        return feat

    # ── Training ───────────────────────────────────────────────────────────────
    def train(self) -> dict:
        """Fetch data from DB and fit both model families."""
        rows = fetch_all_metrics()
        if len(rows) < MIN_ROWS_FOR_TRAINING:
            return {"status": "insufficient_data", "rows": len(rows)}

        df = pd.DataFrame(rows)
        df = df[["cpu", "memory", "disk"]].astype(float)

        X = self._build_features(df)
        self.last_index = len(df)

        for metric in self.metrics_used:
            y = df[metric].values

            # Linear Regression (baseline)
            lr = LinearRegression()
            lr.fit(X, y)
            lr_pred = lr.predict(X)
            lr_mae  = mean_absolute_error(y, lr_pred)

            # Random Forest (improved accuracy)
            rf = RandomForestRegressor(n_estimators=80, max_depth=6,
                                       random_state=42, n_jobs=-1)
            rf.fit(X, y)
            rf_pred = rf.predict(X)
            rf_mae  = mean_absolute_error(y, rf_pred)

            self.lr_models[metric] = lr
            self.rf_models[metric] = rf
            self.train_errors[metric] = {
                "lr_mae":  round(lr_mae, 3),
                "rf_mae":  round(rf_mae, 3),
                "rf_rmse": round(np.sqrt(mean_squared_error(y, rf_pred)), 3),
            }

        self.is_trained = True
        print(f"[AI] Models trained on {len(df)} rows. Errors: {self.train_errors}")
        return {"status": "trained", "rows": len(df), "errors": self.train_errors}

    # ── Prediction ─────────────────────────────────────────────────────────────
    def predict_future(self, steps: int = PREDICT_STEPS_AHEAD) -> dict:
        """
        Forecast metric values for the next `steps` time steps.
        Returns both LR and RF predictions for comparison.
        """
        if not self.is_trained:
            self.train()
        if not self.is_trained:
            return {"status": "not_trained"}

        # Build future feature rows
        rows = fetch_all_metrics()
        df   = pd.DataFrame(rows)[["cpu", "memory", "disk"]].astype(float)
        feat = self._build_features(df)

        # Use last row as seed for lag features
        last_feat = feat.iloc[-1].copy()
        future_X  = []

        for i in range(1, steps + 1):
            row = last_feat.copy()
            row["t"]  = self.last_index + i
            row["t2"] = row["t"] ** 2
            future_X.append(row.values)

        future_X = np.array(future_X)
        col_names = feat.columns.tolist()

        results = {}
        alerts_raised = []
        for metric in self.metrics_used:
            lr_preds = self.lr_models[metric].predict(
                pd.DataFrame(future_X, columns=col_names)
            )
            rf_preds = self.rf_models[metric].predict(
                pd.DataFrame(future_X, columns=col_names)
            )

            # Clamp to valid percentage range
            lr_preds = np.clip(lr_preds, 0, 100).tolist()
            rf_preds = np.clip(rf_preds, 0, 100).tolist()

            results[metric] = {
                "linear_regression": [round(v, 2) for v in lr_preds],
                "random_forest":     [round(v, 2) for v in rf_preds],
            }

            # Check if prediction crosses alert threshold
            max_pred = max(rf_preds)
            alert_msg = check_prediction_alert(metric, max_pred)
            if alert_msg:
                alerts_raised.append(alert_msg)

        return {
            "status": "ok",
            "steps": steps,
            "predictions": results,
            "prediction_alerts": alerts_raised,
            "model_errors": self.train_errors,
        }


class AnomalyDetector:
    """
    Isolation Forest — detects abnormal system behaviour in real time.
    OS Concept: Identifies memory leaks, CPU spikes, or abnormal I/O patterns.
    """

    def __init__(self, contamination: float = 0.05):
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    def train(self) -> dict:
        rows = fetch_all_metrics()
        if len(rows) < MIN_ROWS_FOR_TRAINING:
            return {"status": "insufficient_data", "rows": len(rows)}

        df = pd.DataFrame(rows)[["cpu", "memory", "disk"]].astype(float)
        X  = self.scaler.fit_transform(df)
        self.model.fit(X)
        self.is_trained = True
        print(f"[Anomaly] Isolation Forest trained on {len(df)} rows.")
        return {"status": "trained", "rows": len(df)}

    def detect(self, cpu: float, memory: float, disk: float) -> dict:
        """
        Classify a single snapshot as normal (-1 = anomaly, 1 = normal).
        Returns anomaly flag and per-metric z-scores.
        """
        if not self.is_trained:
            self.train()
        if not self.is_trained:
            return {"status": "not_trained", "is_anomaly": False}

        point = np.array([[cpu, memory, disk]])
        scaled = self.scaler.transform(point)
        pred   = self.model.predict(scaled)[0]          # 1 = normal, -1 = anomaly
        score  = self.model.score_samples(scaled)[0]    # lower = more anomalous

        return {
            "status":     "ok",
            "is_anomaly": bool(pred == -1),
            "anomaly_score": round(float(score), 4),
            "label":      "ANOMALY" if pred == -1 else "Normal",
            "input":      {"cpu": cpu, "memory": memory, "disk": disk},
        }

    def detect_from_history(self, limit: int = 200) -> list[dict]:
        """
        Run anomaly detection over recent history and return flagged rows.
        """
        if not self.is_trained:
            self.train()
        if not self.is_trained:
            return []

        rows = fetch_all_metrics()[-limit:]
        if not rows:
            return []

        df     = pd.DataFrame(rows)[["cpu", "memory", "disk"]].astype(float)
        scaled = self.scaler.transform(df)
        preds  = self.model.predict(scaled)

        anomaly_rows = []
        for i, pred in enumerate(preds):
            if pred == -1:
                anomaly_rows.append({
                    "timestamp": rows[i]["timestamp"],
                    "cpu":    rows[i]["cpu"],
                    "memory": rows[i]["memory"],
                    "disk":   rows[i]["disk"],
                    "label":  "ANOMALY",
                })
        return anomaly_rows


# ── Singleton instances (imported by Flask API) ────────────────────────────────
predictor        = SystemPredictor()
anomaly_detector = AnomalyDetector()


def retrain_all():
    """Retrain both models — call this daily or on demand."""
    p_result = predictor.train()
    a_result = anomaly_detector.train()
    return {"predictor": p_result, "anomaly_detector": a_result}
