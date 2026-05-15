"""
alerts/alert_manager.py
Threshold-based alert system + desktop notifications + prediction alerts.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import insert_alert, insert_anomaly
from alerts.notifier import notify_cpu, notify_memory, notify_disk, notify_prediction

# ── Thresholds (mutable — updated by dashboard sliders) ───────────────────────
THRESHOLDS = {
    "cpu":    {"warning": 70, "critical": 85},
    "memory": {"warning": 75, "critical": 90},
    "disk":   {"warning": 80, "critical": 95},
}

# Track last fired severity per metric to avoid spam
# Structure: metric -> {"fire_key": (severity, bucket), "thresholds": (warn, crit)}
_last_fired: dict = {}

# Track previous threshold values to detect changes
_prev_thresholds: dict = {}


def _severity(metric: str, value: float):
    t = THRESHOLDS.get(metric, {})
    if value >= t.get("critical", 101):
        return "critical"
    if value >= t.get("warning", 101):
        return "warning"
    return None


def update_thresholds(cpu_warn=70, cpu_crit=85,
                      mem_warn=75, mem_crit=90,
                      disk_warn=80, disk_crit=95):
    """Called every refresh from dashboard sliders.
    Resets _last_fired for any metric whose thresholds changed,
    so the new limits are evaluated fresh immediately.
    """
    new = {
        "cpu":    {"warning": cpu_warn,  "critical": cpu_crit},
        "memory": {"warning": mem_warn,  "critical": mem_crit},
        "disk":   {"warning": disk_warn, "critical": disk_crit},
    }
    for metric, vals in new.items():
        if _prev_thresholds.get(metric) != vals:
            # Threshold changed — reset so crossing is re-evaluated now
            _last_fired[metric] = None
            _prev_thresholds[metric] = vals

    THRESHOLDS["cpu"]    = new["cpu"]
    THRESHOLDS["memory"] = new["memory"]
    THRESHOLDS["disk"]   = new["disk"]


def check_and_raise_alerts(cpu: float, memory: float, disk: float):
    """
    Check live values against current thresholds.
    Fires desktop notification + logs to DB on each new threshold crossing.
    Uses value_bucket (rounded to 5%) so re-fires if value changes significantly.
    """
    readings = {"cpu": cpu, "memory": memory, "disk": disk}

    for metric, value in readings.items():
        sev = _severity(metric, value)

        # Use (severity, bucket) as key — re-fires if value jumps 5%+ in same severity
        bucket = int(value // 5)
        fire_key = (sev, bucket)

        last = _last_fired.get(metric)
        if sev and last != fire_key:
            msg = (
                f"{metric.upper()} is {value:.1f}% — "
                f"{'CRITICAL' if sev == 'critical' else 'WARNING'} "
                f"(threshold: {THRESHOLDS[metric][sev]}%)"
            )
            insert_alert(f"{metric}_{sev}", msg)
            insert_anomaly(metric, value, sev)
            print(f"[Alert] {msg}")

            # 🔔 Desktop notification
            if metric == "cpu":
                notify_cpu(value, sev)
            elif metric == "memory":
                notify_memory(value, sev)
            elif metric == "disk":
                notify_disk(value, sev)

            _last_fired[metric] = fire_key

        elif not sev:
            # Reset when value drops back to normal — allows re-fire next breach
            _last_fired[metric] = None


def check_prediction_alert(metric: str, predicted_value: float):
    sev = _severity(metric, predicted_value)
    if sev:
        msg = (
            f"PREDICTION: {metric.upper()} forecast to reach "
            f"{predicted_value:.1f}% — {sev.upper()} ahead."
        )
        insert_alert(f"{metric}_predicted_{sev}", msg)
        print(f"[Alert][Prediction] {msg}")
        notify_prediction(metric, predicted_value)
        return msg
    return None


def get_threshold_config() -> dict:
    return THRESHOLDS
