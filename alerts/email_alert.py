"""
alerts/email_alert.py
Sends email alerts when critical thresholds are crossed.
Uses Python's built-in smtplib — no paid API needed.
Works with Gmail (use App Password, not your real password).
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Config — edit these ───────────────────────────────────────────────────────
# Store credentials in environment variables or fill directly for demo
SENDER_EMAIL    = os.environ.get("ALERT_SENDER", "")
SENDER_PASSWORD = os.environ.get("ALERT_PASSWORD", "")   # Gmail App Password
RECEIVER_EMAIL  = os.environ.get("ALERT_RECEIVER", "")

_last_email_time: dict[str, float] = {}
EMAIL_COOLDOWN_SECONDS = 300   # Don't spam — max 1 email per metric per 5 min


def is_configured() -> bool:
    return bool(SENDER_EMAIL and SENDER_PASSWORD and RECEIVER_EMAIL)


def send_alert_email(subject: str, body: str, metric: str = "general") -> bool:
    """
    Send an HTML alert email via Gmail SMTP.
    Returns True on success, False on failure.
    """
    if not is_configured():
        return False

    # Cooldown check
    import time
    now = time.time()
    if now - _last_email_time.get(metric, 0) < EMAIL_COOLDOWN_SECONDS:
        return False
    _last_email_time[metric] = now

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🚨 [System Alert] {subject}"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = RECEIVER_EMAIL

        html = f"""
        <html><body style="font-family:Arial,sans-serif;background:#0e1117;color:#fff;padding:20px;">
          <div style="max-width:600px;margin:auto;background:#1a1a2e;border-radius:12px;
                      border:2px solid #ff4444;padding:24px;">
            <h2 style="color:#ff4444;">🚨 System Health Alert</h2>
            <p style="color:#aaa;">Time: <b style="color:#fff;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b></p>
            <hr style="border-color:#333;">
            <p style="font-size:16px;color:#ffcccc;">{body}</p>
            <hr style="border-color:#333;">
            <p style="color:#555;font-size:12px;">AI-Driven System Health Dashboard · Auto-generated alert</p>
          </div>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        print(f"[Email] Alert sent: {subject}")
        return True

    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False


def send_critical_alert(metric: str, value: float):
    subject = f"{metric.upper()} Critical — {value:.1f}%"
    body    = (f"<b>{metric.upper()}</b> usage has reached <b style='color:#ff4444'>{value:.1f}%</b> "
               f"which exceeds the critical threshold.<br><br>"
               f"Immediate attention required to prevent system failure.")
    return send_alert_email(subject, body, metric)


def send_prediction_alert(metric: str, predicted: float):
    subject = f"{metric.upper()} Predicted to reach {predicted:.1f}%"
    body    = (f"AI model predicts <b>{metric.upper()}</b> will reach "
               f"<b style='color:#ffaa00'>{predicted:.1f}%</b> soon.<br><br>"
               f"Proactive action recommended before threshold is crossed.")
    return send_alert_email(subject, body, f"pred_{metric}")
