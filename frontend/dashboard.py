"""
frontend/dashboard.py  — UPGRADED
New features:
  2. Email Alert System
  3. Process Killer
  4. Dark/Light Theme Toggle
  8. Per-Core CPU Monitor (16 cores)
  9. Disk I/O Monitor (Read/Write MB/s)
 10. Network Speed Monitor
 11. System Info Panel
 12. CPU Heatmap
 13. Sidebar Live Stats (uptime, alert count, anomaly count)
 15. Date Range Filter + CSV Export
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import io

from database.db_manager import (
    init_db, fetch_recent_metrics, fetch_recent_alerts,
    fetch_top_processes_latest, count_metrics, fetch_recent_anomalies,
)
from collector.system_collector import collect_snapshot
from collector.extended_collector import (
    get_per_core_cpu, get_disk_io_speed, get_network_speed,
    get_system_info, get_memory_detail, kill_process,
)
from ai_model.predictor import predictor, anomaly_detector, retrain_all
from alerts.alert_manager import get_threshold_config, update_thresholds, check_and_raise_alerts
from alerts.notifier import notify_anomaly


# ── Init DB ───────────────────────────────────────────────────────────────────
init_db()

# ── Theme state ───────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

dark    = st.session_state.dark_mode
BG      = "#0E1117" if dark else "#f5f7fa"
CARD_BG = "#1a1a2e" if dark else "#ffffff"
PLOT_BG = "#0E1117" if dark else "#ffffff"
FONT_C  = "white"   if dark else "#1a1a2e"
GRID_C  = "#1a2a40" if dark else "#e0e0e0"
BORDER  = "#0f3460" if dark else "#d0d0d0"
ACCENT  = "#00d4ff" if dark else "#0055aa"

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI System Health Dashboard",
    page_icon="🖥️", layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
_global_color = "color: white !important;" if dark else "color: #1a1a2e !important;"
st.markdown(f"""
<style>
  .stApp, .main {{ background-color: {BG} !important; }}

  /* Force ALL text white in dark mode */
  .stApp p, .stApp span, .stApp label, .stApp div,
  .stMarkdown, .stMarkdown p, .stMarkdown span,
  .stText, [data-testid="stText"],
  .stSelectbox label, .stSlider label, .stToggle label,
  .stNumberInput label, .stCaption p,
  .streamlit-expanderHeader {{
      {_global_color}
  }}

  /* Sidebar */
  section[data-testid="stSidebar"] > div {{
      background-color: {"#12121f" if dark else "#eef0f5"} !important;
  }}
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] div {{
      {_global_color}
  }}

  /* Metric cards */
  div[data-testid="metric-container"] {{
      background-color: {CARD_BG} !important;
      border: 1px solid {BORDER} !important;
      border-radius: 10px !important; padding: 14px !important;
  }}
  div[data-testid="metric-container"] * {{ {_global_color} }}

  /* Section titles */
  .section-title {{
      font-size: 20px; font-weight: 700; color: {ACCENT} !important;
      border-bottom: 2px solid {BORDER}; padding-bottom: 6px; margin: 14px 0 10px 0;
  }}

  /* Info cards */
  .info-card {{
      background: {CARD_BG}; border-radius: 10px; padding: 14px;
      border: 1px solid {BORDER}; margin: 4px 0;
  }}
  .info-card, .info-card * {{ {_global_color} }}

  /* Alert boxes */
  .alert-critical {{
      background-color: {"#3d0000" if dark else "#fff0f0"};
      border-left: 5px solid #ff4444; padding: 10px; border-radius: 6px; margin: 4px 0;
      color: {"#ff8888" if dark else "#cc0000"} !important; font-size: 13px;
  }}
  .alert-warning {{
      background-color: {"#3d2800" if dark else "#fffbe6"};
      border-left: 5px solid #ffaa00; padding: 10px; border-radius: 6px; margin: 4px 0;
      color: {"#ffcc66" if dark else "#996600"} !important; font-size: 13px;
  }}
  .alert-ok {{
      background-color: {"#003d00" if dark else "#f0fff4"};
      border-left: 5px solid #00cc44; padding: 10px; border-radius: 6px; margin: 4px 0;
      color: {"#66ff99" if dark else "#006622"} !important; font-size: 13px;
  }}

  /* Dataframe */
  .stDataFrame, .stDataFrame * {{ {_global_color} }}

  /* Captions dimmer */
  .stCaption, .stCaption p {{ color: {"#aaaaaa" if dark else "#666666"} !important; }}

  /* All buttons — force white text in dark mode */
  .stButton > button {{
      color: {"white" if dark else "#1a1a2e"} !important;
      border: 1px solid {BORDER} !important;
  }}
  .stButton > button:hover,
  .stButton > button:focus,
  .stButton > button:active {{
      color: {"white" if dark else "#1a1a2e"} !important;
  }}
  .stButton > button[kind="primary"],
  .stButton > button[kind="primary"]:hover {{
      color: white !important;
  }}
  /* Download button */
  .stDownloadButton button {{
      color: {"white" if dark else "#1a1a2e"} !important;
      border: 1px solid {BORDER} !important;
  }}
  .stDownloadButton button:hover {{
      color: {"white" if dark else "#1a1a2e"} !important;
  }}
  /* Form submit buttons */
  .stFormSubmitButton > button {{
      color: {"white" if dark else "#1a1a2e"} !important;
  }}
</style>
""", unsafe_allow_html=True)

COLORS = {"cpu":"#00d4ff","memory":"#ff6b6b","disk":"#ffd93d","net":"#6bcb77","write":"#ff6b6b"}

# ══════════════════════════════════════════════════════════════════════════════
# Chart helpers
# ══════════════════════════════════════════════════════════════════════════════
def gauge(value, title, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=value,
        title={"text":title,"font":{"size":14,"color":FONT_C}},
        number={"suffix":"%","font":{"color":color,"size":28}},
        gauge={"axis":{"range":[0,100],"tickcolor":"gray"},"bar":{"color":color},
               "bgcolor":CARD_BG,
               "steps":[{"range":[0,50],"color":PLOT_BG},
                        {"range":[50,75],"color":CARD_BG},
                        {"range":[75,100],"color":"#2a1a1a" if dark else "#fff0f0"}],
               "threshold":{"line":{"color":"red","width":3},"thickness":0.8,"value":80}},
    ))
    fig.update_layout(height=200,margin=dict(l=20,r=20,t=40,b=10),
                      paper_bgcolor=BG,font_color=FONT_C)
    return fig

def line_chart(df):
    fig = make_subplots(rows=3,cols=1,shared_xaxes=True,
                        subplot_titles=("CPU %","Memory %","Disk %"),vertical_spacing=0.08)
    for i,(col,color) in enumerate(
        [("cpu",COLORS["cpu"]),("memory",COLORS["memory"]),("disk",COLORS["disk"])],1):
        r,g,b = int(color[1:3],16),int(color[3:5],16),int(color[5:7],16)
        fig.add_trace(go.Scatter(x=df["timestamp"],y=df[col],name=col.upper(),
            line=dict(color=color,width=2),fill="tozeroy",
            fillcolor=f"rgba({r},{g},{b},0.08)"),row=i,col=1)
    fig.update_layout(height=400,paper_bgcolor=BG,plot_bgcolor=PLOT_BG,
                      font_color=FONT_C,showlegend=True,margin=dict(l=40,r=20,t=40,b=20))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(range=[0,105],showgrid=True,gridcolor=GRID_C)
    return fig

def prediction_chart(pred_data, history_df):
    fig  = go.Figure()
    cfg  = [("cpu",COLORS["cpu"],"CPU"),("memory",COLORS["memory"],"Memory"),
            ("disk",COLORS["disk"],"Disk")]
    n    = len(history_df)
    for metric,color,label in cfg:
        fig.add_trace(go.Scatter(x=list(range(n)),y=history_df[metric].tolist(),
            name=f"{label} (actual)",line=dict(color=color,width=2)))
    pred_x = list(range(n, n+pred_data.get("steps",20)))
    for metric,color,label in cfg:
        rf = pred_data.get("predictions",{}).get(metric,{}).get("random_forest",[])
        lr = pred_data.get("predictions",{}).get(metric,{}).get("linear_regression",[])
        if rf: fig.add_trace(go.Scatter(x=pred_x,y=rf,name=f"{label} RF",
                                        line=dict(color=color,width=2,dash="dot")))
        if lr: fig.add_trace(go.Scatter(x=pred_x,y=lr,name=f"{label} LR",
                                        line=dict(color=color,width=1,dash="dash"),opacity=0.5))
    fig.add_vline(x=n-1,line_dash="dash",line_color="gray",
                  annotation_text="Now",annotation_font_color=FONT_C)
    fig.update_layout(height=400,paper_bgcolor=BG,plot_bgcolor=PLOT_BG,font_color=FONT_C,
                      yaxis=dict(range=[0,105]),margin=dict(l=40,r=20,t=30,b=20),
                      legend=dict(bgcolor=CARD_BG,bordercolor=BORDER))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True,gridcolor=GRID_C)
    return fig

def per_core_chart(core_values):
    colors = ["#ff4444" if v>80 else "#ffaa00" if v>50 else "#00d4ff" for v in core_values]
    fig = go.Figure(go.Bar(
        x=[f"C{i}" for i in range(len(core_values))], y=core_values,
        marker_color=colors,
        text=[f"{v:.0f}%" for v in core_values], textposition="outside",
    ))
    fig.update_layout(height=260,paper_bgcolor=BG,plot_bgcolor=PLOT_BG,font_color=FONT_C,
                      yaxis=dict(range=[0,115]),margin=dict(l=20,r=20,t=20,b=20),
                      xaxis_title="Core",yaxis_title="Usage %")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True,gridcolor=GRID_C)
    return fig

def io_net_chart(hist_df, sent_col, recv_col, sent_label, recv_label, sent_color, recv_color):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist_df["timestamp"],y=hist_df.get(sent_col,[0]*len(hist_df)),
        name=sent_label,line=dict(color=sent_color,width=2),fill="tozeroy",
        fillcolor=f"rgba({int(sent_color[1:3],16)},{int(sent_color[3:5],16)},{int(sent_color[5:7],16)},0.08)"))
    fig.add_trace(go.Scatter(x=hist_df["timestamp"],y=hist_df.get(recv_col,[0]*len(hist_df)),
        name=recv_label,line=dict(color=recv_color,width=2),fill="tozeroy",
        fillcolor=f"rgba({int(recv_color[1:3],16)},{int(recv_color[3:5],16)},{int(recv_color[5:7],16)},0.08)"))
    fig.update_layout(height=220,paper_bgcolor=BG,plot_bgcolor=PLOT_BG,font_color=FONT_C,
                      yaxis_title="MB/s",margin=dict(l=40,r=20,t=20,b=20),
                      legend=dict(bgcolor=CARD_BG))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True,gridcolor=GRID_C)
    return fig

def cpu_heatmap(hist_df):
    vals = hist_df["cpu"].values[-60:]
    cols = 10
    rows = len(vals)//cols
    if rows < 1:
        return None
    grid = vals[:rows*cols].reshape(rows,cols)
    fig  = go.Figure(go.Heatmap(
        z=grid,
        colorscale=[[0.0,"#003d00"],[0.5,"#ffaa00"],[1.0,"#ff0000"]],
        zmin=0,zmax=100,showscale=True,
        colorbar=dict(title="CPU %",tickfont=dict(color=FONT_C)),
    ))
    fig.update_layout(height=220,paper_bgcolor=BG,plot_bgcolor=PLOT_BG,font_color=FONT_C,
                      xaxis_title="Sample",yaxis_title="Time bucket",
                      margin=dict(l=40,r=20,t=20,b=20))
    return fig

def process_bar(processes):
    if not processes: return go.Figure()
    df = pd.DataFrame(processes).sort_values("cpu_percent")
    fig = go.Figure(go.Bar(x=df["cpu_percent"],y=df["name"],orientation="h",
        marker_color=COLORS["cpu"],
        text=[f"{v:.1f}%" for v in df["cpu_percent"]],textposition="outside"))
    fig.update_layout(height=240,paper_bgcolor=BG,plot_bgcolor=PLOT_BG,
                      font_color=FONT_C,xaxis_title="CPU %",margin=dict(l=10,r=40,t=20,b=20))
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# Collect live data
# ══════════════════════════════════════════════════════════════════════════════
try:
    snap = collect_snapshot()
except Exception as e:
    st.error(f"Collector error: {e}")
    snap = {"cpu":0,"memory":0,"disk":0,"net_sent":0,"net_recv":0,"top_processes":[]}

cpu_val  = snap["cpu"];  mem_val = snap["memory"]
disk_val = snap["disk"]; processes = snap.get("top_processes",[])

# alerts are checked after sidebar sliders set thresholds (see below)

try:
    core_vals  = get_per_core_cpu()
    disk_io    = get_disk_io_speed()
    net_speed  = get_network_speed()
    mem_detail = get_memory_detail()
except Exception:
    core_vals  = []
    disk_io    = {"read_mbps":0,"write_mbps":0,"read_count":0,"write_count":0}
    net_speed  = {"upload_mbps":0,"download_mbps":0,"packets_sent":0,"packets_recv":0}
    mem_detail = {}

if "sysinfo" not in st.session_state:
    try:    st.session_state.sysinfo = get_system_info()
    except: st.session_state.sysinfo = {}
sysinfo = st.session_state.sysinfo

total_records   = count_metrics()
total_alerts    = len(fetch_recent_alerts(9999))
total_anomalies = len(fetch_recent_anomalies(9999))

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://img.icons8.com/nolan/64/activity-monitor.png", width=64)
    st.title("⚙️ Control Panel")

    # Feature 4 — Theme toggle
    if st.button("☀️ Light Mode" if dark else "🌙 Dark Mode", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

    st.divider()
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = True
    st.session_state.auto_refresh = st.toggle(
        "🔄 Auto-Refresh (5s)",
        value=st.session_state.auto_refresh,
        key="auto_refresh_toggle"
    )
    auto_refresh = st.session_state.auto_refresh
    st.button("↻ Refresh Now", use_container_width=True)

    st.divider()
    st.subheader("🤖 AI Models")
    train_btn  = st.button("🏋️ Train / Retrain Models", use_container_width=True)
    pred_steps = st.slider("Forecast Steps", 5, 50, 20)

    st.divider()

    # Feature 15 — Time range filter
    st.subheader("📅 Time Range")
    time_range = st.selectbox("Show history:",
        ["Last 1 min","Last 5 min","Last 30 min","Last 1 hour","All time"], index=1)
    history_pts = {"Last 1 min":20,"Last 5 min":100,"Last 30 min":600,
                   "Last 1 hour":1200,"All time":9999}[time_range]

    st.divider()

    st.subheader("🚨 Alert Thresholds")
    st.caption("Drag to change when notifications fire:")

    # Use session_state defaults so slider values persist across reruns
    if "cpu_w"  not in st.session_state: st.session_state["cpu_w"]  = 70
    if "cpu_c"  not in st.session_state: st.session_state["cpu_c"]  = 85
    if "mem_w"  not in st.session_state: st.session_state["mem_w"]  = 75
    if "mem_c"  not in st.session_state: st.session_state["mem_c"]  = 90
    if "dsk_w"  not in st.session_state: st.session_state["dsk_w"]  = 80
    if "dsk_c"  not in st.session_state: st.session_state["dsk_c"]  = 95

    cpu_warn  = st.slider("CPU Warning %",    40, 90, st.session_state["cpu_w"], 5, key="cpu_w")
    cpu_crit  = st.slider("CPU Critical %",   50, 99, st.session_state["cpu_c"], 5, key="cpu_c")
    mem_warn  = st.slider("Memory Warning %", 40, 90, st.session_state["mem_w"], 5, key="mem_w")
    mem_crit  = st.slider("Memory Critical %",50, 99, st.session_state["mem_c"], 5, key="mem_c")
    disk_warn = st.slider("Disk Warning %",   40, 95, st.session_state["dsk_w"], 5, key="dsk_w")
    disk_crit = st.slider("Disk Critical %",  50, 99, st.session_state["dsk_c"], 5, key="dsk_c")

    # Apply slider values to threshold engine
    update_thresholds(cpu_warn, cpu_crit, mem_warn, mem_crit, disk_warn, disk_crit)

    st.caption(f"CPU: ⚠️{cpu_warn}%  🔴{cpu_crit}%")
    st.caption(f"MEM: ⚠️{mem_warn}%  🔴{mem_crit}%")
    st.caption(f"DSK: ⚠️{disk_warn}%  🔴{disk_crit}%")

    # Show current live values vs thresholds in sidebar
    st.divider()
    st.subheader("📊 Current vs Threshold")
    for label, val, warn, crit in [
        ("CPU",  "cpu_val_sb",  cpu_warn,  cpu_crit),
        ("MEM",  "mem_val_sb",  mem_warn,  mem_crit),
        ("DISK", "disk_val_sb", disk_warn, disk_crit),
    ]:
        pass  # values shown after collection below

    st.divider()

    # Feature 13 — Live sidebar stats
    st.subheader("📊 Live Stats")
    st.metric("Records",          total_records)
    st.metric("Alerts Fired",     total_alerts)
    st.metric("Anomalies Found",  total_anomalies)
    st.metric("System Uptime",    sysinfo.get("uptime","—"))
    st.caption("OS: CPU Scheduling · Memory Mgmt · Disk I/O · Process Table")

# ── Sidebar actions ───────────────────────────────────────────────────────────
if train_btn:
    with st.spinner("Training..."):
        retrain_all()
    st.sidebar.success("Models retrained!")

# ── Fire alerts AFTER thresholds set by sliders ──────────────────────────────
try:
    check_and_raise_alerts(cpu_val, mem_val, disk_val)
except Exception as _ae:
    print(f"[Alert check error] {_ae}")

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<h1 style='text-align:center;color:{ACCENT};font-size:32px;margin-bottom:4px;'>
    🖥️ AI-Driven System Health Dashboard
</h1>
<p style='text-align:center;color:#888;font-size:14px;margin-top:0;'>
    Real-Time Monitoring · Predictive Analytics · Anomaly Detection
</p>
""", unsafe_allow_html=True)
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 11 — System Info Panel
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("🖥️ System Identity Card", expanded=False):
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f"<div class='info-card'><b>🖥️ Host</b><br>{sysinfo.get('hostname','—')}<br>"
                f"<small>{sysinfo.get('os','—')}</small></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='info-card'><b>⚙️ CPU</b><br>{sysinfo.get('cpu_cores_logical','—')} Cores<br>"
                f"<small>{sysinfo.get('cpu_freq_mhz','—')} MHz</small></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='info-card'><b>🧠 RAM</b><br>{sysinfo.get('ram_total_gb','—')} GB Total<br>"
                f"<small>{sysinfo.get('ram_used_gb','—')} GB Used</small></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='info-card'><b>💾 Disk</b><br>{sysinfo.get('disk_total_gb','—')} GB Total<br>"
                f"<small>Boot: {sysinfo.get('boot_time','—')}</small></div>", unsafe_allow_html=True)
    c5,c6,c7,c8 = st.columns(4)
    c5.markdown(f"<div class='info-card'><b>🏗️ Arch</b><br>{sysinfo.get('architecture','—')}</div>", unsafe_allow_html=True)
    c6.markdown(f"<div class='info-card'><b>🐍 Python</b><br>{sysinfo.get('python_version','—')}</div>", unsafe_allow_html=True)
    c7.markdown(f"<div class='info-card'><b>⏱️ Uptime</b><br>{sysinfo.get('uptime','—')}</div>", unsafe_allow_html=True)
    c8.markdown(f"<div class='info-card'><b>🔲 Physical Cores</b><br>{sysinfo.get('cpu_cores_physical','—')}</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LIVE GAUGES
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">📡 Real-Time System Metrics</div>', unsafe_allow_html=True)
g1,g2,g3 = st.columns(3)
with g1: st.plotly_chart(gauge(cpu_val,  "CPU Usage",    COLORS["cpu"]),    width='stretch')
with g2: st.plotly_chart(gauge(mem_val,  "Memory Usage", COLORS["memory"]), width='stretch')
with g3: st.plotly_chart(gauge(disk_val, "Disk Usage",   COLORS["disk"]),   width='stretch')

m1,m2,m3,m4,m5,m6 = st.columns(6)
m1.metric("⬆️ Upload",    f"{net_speed['upload_mbps']:.3f} MB/s")
m2.metric("⬇️ Download",  f"{net_speed['download_mbps']:.3f} MB/s")
m3.metric("📖 Disk Read", f"{disk_io['read_mbps']:.3f} MB/s")
m4.metric("✏️ Disk Write",f"{disk_io['write_mbps']:.3f} MB/s")
m5.metric("🧠 RAM Used",  f"{mem_detail.get('used_gb',0):.1f} GB")
m6.metric("💾 Swap",      f"{mem_detail.get('swap_percent',0):.0f}%")

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 8 — Per-Core CPU Monitor
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🔬 Per-Core CPU Monitor</div>', unsafe_allow_html=True)
if core_vals:
    ci1,ci2,ci3 = st.columns(3)
    ci1.metric("Total Cores",   len(core_vals))
    ci2.metric("Average Load",  f"{sum(core_vals)/len(core_vals):.1f}%")
    ci3.metric("Hottest Core",  f"Core {core_vals.index(max(core_vals))} ({max(core_vals):.1f}%)")
    st.plotly_chart(per_core_chart(core_vals), width='stretch')
else:
    st.info("Collecting per-core data...")

# ══════════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION  (rule-based — always reliable)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🔍 Anomaly Detection</div>', unsafe_allow_html=True)

cfg = get_threshold_config()

def _rule_anomaly(cpu, mem, disk, cfg):
    """
    Detect anomaly by checking each metric against warning/critical thresholds.
    Returns (is_anomaly, severity, reasons[])
    """
    reasons  = []
    severity = None

    for metric, val in [("cpu", cpu), ("memory", mem), ("disk", disk)]:
        t = cfg.get(metric, {})
        crit = t.get("critical", 101)
        warn = t.get("warning",  101)
        if val >= crit:
            reasons.append(f"{metric.upper()} {val:.1f}% ≥ critical {crit}%")
            severity = "critical"
        elif val >= warn:
            reasons.append(f"{metric.upper()} {val:.1f}% ≥ warning {warn}%")
            if severity != "critical":
                severity = "warning"

    return bool(reasons), severity, reasons

is_anom, anom_sev, reasons = _rule_anomaly(cpu_val, mem_val, disk_val, cfg)

if is_anom:
    color_cls = "alert-critical" if anom_sev == "critical" else "alert-warning"
    icon      = "🔴 CRITICAL ANOMALY" if anom_sev == "critical" else "⚠️ WARNING ANOMALY"
    reason_str = "  |  ".join(reasons)
    st.markdown(
        f'<div class="{color_cls}"><b>{icon} DETECTED</b> — {reason_str}</div>',
        unsafe_allow_html=True,
    )
    # Only fire anomaly notification when the state *changes* — not on every rerun
    _anom_key = ("anomaly_fired", anom_sev)
    if st.session_state.get("_last_anomaly_key") != _anom_key:
        notify_anomaly(cpu_val, mem_val, disk_val, severity=anom_sev)
        st.session_state["_last_anomaly_key"] = _anom_key
else:
    # Reset so the next breach will fire again
    st.session_state["_last_anomaly_key"] = None
    st.markdown(
        f'<div class="alert-ok">✅ System Normal — '
        f'CPU:{cpu_val:.1f}%  MEM:{mem_val:.1f}%  DISK:{disk_val:.1f}%</div>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# HISTORICAL TRENDS + FEATURE 15 CSV EXPORT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">📊 Historical Trends</div>', unsafe_allow_html=True)
hist_rows = fetch_recent_metrics(history_pts)
if hist_rows:
    hist_df = pd.DataFrame(hist_rows)
    csv_buf = io.StringIO()
    hist_df.to_csv(csv_buf, index=False)
    st.download_button("⬇️ Export as CSV", data=csv_buf.getvalue(),
                       file_name=f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                       mime="text/csv")
    st.plotly_chart(line_chart(hist_df), width='stretch')
else:
    st.info("Collecting data… please wait.")

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 12 — CPU Heatmap
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🌡️ CPU Usage Heatmap</div>', unsafe_allow_html=True)
if hist_rows and len(hist_rows) >= 10:
    hm = cpu_heatmap(pd.DataFrame(hist_rows))
    if hm:
        st.plotly_chart(hm, width='stretch')
        st.caption("🟢 Low  🟡 Moderate  🔴 High — each cell = one reading")
else:
    st.info("Need at least 10 readings for heatmap...")

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 9 — Disk I/O  +  FEATURE 10 — Network Monitor
# ══════════════════════════════════════════════════════════════════════════════
io_col, net_col = st.columns(2)
with io_col:
    st.markdown('<div class="section-title">💾 Disk I/O Monitor</div>', unsafe_allow_html=True)
    d1,d2 = st.columns(2)
    d1.metric("Read Speed",   f"{disk_io['read_mbps']:.3f} MB/s")
    d2.metric("Write Speed",  f"{disk_io['write_mbps']:.3f} MB/s")
    d3,d4 = st.columns(2)
    d3.metric("Total Reads",  disk_io['read_count'])
    d4.metric("Total Writes", disk_io['write_count'])
    if hist_rows:
        st.plotly_chart(io_net_chart(hist_df,"net_sent","net_recv",
            "Read (MB/s)","Write (MB/s)",COLORS["net"],COLORS["write"]),
            width='stretch')

with net_col:
    st.markdown('<div class="section-title">🌐 Network Monitor</div>', unsafe_allow_html=True)
    n1,n2 = st.columns(2)
    n1.metric("⬆️ Upload",   f"{net_speed['upload_mbps']:.4f} MB/s")
    n2.metric("⬇️ Download", f"{net_speed['download_mbps']:.4f} MB/s")
    n3,n4 = st.columns(2)
    n3.metric("Pkts Sent", net_speed['packets_sent'])
    n4.metric("Pkts Recv", net_speed['packets_recv'])
    if hist_rows:
        st.plotly_chart(io_net_chart(hist_df,"net_sent","net_recv",
            "Upload (MB/s)","Download (MB/s)",COLORS["cpu"],COLORS["net"]),
            width='stretch')

# ══════════════════════════════════════════════════════════════════════════════
# AI PREDICTION PANEL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🤖 AI Prediction Panel</div>', unsafe_allow_html=True)
try:
    pred_result = predictor.predict_future(steps=pred_steps)
    if pred_result.get("status") == "ok" and hist_rows:
        pc,pi = st.columns([3,1])
        with pc:
            st.plotly_chart(prediction_chart(pred_result, pd.DataFrame(hist_rows)),
                            width='stretch')
        with pi:
            st.subheader("Model Accuracy")
            for metric,err in pred_result.get("model_errors",{}).items():
                st.markdown(f"**{metric.upper()}**")
                st.caption(f"LR MAE:  `{err.get('lr_mae','—')}`")
                st.caption(f"RF MAE:  `{err.get('rf_mae','—')}`")
                st.caption(f"RF RMSE: `{err.get('rf_rmse','—')}`")
                st.divider()
            for a in pred_result.get("prediction_alerts",[]):
                st.markdown(f'<div class="alert-warning">🔮 {a}</div>', unsafe_allow_html=True)
    else:
        st.info("Need more data for predictions. Keep the app running...")
except Exception as ex:
    st.warning(f"Prediction engine: {ex}")

# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 3 — Process Manager + Kill
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🏃 Process Manager</div>', unsafe_allow_html=True)
st.caption("⚠️ Only kill non-system processes. Killing system processes may crash your PC.")

pc1,pc2 = st.columns([2,1])
with pc1:
    if processes: st.plotly_chart(process_bar(processes), width='stretch')
with pc2:
    if processes:
        df_proc = pd.DataFrame(processes)[["pid","name","cpu_percent","mem_percent"]]
        df_proc.columns = ["PID","Name","CPU%","MEM%"]
        st.dataframe(df_proc, use_container_width=True, hide_index=True)

st.subheader("🔫 Kill a Process")
k1,k2 = st.columns([2,1])
with k1:
    kill_pid = st.number_input("Enter PID to terminate", min_value=1, step=1, value=1)
with k2:
    st.write(""); st.write("")
    if st.button("⚡ Kill Process", type="primary"):
        result = kill_process(int(kill_pid))
        if result["success"]: st.success(result["message"])
        else:                 st.error(result["message"])

# ══════════════════════════════════════════════════════════════════════════════
# ALERTS LOG
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🚨 System Alerts Log</div>', unsafe_allow_html=True)
alert_rows = fetch_recent_alerts(15)
if alert_rows:
    for row in alert_rows[:15]:
        cls = "alert-critical" if "critical" in row["alert_type"] else "alert-warning"
        st.markdown(f'<div class="{cls}"><b>[{row["timestamp"]}]</b> {row["message"]}</div>',
                    unsafe_allow_html=True)
else:
    st.markdown('<div class="alert-ok">✅ No alerts — system is healthy.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.markdown(f"""
<p style='text-align:center;color:#555;font-size:12px;'>
    OS Concepts: CPU Scheduling · Virtual Memory · Disk I/O · Process Table ·
    System Calls · Resource Allocation · Network Stack<br>
    AI Models: Linear Regression · Random Forest · Isolation Forest
</p>
""", unsafe_allow_html=True)

if st.session_state.get("auto_refresh", True):
    time.sleep(5)
    st.rerun()
