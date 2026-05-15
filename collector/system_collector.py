"""
collector/system_collector.py
Collects real-time OS-level metrics using psutil system calls.
OS Concept: Demonstrates CPU scheduling, memory management, disk I/O, and process management.
"""

import psutil
import time
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db_manager import (
    init_db, insert_metric, insert_top_processes, count_metrics
)
from alerts.alert_manager import check_and_raise_alerts

# ── Configuration ─────────────────────────────────────────────────────────────
COLLECTION_INTERVAL_SECONDS = 3   # Collect every 3 seconds
TOP_PROCESS_COUNT = 5
_prev_net = psutil.net_io_counters()


def get_cpu_usage() -> float:
    """
    OS Concept: CPU utilization = percentage of time CPU spent on non-idle tasks.
    Reflects process scheduling and context-switching overhead.
    """
    return psutil.cpu_percent(interval=1)


def get_memory_usage() -> float:
    """
    OS Concept: Virtual memory management — percentage of RAM in use.
    High values indicate potential page-fault / swap pressure.
    """
    return psutil.virtual_memory().percent


def get_disk_usage(path: str = "/") -> float:
    """
    OS Concept: File-system disk utilization percentage.
    Tracks storage allocation managed by the OS kernel.
    """
    try:
        return psutil.disk_usage(path).percent
    except PermissionError:
        return 0.0


def get_network_bytes() -> tuple[float, float]:
    """
    Return MB sent/received since last call (delta).
    OS Concept: Network I/O counters maintained by the OS network stack.
    """
    global _prev_net
    curr = psutil.net_io_counters()
    sent = round((curr.bytes_sent - _prev_net.bytes_sent) / (1024 * 1024), 4)
    recv = round((curr.bytes_recv - _prev_net.bytes_recv) / (1024 * 1024), 4)
    _prev_net = curr
    return sent, recv


def get_top_processes(n: int = TOP_PROCESS_COUNT) -> list[dict]:
    """
    OS Concept: Process table inspection — enumerates running processes
    and their resource consumption (CPU scheduling, memory allocation).
    """
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            if info["cpu_percent"] is not None:
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "Unknown",
                    "cpu_percent": round(info["cpu_percent"], 2),
                    "mem_percent": round(info["memory_percent"] or 0, 2),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return sorted(procs, key=lambda x: x["cpu_percent"], reverse=True)[:n]


def collect_snapshot() -> dict:
    """Collect one complete system snapshot and persist it."""
    cpu    = get_cpu_usage()
    memory = get_memory_usage()
    disk   = get_disk_usage()
    net_s, net_r = get_network_bytes()
    procs  = get_top_processes()

    insert_metric(cpu, memory, disk, net_s, net_r)
    insert_top_processes(procs)
    check_and_raise_alerts(cpu, memory, disk)

    return {
        "cpu": cpu, "memory": memory, "disk": disk,
        "net_sent": net_s, "net_recv": net_r,
        "top_processes": procs,
    }


def run_collector(verbose: bool = True):
    """
    Main collection loop — continuously gathers system metrics.
    Run this in a background thread or separate process.
    """
    init_db()
    print(f"[Collector] Starting — interval={COLLECTION_INTERVAL_SECONDS}s")

    while True:
        try:
            snap = collect_snapshot()
            if verbose:
                print(
                    f"[Collector] CPU={snap['cpu']}%  MEM={snap['memory']}%  "
                    f"DISK={snap['disk']}%  Total rows={count_metrics()}"
                )
        except Exception as exc:
            print(f"[Collector] Error: {exc}")
        time.sleep(COLLECTION_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_collector()
