"""
alerts/notifier.py
Windows desktop notifications using ctypes MessageBox (confirmed working).
Runs in a background thread so it never blocks the Streamlit dashboard.
"""

import sys
import time
import threading
import subprocess
import ctypes

_last_notif_time: dict = {}
COOLDOWN_SECONDS = 20


def _can_notify(key: str) -> bool:
    now = time.time()
    if now - _last_notif_time.get(key, 0) >= COOLDOWN_SECONDS:
        _last_notif_time[key] = now
        return True
    return False


# ── MB icon constants ─────────────────────────────────────────────────────────
MB_ICONWARNING    = 0x00000030   # yellow triangle  — for WARNING
MB_ICONSTOP       = 0x00000010   # red X            — for CRITICAL
MB_ICONINFO       = 0x00000040   # blue i           — for info
MB_OK             = 0x00000000
MB_SYSTEMMODAL    = 0x00001000   # stays on top of all windows


def _ctypes_popup(title: str, message: str, severity: str = "warning"):
    """
    Show a Windows MessageBox dialog.
    Confirmed working on this machine.
    Runs in its own thread — won't block the dashboard.
    """
    if severity == "critical":
        icon = MB_ICONSTOP
    else:
        icon = MB_ICONWARNING

    flags = MB_OK | icon | MB_SYSTEMMODAL

    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, flags)
    except Exception as e:
        print(f"[Notif] ctypes error: {e}")


def _toast_popup(title: str, message: str):
    """
    Windows 10/11 toast via PowerShell — secondary method.
    Non-blocking, fires and forgets.
    """
    t = title.replace("'", "").replace('"', "")
    m = message.replace("'", "").replace('"', "").replace("\n", " ")
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null
[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]|Out-Null
$xml=New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast duration="long"><visual><binding template="ToastGeneric"><text>{t}</text><text>{m}</text></binding></visual><audio src="ms-winsoundevent:Notification.Looping.Alarm"/></toast>')
$toast=[Windows.UI.Notifications.ToastNotification]::new($xml)
$notifier=[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AI.System.Dashboard')
$notifier.Show($toast)
Start-Sleep -Seconds 6
"""
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        print(f"[Notif] toast error: {e}")


def send_notification(title: str, message: str, key: str = "general",
                      severity: str = "warning"):
    """
    Fire a popup alert in a background thread (non-blocking).
    Uses ctypes MessageBox — confirmed working on this machine.
    Also fires a toast notification alongside it.
    """
    if not _can_notify(key):
        return

    print(f"[ALERT] {title} | {message}")

    def _fire():
        # Fire toast first (non-blocking, appears in corner)
        _toast_popup(title, message)
        # Then show MessageBox (confirmed working — stays until dismissed)
        _ctypes_popup(title, message, severity)

    threading.Thread(target=_fire, daemon=True).start()


# ── Typed helpers ─────────────────────────────────────────────────────────────

def notify_cpu(value: float, severity: str):
    label = "CRITICAL" if severity == "critical" else "WARNING"
    send_notification(
        title=f"CPU {label} — AI Dashboard",
        message=(f"CPU is at {value:.1f}%!\n\n"
                 f"{'Take action NOW!' if severity == 'critical' else 'Monitor closely.'}"),
        key=f"cpu_{severity}",
        severity=severity,
    )


def notify_memory(value: float, severity: str):
    label = "CRITICAL" if severity == "critical" else "WARNING"
    send_notification(
        title=f"Memory {label} — AI Dashboard",
        message=(f"Memory is at {value:.1f}%!\n\n"
                 f"{'Close apps immediately!' if severity == 'critical' else 'Memory usage is high.'}"),
        key=f"memory_{severity}",
        severity=severity,
    )


def notify_disk(value: float, severity: str):
    label = "CRITICAL" if severity == "critical" else "WARNING"
    send_notification(
        title=f"Disk {label} — AI Dashboard",
        message=(f"Disk is at {value:.1f}%!\n\n"
                 f"{'Free up space NOW!' if severity == 'critical' else 'Disk usage is high.'}"),
        key=f"disk_{severity}",
        severity=severity,
    )


def notify_anomaly(cpu: float, memory: float, disk: float, severity: str = "warning"):
    send_notification(
        title="ANOMALY DETECTED — AI Dashboard",
        message=(f"Abnormal system state detected!\n\n"
                 f"CPU:  {cpu:.1f}%\n"
                 f"MEM:  {memory:.1f}%\n"
                 f"DISK: {disk:.1f}%"),
        key="anomaly",
        severity=severity,
    )


def notify_prediction(metric: str, predicted_value: float):
    send_notification(
        title=f"AI Prediction — {metric.upper()} Alert",
        message=(f"AI forecasts {metric.upper()} will reach {predicted_value:.1f}%.\n\n"
                 f"Act before it happens!"),
        key=f"pred_{metric}",
        severity="warning",
    )
