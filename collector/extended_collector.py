"""
collector/extended_collector.py
Extended OS metrics:
  - Per-core CPU usage (each of the 16 cores individually)
  - Disk Read/Write speed (MB/s)
  - Network Upload/Download speed (MB/s)
  - System info (OS, hostname, CPU model, RAM total, uptime)
OS Concept: Demonstrates granular kernel resource monitoring.
"""

import psutil
import platform
import socket
import time
import os

_prev_disk_io  = psutil.disk_io_counters()
_prev_net_io   = psutil.net_io_counters()
_prev_time     = time.time()


def get_per_core_cpu() -> list[float]:
    """
    OS Concept: Each core runs its own scheduler queue.
    Returns individual utilization per logical CPU core.
    """
    return psutil.cpu_percent(interval=0.5, percpu=True)


def get_disk_io_speed() -> dict:
    """
    OS Concept: Disk I/O managed by the OS block device layer.
    Returns read/write throughput in MB/s since last call.
    """
    global _prev_disk_io, _prev_time
    curr = psutil.disk_io_counters()
    now  = time.time()

    if curr is None or _prev_disk_io is None:
        _prev_disk_io = curr
        _prev_time    = now
        return {"read_mbps": 0.0, "write_mbps": 0.0, "read_count": 0, "write_count": 0}

    dt = max(now - _prev_time, 0.001)
    read_speed  = (curr.read_bytes  - _prev_disk_io.read_bytes)  / dt / (1024*1024)
    write_speed = (curr.write_bytes - _prev_disk_io.write_bytes) / dt / (1024*1024)

    _prev_disk_io = curr
    _prev_time    = now

    return {
        "read_mbps":  round(read_speed,  3),
        "write_mbps": round(write_speed, 3),
        "read_count":  curr.read_count,
        "write_count": curr.write_count,
    }


def get_network_speed() -> dict:
    """
    OS Concept: Network I/O counters maintained by kernel network stack.
    Returns upload/download speed in MB/s since last call.
    """
    global _prev_net_io
    curr = psutil.net_io_counters()
    dt   = 1.0  # approximate

    upload   = (curr.bytes_sent - _prev_net_io.bytes_sent) / dt / (1024*1024)
    download = (curr.bytes_recv - _prev_net_io.bytes_recv) / dt / (1024*1024)

    _prev_net_io = curr

    return {
        "upload_mbps":   round(upload,   4),
        "download_mbps": round(download, 4),
        "packets_sent":  curr.packets_sent,
        "packets_recv":  curr.packets_recv,
    }


def get_system_info() -> dict:
    """
    OS Concept: System calls to kernel for hardware/OS identification.
    Returns static system identity card.
    """
    uname = platform.uname()
    boot  = psutil.boot_time()
    uptime_secs = time.time() - boot
    hours   = int(uptime_secs // 3600)
    minutes = int((uptime_secs % 3600) // 60)

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "hostname":     socket.gethostname(),
        "os":           f"{uname.system} {uname.release}",
        "architecture": uname.machine,
        "cpu_model":    uname.processor or platform.processor() or "Unknown",
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical":  psutil.cpu_count(logical=True),
        "cpu_freq_mhz": round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else 0,
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_used_gb":  round(mem.used  / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_used_gb":  round(disk.used  / (1024**3), 2),
        "python_version": platform.python_version(),
        "uptime":       f"{hours}h {minutes}m",
        "boot_time":    time.strftime("%Y-%m-%d %H:%M", time.localtime(boot)),
    }


def get_memory_detail() -> dict:
    """Detailed memory breakdown."""
    m = psutil.virtual_memory()
    s = psutil.swap_memory()
    return {
        "total_gb":     round(m.total     / (1024**3), 2),
        "available_gb": round(m.available / (1024**3), 2),
        "used_gb":      round(m.used      / (1024**3), 2),
        "cached_gb":    round(getattr(m, "cached", 0) / (1024**3), 2),
        "percent":      m.percent,
        "swap_used_gb": round(s.used  / (1024**3), 2),
        "swap_total_gb":round(s.total / (1024**3), 2),
        "swap_percent": s.percent,
    }


def kill_process(pid: int) -> dict:
    """
    OS Concept: Process termination via OS kill signal (SIGTERM).
    """
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        return {"success": True, "message": f"Process '{name}' (PID {pid}) terminated."}
    except psutil.NoSuchProcess:
        return {"success": False, "message": f"PID {pid} not found."}
    except psutil.AccessDenied:
        return {"success": False, "message": f"Access denied — cannot kill PID {pid}."}
    except Exception as e:
        return {"success": False, "message": str(e)}
