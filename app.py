"""Streamlit dashboard for the thermal-aware scheduler project.

Run with: streamlit run app.py
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scheduler import run_simulation


CORE_COUNT = 4
ALGORITHMS = ("FCFS", "Thermal-aware")


def _records(result: dict[str, Any]) -> pd.DataFrame:
    data = result.get("records", result.get("execution_records", []))
    return pd.DataFrame(data)


def _metric(result: dict[str, Any], key: str, alternatives: tuple[str, ...] = (), default: float = 0.0) -> float:
    for name in (key, *alternatives):
        if name in result:
            try:
                return float(result[name])
            except (TypeError, ValueError):
                break
    return default


def main() -> None:
    st.set_page_config(page_title="Thermal-aware CPU scheduler", page_icon="🌡️", layout="wide")
    st.title("🌡️ Thermal-aware CPU scheduler")
    st.caption("Compare a four-core FCFS baseline with thermal-aware process assignment.")

    with st.sidebar:
        st.header("Simulation setup")
        algorithm = st.selectbox("Algorithm", ALGORITHMS, index=1)
        compare = st.toggle("Compare both algorithms", value=True)
        st.caption("Enter one process per row. Arrival and burst times are measured in simulated time units.")

    seed = pd.DataFrame([
        {"Process ID": "P1", "Arrival time": 0, "Burst time": 8},
        {"Process ID": "P2", "Arrival time": 1, "Burst time": 5},
        {"Process ID": "P3", "Arrival time": 2, "Burst time": 7},
        {"Process ID": "P4", "Arrival time": 3, "Burst time": 4},
        {"Process ID": "P5", "Arrival time": 5, "Burst time": 6},
    ])
    st.subheader("Process workload")
    edited = st.data_editor(seed, num_rows="dynamic", use_container_width=True,
                            column_config={"Process ID": st.column_config.TextColumn(required=True),
                                           "Arrival time": st.column_config.NumberColumn(min_value=0, step=1, required=True),
                                           "Burst time": st.column_config.NumberColumn(min_value=0.1, step=1, required=True)})
    run = st.button("▶ Run simulation", type="primary", use_container_width=False)

    if run:
        frame = edited.rename(columns={"Process ID": "process_id", "Arrival time": "arrival_time", "Burst time": "burst_time"})
        frame = frame.dropna(subset=["process_id", "arrival_time", "burst_time"])
        if frame.empty:
            st.error("Add at least one process with an ID, arrival time, and burst time.")
            return
        if frame["process_id"].astype(str).str.strip().eq("").any() or frame["process_id"].astype(str).duplicated().any():
            st.error("Process IDs must be non-empty and unique.")
            return
        if (frame["arrival_time"] < 0).any() or (frame["burst_time"] <= 0).any():
            st.error("Arrival times must be zero or greater, and burst times must be greater than zero.")
            return
        processes = frame.to_dict("records")
        algorithms = list(ALGORITHMS) if compare else [algorithm]
        results = {name: run_simulation(processes, name) for name in algorithms}
        st.session_state["simulation_results"] = results

    results = st.session_state.get("simulation_results")
    if not results:
        st.info("Set the workload above and select **Run simulation** to see the schedule and metrics.")
        return

    if "Thermal-aware" in results and "FCFS" in results:
        display_name = "Thermal-aware"
    else:
        display_name = next(iter(results))
    result = results[display_name]
    records = _records(result)

    st.subheader(f"{display_name} results")
    cols = st.columns(CORE_COUNT)
    for core_index, col in enumerate(cols):
        core_name = f"Core {core_index + 1}"
        assigned = records[records.get("core", pd.Series(dtype=str)).astype(str).isin([core_name, str(core_index), str(core_index + 1)])] if not records.empty else pd.DataFrame()
        temperature = 35.0
        history = result.get("temperature_history", [])
        if isinstance(history, list):
            vals = [h.get("temperature") for h in history if isinstance(h, dict) and str(h.get("core", "")) in [core_name, str(core_index), str(core_index + 1)]]
            if vals:
                temperature = max(float(v) for v in vals)
        with col:
            st.markdown(f"#### {core_name}")
            st.metric("Peak temperature", f"{temperature:.1f} °C")
            ids = assigned["process_id"].astype(str).tolist() if "process_id" in assigned else []
            st.caption("Workload: " + (", ".join(ids) if ids else "Idle"))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Peak temperature", f"{_metric(result, 'peak_temperature', ('peak_temp',), 35):.1f} °C")
    m2.metric("Average waiting time", f"{_metric(result, 'average_waiting_time', ('avg_waiting_time',)):.2f}")
    m3.metric("Average turnaround time", f"{_metric(result, 'average_turnaround_time', ('avg_turnaround_time',)):.2f}")
    m4.metric("CPU utilization", f"{_metric(result, 'cpu_utilization', ('utilization',)):.1f}%")

    if not records.empty:
        st.subheader("Process assignments")
        st.dataframe(records, hide_index=True, use_container_width=True)
        if {"start_time", "finish_time", "core"}.issubset(records.columns):
            gantt = px.timeline(records, x_start="start_time", x_end="finish_time", y="core", color="process_id",
                                hover_data=[c for c in ["arrival_time", "burst_time", "waiting_time", "turnaround_time"] if c in records],
                                title="Execution timeline")
            gantt.update_yaxes(autorange="reversed", title="CPU core")
            gantt.update_xaxes(title="Simulated time")
            st.plotly_chart(gantt, use_container_width=True)

    history_frames = []
    for name, item in results.items():
        hist = item.get("temperature_history", [])
        if isinstance(hist, list) and hist:
            hist_frame = pd.DataFrame(hist)
            if "temperature" in hist_frame:
                hist_frame["algorithm"] = name
                history_frames.append(hist_frame)
    if history_frames:
        thermal = pd.concat(history_frames, ignore_index=True)
        if "time" in thermal:
            chart = px.line(thermal, x="time", y="temperature", color="core" if "core" in thermal else None,
                            line_dash="algorithm" if "algorithm" in thermal else None,
                            title="Core temperature over time", markers=True)
            chart.update_xaxes(title="Simulated time")
            chart.update_yaxes(title="Temperature (°C)")
            st.plotly_chart(chart, use_container_width=True)

    if len(results) > 1:
        st.subheader("Algorithm comparison")
        metrics = []
        for name, item in results.items():
            metrics.append({"Algorithm": name,
                            "Average waiting time": _metric(item, "average_waiting_time", ("avg_waiting_time",)),
                            "Average turnaround time": _metric(item, "average_turnaround_time", ("avg_turnaround_time",)),
                            "CPU utilization (%)": _metric(item, "cpu_utilization", ("utilization",)),
                            "Peak temperature (°C)": _metric(item, "peak_temperature", ("peak_temp",))})
        comparison = pd.DataFrame(metrics)
        st.dataframe(comparison, hide_index=True, use_container_width=True)
        chart = go.Figure()
        for column in comparison.columns[1:]:
            chart.add_trace(go.Bar(name=column, x=comparison["Algorithm"], y=comparison[column]))
        chart.update_layout(barmode="group", title="Performance metrics by algorithm", yaxis_title="Metric value")
        st.plotly_chart(chart, use_container_width=True)

    st.caption("Thermal-aware selection uses normalized core temperature and accumulated workload with weights 0.6 and 0.4.")


if __name__ == "__main__":
    main()
