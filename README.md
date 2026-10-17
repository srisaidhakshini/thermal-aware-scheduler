# Thermal-aware CPU Scheduler

A Streamlit dashboard for simulating process scheduling across a four-core CPU. Compare a first-come, first-served (FCFS) baseline with a thermal-aware scheduler, and inspect process assignments, timing metrics, and simulated core temperatures.

## Features

- Edit a workload in the dashboard: process ID, arrival time, and burst time.
- Run FCFS, thermal-aware scheduling, or compare both algorithms.
- View per-core workload and peak temperature, process assignment tables, and execution timelines.
- Track temperature over simulated time and compare aggregate metrics.
- Use the scheduling functions directly from Python for custom workloads or core counts.

## Requirements

- Python 3.10 or newer
- Dependencies listed in `requirements.txt`

## Run the dashboard

From the project directory, create and activate a virtual environment, then install dependencies and launch Streamlit:

```bash
python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Then install and run:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. The dashboard starts with a sample workload. Edit or add rows, choose an algorithm or leave **Compare both algorithms** enabled, and select **Run simulation**. Process IDs must be unique and non-empty; arrival times must be zero or greater, and burst times must be greater than zero.

## Scheduling behavior

Both schedulers use non-preemptive execution. Processes enter a FIFO ready queue in arrival order (ties are ordered by process ID), and wait there until a core becomes idle.

- **FCFS** dispatches each ready process to the lowest-numbered idle core.
- **Thermal-aware** dispatches to the idle core with the lowest score, combining normalized current temperature (weight `0.6`) and accumulated assigned burst time (weight `0.4`). Ties go to the lowest-numbered core.

The thermal model starts each core at ambient temperature, heats it linearly while busy, and cools it linearly while idle. Defaults are 35 °C ambient, 100 °C maximum, 1.8 °C per busy time unit heating, and 0.7 °C per idle time unit cooling. These are simulation parameters, not measurements of physical hardware.

## Metrics

- **Waiting time:** process start time minus arrival time.
- **Turnaround time:** process finish time minus arrival time.
- **CPU utilization:** total process burst time divided by core count and simulation makespan, as a percentage.
- **Peak temperature:** highest simulated temperature reached by any core.
- **Makespan:** time from simulation start (time zero) until the final process finishes.

## Python API

The scheduler can be used without the dashboard:

```python
from scheduler import run_simulation

processes = [
    {"process_id": "P1", "arrival_time": 0, "burst_time": 8},
    {"process_id": "P2", "arrival_time": 1, "burst_time": 5},
]

result = run_simulation(processes, "Thermal-aware")
print(result["records"])
print(result["peak_temperature"])
```

`run_simulation(processes, algorithm="FCFS", *, core_count=4, thermal_model=None)` accepts `FCFS` or `Thermal-aware` (also `thermal-aware`/`thermal aware`). It returns execution records, temperature samples, per-core information, and aggregate metrics. Convenience wrappers `fcfs_schedule(...)` and `thermal_aware_schedule(...)` are also available from `scheduler.py`. A custom `ThermalModel` can be passed; its parameters are defined in `thermal_model.py`.

## Project files

- `app.py` — Streamlit dashboard and visualizations.
- `scheduler.py` — process validation, scheduling algorithms, and metrics.
- `thermal_model.py` — configurable core heating and cooling model.
- `requirements.txt` — Python package dependencies.
