"""
main.py
Entry point for the AI-Driven System Health Dashboard.

Starts:
  1. Database initialization
  2. Background system data collector (thread)
  3. Flask REST API server (thread)
  4. Streamlit dashboard (foreground subprocess)

Usage:
    python main.py
    
Or run components individually:
    python collector/system_collector.py   # collector only
    python backend/app.py                  # API only
    streamlit run frontend/dashboard.py    # dashboard only (recommended)
"""

import sys
import os
import threading
import subprocess
import time

# Ensure project root is on path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from database.db_manager import init_db
from collector.system_collector import run_collector
from backend.app import app as flask_app


def _start_collector():
    """Run collector in a background daemon thread."""
    run_collector(verbose=True)


def _start_flask():
    """Run Flask API in a background daemon thread."""
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


def _start_dashboard():
    """Launch Streamlit dashboard as a subprocess."""
    dashboard_path = os.path.join(ROOT, "frontend", "dashboard.py")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", dashboard_path,
         "--server.port", "8501",
         "--server.headless", "true"],
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  AI-Driven System Health Dashboard")
    print("  OS + AI + Systems Engineering Project")
    print("=" * 60)

    # 1. Initialize database
    print("\n[1/4] Initializing database...")
    init_db()

    # 2. Start collector thread
    print("[2/4] Starting system data collector...")
    collector_thread = threading.Thread(target=_start_collector, daemon=True)
    collector_thread.start()
    time.sleep(2)   # Let it collect a few rows

    # 3. Start Flask API thread
    print("[3/4] Starting Flask API on http://localhost:5000 ...")
    flask_thread = threading.Thread(target=_start_flask, daemon=True)
    flask_thread.start()
    time.sleep(1)

    # 4. Start Streamlit (blocking — keeps process alive)
    print("[4/4] Launching Streamlit dashboard on http://localhost:8501 ...")
    print("\n✅  Dashboard ready! Open http://localhost:8501 in your browser.\n")
    _start_dashboard()
