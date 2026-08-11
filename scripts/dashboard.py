"""
Dashboard OBS-30: 6 panels từ data/logs.jsonl
Chạy: streamlit run scripts/dashboard.py
"""
import json
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

REPO_ROOT = Path(__file__).resolve().parents[1]
LOGS_PATH = REPO_ROOT / "data" / "logs.jsonl"

st.set_page_config(
    page_title="Day 13 Observability Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stMetric {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    .panel-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 0.5rem;
        padding-left: 0.5rem;
        border-left: 4px solid #667eea;
    }
    .contract-box {
        background: #f8f9fa;
        padding: 0.75rem;
        border-radius: 8px;
        font-size: 0.85rem;
    }
    .contract-box h4 {
        margin: 0 0 0.5rem 0;
        color: #495057;
        font-size: 0.9rem;
    }
    .threshold-ok {
        color: #28a745;
        font-weight: 600;
    }
    .threshold-warn {
        color: #dc3545;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">📊 Day 13 AI Observability Dashboard</p>', unsafe_allow_html=True)
st.markdown(f"""
<p class="sub-header">
    <span style="background:#e9ecef; padding:4px 12px; border-radius:20px; margin-right:10px;">⏱️ 60 min</span>
    <span style="background:#e9ecef; padding:4px 12px; border-radius:20px; margin-right:10px;">🔄 30s</span>
    <span style="background:#667eea; color:white; padding:4px 12px; border-radius:20px;">📁 logs.jsonl</span>
</p>
""", unsafe_allow_html=True)

# Load data
@st.cache_data
def load_logs():
    records = []
    with open(LOGS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return pd.DataFrame(records)

df = load_logs()
df["ts"] = pd.to_datetime(df["ts"])

# Sidebar
with st.sidebar:
    st.header("🔍 Filters")
    events = st.multiselect(
        "Events",
        options=df["event"].unique().tolist(),
        default=df["event"].unique().tolist()
    )
    st.divider()
    st.caption("**Contract Source**")
    st.caption("config/dashboard.yaml")

df_filtered = df[df["event"].isin(events)] if events else df

# Threshold values from contract
THRESHOLDS = {
    "latency_p95": 3000,
    "traffic_rate": 1,
    "error_rate": 2,
    "cost_total": 2.5,
    "tokens_total": 50000,
    "quality_mean": 0.75
}

# ============ ROW 1: Latency & Traffic ============
st.markdown("---")

col_lat, col_tra = st.columns(2)

with col_lat:
    st.markdown('<p class="panel-title">1️⃣ Latency Percentiles</p>', unsafe_allow_html=True)
    response_df = df_filtered[df_filtered["event"] == "response_sent"].copy()

    if not response_df.empty and "latency_ms" in response_df.columns:
        p50 = response_df["latency_ms"].quantile(0.5)
        p95 = response_df["latency_ms"].quantile(0.95)
        p99 = response_df["latency_ms"].quantile(0.99)

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("P50", f"{p50:.0f} ms")
        with m2:
            delta = "⚠️" if p95 > THRESHOLDS["latency_p95"] else "✅"
            st.metric("P95", f"{p95:.0f} ms", delta=delta)
        with m3:
            st.metric("P99", f"{p99:.0f} ms")

        # Chart with threshold line
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=response_df["ts"],
            y=response_df["latency_ms"],
            mode="lines+markers",
            name="Latency (ms)",
            line=dict(color="#667eea", width=2),
            marker=dict(size=6)
        ))
        fig.add_hline(
            y=THRESHOLDS["latency_p95"],
            line_dash="dash",
            line_color="red",
            annotation_text=f"Threshold: {THRESHOLDS['latency_p95']}ms",
            annotation_position="top right"
        )
        fig.update_layout(
            height=250,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Time",
            yaxis_title="ms",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No latency data")

with col_tra:
    st.markdown('<p class="panel-title">2️⃣ Request Traffic</p>', unsafe_allow_html=True)
    traffic_df = df_filtered[df_filtered["event"] == "request_received"].copy()

    if not traffic_df.empty:
        total = len(traffic_df)
        traffic_df["minute"] = traffic_df["ts"].dt.floor("min")
        rate = traffic_df.groupby("minute").size().mean()

        m1, m2 = st.columns(2)
        with m1:
            st.metric("Total Requests", f"{total}")
        with m2:
            st.metric("Avg Rate", f"{rate:.1f} req/min")

        # Chart
        req_per_min = traffic_df.groupby("minute").size().reset_index(name="requests")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=req_per_min["minute"],
            y=req_per_min["requests"],
            name="Requests",
            marker_color="#48bb78"
        ))
        fig.update_layout(
            height=250,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Time",
            yaxis_title="requests",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No traffic data")

# ============ ROW 2: Errors & Cost ============
st.markdown("---")

col_err, col_cst = st.columns(2)

with col_err:
    st.markdown('<p class="panel-title">3️⃣ Error Rate</p>', unsafe_allow_html=True)
    total_req = len(df_filtered[df_filtered["event"] == "request_received"])
    total_err = len(df_filtered[df_filtered["event"] == "request_failed"])
    error_rate = (total_err / total_req * 100) if total_req > 0 else 0

    delta = "⚠️" if error_rate > THRESHOLDS["error_rate"] else "✅"
    st.metric("Error Rate", f"{error_rate:.2f}%", delta=delta)

    if total_err > 0 and "error_type" in df_filtered.columns:
        err_df = df_filtered[df_filtered["event"] == "request_failed"]["error_type"].value_counts().reset_index()
        err_df.columns = ["Error Type", "Count"]
        fig = px.pie(err_df, values="Count", names="Error Type", hole=0.4)
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No errors in current range")

with col_cst:
    st.markdown('<p class="panel-title">4️⃣ Cost Over Time</p>', unsafe_allow_html=True)
    cost_df = df_filtered[df_filtered["event"] == "response_sent"].copy()

    if not cost_df.empty and "cost_usd" in cost_df.columns:
        total_cost = cost_df["cost_usd"].sum()
        cost_df["minute"] = cost_df["ts"].dt.floor("min")
        cost_per_min = cost_df.groupby("minute")["cost_usd"].sum().reset_index()
        cost_per_min.columns = ["Time", "Cost (USD)"]

        st.metric("Total Cost", f"${total_cost:.4f}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=cost_per_min["Time"],
            y=cost_per_min["Cost (USD)"],
            mode="lines",
            name="Cost",
            fill="tozeroy",
            line=dict(color="#f6ad55")
        ))
        fig.add_hline(
            y=THRESHOLDS["cost_total"],
            line_dash="dash",
            line_color="red",
            annotation_text=f"${THRESHOLDS['cost_total']}"
        )
        fig.update_layout(
            height=200,
            margin=dict(l=20, r=20, t=30, b=20),
            xaxis_title="Time",
            yaxis_title="USD",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No cost data")

# ============ ROW 3: Tokens & Quality ============
st.markdown("---")

col_tok, col_qlty = st.columns(2)

with col_tok:
    st.markdown('<p class="panel-title">5️⃣ Token Usage</p>', unsafe_allow_html=True)
    token_df = df_filtered[df_filtered["event"] == "response_sent"].copy()

    if not token_df.empty:
        tokens_in = int(token_df["tokens_in"].sum()) if "tokens_in" in token_df.columns else 0
        tokens_out = int(token_df["tokens_out"].sum()) if "tokens_out" in token_df.columns else 0
        total_tokens = tokens_in + tokens_out

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total", f"{total_tokens:,}")
        with m2:
            st.metric("In", f"{tokens_in:,}")
        with m3:
            st.metric("Out", f"{tokens_out:,}")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Tokens In", "Tokens Out"],
            y=[tokens_in, tokens_out],
            marker_color=["#667eea", "#764ba2"]
        ))
        fig.add_hline(
            y=THRESHOLDS["tokens_total"],
            line_dash="dash",
            line_color="red",
            annotation_text=f"Limit: {THRESHOLDS['tokens_total']:,}"
        )
        fig.update_layout(
            height=180,
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis_title="tokens",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No token data")

with col_qlty:
    st.markdown('<p class="panel-title">6️⃣ Quality Proxy</p>', unsafe_allow_html=True)
    quality_df = df_filtered[df_filtered["event"] == "response_sent"].copy()

    if not quality_df.empty and "quality_score" in quality_df.columns:
        mean_q = quality_df["quality_score"].mean()

        delta = "✅" if mean_q >= THRESHOLDS["quality_mean"] else "⚠️"
        st.metric("Quality Score", f"{mean_q:.3f}", delta=delta)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=quality_df["ts"],
            y=quality_df["quality_score"],
            mode="lines+markers",
            name="Quality",
            line=dict(color="#48bb78", width=2)
        ))
        fig.add_hline(
            y=THRESHOLDS["quality_mean"],
            line_dash="dash",
            line_color="red",
            annotation_text=f"Min: {THRESHOLDS['quality_mean']}"
        )
        fig.update_layout(
            height=180,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="Time",
            yaxis_title="score",
            yaxis_range=[0, 1],
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No quality data")

# Footer
st.markdown("---")
st.caption(f"🕐 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Source: {LOGS_PATH}")
