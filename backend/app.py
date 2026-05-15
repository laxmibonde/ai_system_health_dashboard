"""
backend/app.py
Flask REST API — exposes system metrics, predictions, anomalies, and alerts
to the Streamlit frontend dashboard.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, jsonify
from flask_cors import CORS

from database.db_manager import (
    init_db,
    fetch_recent_metrics,
    fetch_recent_anomalies,
    fetch_recent_alerts,
    fetch_top_processes_latest,
    count_metrics,
)
from collector.system_collector import collect_snapshot
from ai_model.predictor import predictor, anomaly_detector, retrain_all
from alerts.alert_manager import get_threshold_config

app = Flask(__name__)
CORS(app)   # Allow cross-origin requests from Streamlit


# ── Health ─────────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "total_rows": count_metrics()})


# ── Live Snapshot ──────────────────────────────────────────────────────────────
@app.route("/api/snapshot", methods=["GET"])
def snapshot():
    """Collect one snapshot right now and return it."""
    try:
        data = collect_snapshot()
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Historical Metrics ─────────────────────────────────────────────────────────
@app.route("/api/metrics", methods=["GET"])
@app.route("/api/metrics/<int:limit>", methods=["GET"])
def metrics(limit=150):
    rows = fetch_recent_metrics(limit)
    return jsonify({"status": "ok", "count": len(rows), "data": rows})


# ── Predictions ────────────────────────────────────────────────────────────────
@app.route("/api/predict", methods=["GET"])
@app.route("/api/predict/<int:steps>", methods=["GET"])
def predict(steps=20):
    result = predictor.predict_future(steps=steps)
    return jsonify(result)


# ── Anomaly Detection (latest snapshot) ───────────────────────────────────────
@app.route("/api/anomaly/current", methods=["GET"])
def anomaly_current():
    snap = collect_snapshot()
    result = anomaly_detector.detect(snap["cpu"], snap["memory"], snap["disk"])
    return jsonify(result)


@app.route("/api/anomaly/history", methods=["GET"])
def anomaly_history():
    rows = anomaly_detector.detect_from_history()
    return jsonify({"status": "ok", "count": len(rows), "anomalies": rows})


# ── Alerts ────────────────────────────────────────────────────────────────────
@app.route("/api/alerts", methods=["GET"])
def alerts():
    rows = fetch_recent_alerts(50)
    return jsonify({"status": "ok", "count": len(rows), "data": rows})


@app.route("/api/anomalies", methods=["GET"])
def anomalies():
    rows = fetch_recent_anomalies(50)
    return jsonify({"status": "ok", "count": len(rows), "data": rows})


# ── Processes ─────────────────────────────────────────────────────────────────
@app.route("/api/processes", methods=["GET"])
def processes():
    rows = fetch_top_processes_latest()
    return jsonify({"status": "ok", "data": rows})


# ── Model Training ────────────────────────────────────────────────────────────
@app.route("/api/train", methods=["POST", "GET"])
def train():
    result = retrain_all()
    return jsonify(result)


# ── Thresholds ────────────────────────────────────────────────────────────────
@app.route("/api/thresholds", methods=["GET"])
def thresholds():
    return jsonify(get_threshold_config())


if __name__ == "__main__":
    init_db()
    print("[Flask] Starting API server on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
