"""FCFS and temperature-aware scheduling for a four-core CPU simulation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

from thermal_model import ThermalModel


CORE_COUNT = 4
THERMAL_WEIGHT = 0.6
WORKLOAD_WEIGHT = 0.4


@dataclass(frozen=True)
class Process:
    process_id: str
    arrival_time: float
    burst_time: float

    @classmethod
    def from_value(cls, value: Process | dict[str, Any]) -> Process:
        if isinstance(value, cls):
            process = value
        else:
            process = cls(
                process_id=str(value.get("process_id", value.get("pid", ""))).strip(),
                arrival_time=float(value["arrival_time"]),
                burst_time=float(value["burst_time"]),
            )
        if not process.process_id:
            raise ValueError("process_id must be non-empty")
        if process.arrival_time < 0:
            raise ValueError(f"arrival_time for {process.process_id} must be non-negative")
        if process.burst_time <= 0:
            raise ValueError(f"burst_time for {process.process_id} must be greater than zero")
        return process


def _normalize_processes(values: Iterable[Process | dict[str, Any]]) -> list[Process]:
    processes = [Process.from_value(value) for value in values]
    ids = [process.process_id for process in processes]
    if len(set(ids)) != len(ids):
        raise ValueError("process IDs must be unique")
    return sorted(processes, key=lambda process: (process.arrival_time, process.process_id))


def run_simulation(
    processes: Iterable[Process | dict[str, Any]],
    algorithm: str = "FCFS",
    *,
    core_count: int = CORE_COUNT,
    thermal_model: ThermalModel | None = None,
) -> dict[str, Any]:
    """Schedule a workload and return execution records, temperature samples,
    and aggregate metrics. ``algorithm`` accepts FCFS or Thermal-aware.

    FCFS dispatches each ready process to the lowest-numbered idle core.
    Thermal-aware dispatches to the idle core with the lowest weighted score.
    If every core is busy, ready processes stay in arrival-order FIFO until a
    core finishes.
    """
    if core_count <= 0:
        raise ValueError("core_count must be a positive integer")
    mode = algorithm.strip().lower().replace("_", "-")
    if mode not in {"fcfs", "thermal-aware", "thermal aware"}:
        raise ValueError("algorithm must be 'FCFS' or 'Thermal-aware'")
    thermal_aware = mode != "fcfs"
    workload = _normalize_processes(processes)
    if not workload:
        return _empty_result(core_count)

    model = thermal_model or ThermalModel()
    temperatures = [model.ambient_temperature] * core_count
    peak_by_core = temperatures.copy()
    cumulative_work = [0.0] * core_count
    busy_until: list[float | None] = [None] * core_count
    running: list[Process | None] = [None] * core_count
    last_update = 0.0
    now = 0.0
    next_process = 0
    ready: deque[Process] = deque()
    records: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []

    def sample(time: float, core: int, event: str) -> None:
        history.append({"time": time, "core": f"Core {core + 1}", "temperature": temperatures[core], "event": event})

    def advance_all(time: float) -> None:
        nonlocal last_update
        elapsed = time - last_update
        if elapsed < -1e-9:
            raise RuntimeError("simulation clock moved backwards")
        if elapsed <= 0:
            return
        for core in range(core_count):
            temperatures[core] = model.advance(temperatures[core], elapsed, running[core] is not None)
            peak_by_core[core] = max(peak_by_core[core], temperatures[core])
        last_update = time

    while next_process < len(workload) or ready or any(process is not None for process in running):
        # Advance whenever no process can be dispatched immediately. This is
        # either an empty ready queue or a full set of busy cores.
        if not ready or not any(process is None for process in running):
            finishes = [value for value in busy_until if value is not None]
            next_finish = min(finishes) if finishes else float("inf")
            next_arrival = (
                workload[next_process].arrival_time
                if not ready and next_process < len(workload)
                else float("inf")
            )
            next_event = min(next_finish, next_arrival)
            if next_event == float("inf"):
                break
            now = max(now, next_event)

        advance_all(now)

        # Finish work at this instant before dispatching newly ready work.
        for core in range(core_count):
            process = running[core]
            if process is not None and busy_until[core] is not None and busy_until[core] <= now + 1e-9:
                temperatures[core] = model.advance(temperatures[core], 0.0, False)
                running[core] = None
                busy_until[core] = None
                sample(now, core, "finish")

        while next_process < len(workload) and workload[next_process].arrival_time <= now + 1e-9:
            ready.append(workload[next_process])
            next_process += 1

        # Dispatch FIFO-ready processes into idle cores. The thermal score is
        # normalized against the hottest temperature and highest assigned work.
        while ready and any(process is None for process in running):
            idle_cores = [core for core, process in enumerate(running) if process is None]
            if thermal_aware:
                temp_scale = max(max(temperatures), model.ambient_temperature, 1.0)
                work_scale = max(max(cumulative_work), 1.0)
                core = min(
                    idle_cores,
                    key=lambda index: (
                        THERMAL_WEIGHT * temperatures[index] / temp_scale
                        + WORKLOAD_WEIGHT * cumulative_work[index] / work_scale,
                        index,
                    ),
                )
            else:
                core = idle_cores[0]
            process = ready.popleft()
            start = now
            finish = start + process.burst_time
            waiting = start - process.arrival_time
            record = {
                "process_id": process.process_id,
                "arrival_time": process.arrival_time,
                "burst_time": process.burst_time,
                "core": f"Core {core + 1}",
                "start_time": start,
                "finish_time": finish,
                "waiting_time": waiting,
                "turnaround_time": finish - process.arrival_time,
            }
            records.append(record)
            running[core] = process
            busy_until[core] = finish
            cumulative_work[core] += process.burst_time
            sample(now, core, f"start:{process.process_id}")

    records.sort(key=lambda record: (record["start_time"], record["core"], record["process_id"]))
    makespan = max((record["finish_time"] for record in records), default=0.0)
    count = len(records)
    total_burst = sum(record["burst_time"] for record in records)
    utilization = total_burst / (core_count * makespan) * 100 if makespan > 0 else 0.0
    return {
        "algorithm": "Thermal-aware" if thermal_aware else "FCFS",
        "records": records,
        "execution_records": records,
        "temperature_history": history,
        "core_temperatures": [
            {"core": f"Core {index + 1}", "temperature": temperatures[index],
             "peak_temperature": peak_by_core[index], "workload": cumulative_work[index]}
            for index in range(core_count)
        ],
        "peak_temperature": max(peak_by_core, default=model.ambient_temperature),
        "average_waiting_time": sum(record["waiting_time"] for record in records) / count if count else 0.0,
        "average_turnaround_time": sum(record["turnaround_time"] for record in records) / count if count else 0.0,
        "cpu_utilization": utilization,
        "makespan": makespan,
        "per_core_utilization": {
            f"Core {index + 1}": cumulative_work[index] / makespan * 100 if makespan else 0.0
            for index in range(core_count)
        },
    }


def fcfs_schedule(processes: Iterable[Process | dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper for the FCFS baseline."""
    return run_simulation(processes, "FCFS", **kwargs)


def thermal_aware_schedule(processes: Iterable[Process | dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Convenience wrapper for weighted thermal-aware scheduling."""
    return run_simulation(processes, "Thermal-aware", **kwargs)


def _empty_result(core_count: int) -> dict[str, Any]:
    return {
        "records": [], "execution_records": [], "temperature_history": [],
        "core_temperatures": [
            {"core": f"Core {i + 1}", "temperature": 35.0, "peak_temperature": 35.0, "workload": 0.0}
            for i in range(core_count)
        ],
        "peak_temperature": 35.0, "average_waiting_time": 0.0,
        "average_turnaround_time": 0.0, "cpu_utilization": 0.0,
        "makespan": 0.0,
        "per_core_utilization": {f"Core {i + 1}": 0.0 for i in range(core_count)},
    }
