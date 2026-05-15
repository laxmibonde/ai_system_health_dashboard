# 🖥️ AI-Driven System Health Dashboard

> **An engineering-level OS + AI + Systems project** — Real-time system monitoring
> with machine learning-based prediction and anomaly detection.

---

## 📦 Project Structure

```
ai_system_dashboard/
│
├── collector/            → OS-level data collection (psutil / system calls)
│   └── system_collector.py
│
├── backend/              → Flask REST API
│   └── app.py
│
├── ai_model/             → ML prediction + anomaly detection
│   └── predictor.py      (Linear Regression · Random Forest · Isolation Forest)
│
├── database/             → SQLite storage layer
│   └── db_manager.py
│
├── frontend/             → Streamlit dashboard UI
│   └── dashboard.py
│
├── alerts/               → Threshold alert system
│   └── alert_manager.py
│
├── main.py               → Orchestrated entry point (all modules)
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the dashboard (recommended — simplest)
```bash
streamlit run frontend/dashboard.py
```
Open **http://localhost:8501** in your browser.

### 3. Run everything together (collector + API + dashboard)
```bash
python main.py
```

### 4. Run components individually
```bash
# Collector only
python collector/system_collector.py

# Flask API only
python backend/app.py

# Streamlit only
streamlit run frontend/dashboard.py
```

---

## 🧠 AI Models Used

| Model | Purpose | Library |
|---|---|---|
| **Linear Regression** | Baseline CPU/Memory/Disk trend prediction | scikit-learn |
| **Random Forest** | Higher-accuracy multi-feature prediction | scikit-learn |
| **Isolation Forest** | Unsupervised anomaly detection | scikit-learn |

---

## ⚙️ OS Concepts Applied

| Concept | Where Used |
|---|---|
| **CPU Scheduling** | `psutil.cpu_percent()` — utilization of scheduled processes |
| **Memory Management** | `psutil.virtual_memory()` — RAM allocation tracking |
| **Disk I/O** | `psutil.disk_usage()` — file-system block allocation |
| **Process Table** | `psutil.process_iter()` — OS process enumeration |
| **System Calls** | All psutil reads invoke kernel system calls |
| **Resource Allocation** | Threshold alerts reflect OS resource exhaustion signals |

---

## 📡 Flask API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Service health check |
| `/api/snapshot` | GET | Collect one live metric snapshot |
| `/api/metrics` | GET | Recent metric history |
| `/api/predict` | GET | AI forecasts (LR + RF) |
| `/api/anomaly/current` | GET | Anomaly check on live snapshot |
| `/api/anomaly/history` | GET | Historical anomaly records |
| `/api/alerts` | GET | Recent system alerts |
| `/api/processes` | GET | Top CPU-consuming processes |
| `/api/train` | GET/POST | Retrain all AI models |
| `/api/thresholds` | GET | Alert threshold config |

---

## 🎯 Features

- ✅ Real-time CPU, Memory, Disk, Network monitoring
- ✅ SQLite persistent time-series storage
- ✅ Linear Regression + Random Forest predictions with MAE/RMSE comparison
- ✅ Isolation Forest anomaly detection
- ✅ Threshold-based alert system (warning + critical levels)
- ✅ Forward-looking prediction alerts
- ✅ Top 5 CPU-consuming processes view
- ✅ Auto-refreshing Streamlit dashboard (every 5 seconds)
- ✅ Full Flask REST API backend
- ✅ All free — zero paid APIs

---

## 🗣️ Viva / Interview Answer

> *"This project monitors system resources in real time using OS-level system calls
> via psutil, reflecting core OS concepts like CPU scheduling, virtual memory
> management, and process table enumeration. Historical metrics are stored in SQLite
> for time-series analysis. Two ML models — Linear Regression as a baseline and
> Random Forest for improved accuracy — forecast future resource usage.
> An Isolation Forest detects anomalous system behaviour such as memory leaks
> or unexpected CPU spikes. A Flask REST API decouples the data layer from the
> Streamlit frontend, and a rule-based alert system triggers warnings before
> resource exhaustion occurs."*

---

## 🏆 Technologies

`Python` · `psutil` · `scikit-learn` · `Flask` · `Streamlit` · `Plotly` · `SQLite` · `pandas` · `numpy`
