"""
Calendar-aware CPM (Critical Path Method) engine.

Implements forward/backward pass on a NetworkX DAG with calendar-aware
date calculations. Runs on most-likely durations; three-point values
support PERT β-distribution for P50/P80 estimates (§8, §17).
"""

from __future__ import annotations

import datetime
import math
from typing import Optional

import networkx as nx

from .calendar_engine import WorkingCalendar, load_calendar_from_library
from .models import Activity, Project


def build_network(activities: list[Activity]) -> nx.DiGraph:
    """Build a directed acyclic graph from activities and their predecessors."""
    G = nx.DiGraph()

    # Add all activities as nodes
    for act in activities:
        G.add_node(act.activity_id, activity=act)

    # Add edges from predecessors
    for act in activities:
        for pred in act.predecessors:
            if G.has_node(pred.activity_id):
                G.add_edge(
                    pred.activity_id,
                    act.activity_id,
                    relationship_type=pred.relationship_type,
                    lag_days=pred.lag_days,
                    lag_reason=pred.lag_reason,
                )

    return G


def detect_circular_dependencies(G: nx.DiGraph) -> list[list[str]]:
    """Detect circular dependencies in the network."""
    try:
        cycles = list(nx.simple_cycles(G))
        return cycles
    except Exception:
        return []


def _get_calendar(calendar_id: str, calendars: dict[str, WorkingCalendar]) -> WorkingCalendar:
    """Get or create a calendar by ID."""
    if calendar_id in calendars:
        return calendars[calendar_id]
    cal = load_calendar_from_library(calendar_id)
    calendars[calendar_id] = cal
    return cal


def _relationship_value(value) -> str:
    """Return a normalized CPM relationship code."""
    if hasattr(value, "value"):
        value = value.value
    return str(value or "FS").upper()


def _effective_duration(act: Activity, cal: WorkingCalendar) -> int:
    """Return the duration that CPM should use after calendar modifiers."""
    duration = act.duration_most_likely_days
    if act.calendar_efficiency_factor and act.calendar_efficiency_factor < 1.0:
        duration = math.ceil(duration / act.calendar_efficiency_factor)
    if act.weather_sensitive:
        duration = cal.apply_weather_buffer(duration)
    return max(0, duration)


def _finish_from_start(
    cal: WorkingCalendar,
    start: datetime.date,
    duration: int,
) -> datetime.date:
    """Calculate inclusive finish from a working start date and duration."""
    start = cal.next_working_day(start)
    if duration <= 0:
        return start
    return cal.add_working_days(start, duration)


def _start_from_finish(
    cal: WorkingCalendar,
    finish: datetime.date,
    duration: int,
) -> datetime.date:
    """Calculate inclusive start from a working finish date and duration."""
    finish = cal.previous_working_day(finish)
    if duration <= 0:
        return finish
    return cal.subtract_working_days_inclusive(finish, duration)


def _successor_start_candidate(
    rel_type: str,
    lag: int,
    pred_es: datetime.date,
    pred_ef: datetime.date,
    succ_duration: int,
    succ_cal: WorkingCalendar,
) -> datetime.date:
    """Earliest successor start allowed by one predecessor relationship."""
    if rel_type == "SS":
        candidate = pred_es if lag <= 0 else succ_cal.add_working_days_exclusive(pred_es, lag)
        return succ_cal.next_working_day(candidate)

    if rel_type == "FF":
        target_finish = pred_ef if lag <= 0 else succ_cal.add_working_days_exclusive(pred_ef, lag)
        return _start_from_finish(succ_cal, target_finish, succ_duration)

    if rel_type == "SF":
        target_finish = pred_es if lag <= 0 else succ_cal.add_working_days_exclusive(pred_es, lag)
        return _start_from_finish(succ_cal, target_finish, succ_duration)

    # FS+0 means the successor starts on the next working day after predecessor
    # finish, because activity finish dates are inclusive.
    return succ_cal.add_working_days_exclusive(pred_ef, lag + 1)


def _predecessor_late_finish_candidate(
    rel_type: str,
    lag: int,
    succ_ls: datetime.date,
    succ_lf: datetime.date,
    pred_duration: int,
    pred_cal: WorkingCalendar,
) -> datetime.date:
    """Latest predecessor finish allowed by one successor relationship."""
    if rel_type == "SS":
        latest_start = (
            pred_cal.previous_working_day(succ_ls)
            if lag <= 0
            else pred_cal.add_working_days_exclusive(succ_ls, -lag)
        )
        return _finish_from_start(pred_cal, latest_start, pred_duration)

    if rel_type == "FF":
        return (
            pred_cal.previous_working_day(succ_lf)
            if lag <= 0
            else pred_cal.add_working_days_exclusive(succ_lf, -lag)
        )

    if rel_type == "SF":
        latest_start = (
            pred_cal.previous_working_day(succ_lf)
            if lag <= 0
            else pred_cal.add_working_days_exclusive(succ_lf, -lag)
        )
        return _finish_from_start(pred_cal, latest_start, pred_duration)

    return pred_cal.add_working_days_exclusive(succ_ls, -(lag + 1))


def _free_float_finish_limit(
    rel_type: str,
    lag: int,
    succ_es: datetime.date,
    succ_ef: datetime.date,
    act_duration: int,
    act_cal: WorkingCalendar,
) -> datetime.date:
    """Latest activity finish before the successor's early dates move."""
    if rel_type == "SS":
        latest_start = (
            act_cal.previous_working_day(succ_es)
            if lag <= 0
            else act_cal.add_working_days_exclusive(succ_es, -lag)
        )
        return _finish_from_start(act_cal, latest_start, act_duration)

    if rel_type == "FF":
        return (
            act_cal.previous_working_day(succ_ef)
            if lag <= 0
            else act_cal.add_working_days_exclusive(succ_ef, -lag)
        )

    if rel_type == "SF":
        latest_start = (
            act_cal.previous_working_day(succ_ef)
            if lag <= 0
            else act_cal.add_working_days_exclusive(succ_ef, -lag)
        )
        return _finish_from_start(act_cal, latest_start, act_duration)

    return act_cal.add_working_days_exclusive(succ_es, -(lag + 1))


def forward_pass(
    G: nx.DiGraph,
    project_start: datetime.date,
    calendars: Optional[dict[str, WorkingCalendar]] = None,
) -> dict[str, tuple[datetime.date, datetime.date]]:
    """
    Forward pass: calculate Early Start (ES) and Early Finish (EF) for each activity.
    
    Returns dict of activity_id -> (ES, EF).
    """
    if calendars is None:
        calendars = {}

    es_ef: dict[str, tuple[datetime.date, datetime.date]] = {}

    # Topological sort ensures we process predecessors before successors
    try:
        topo_order = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        raise ValueError("Circular dependency detected — cannot compute CPM")

    for act_id in topo_order:
        act: Activity = G.nodes[act_id]["activity"]
        cal = _get_calendar(act.calendar_id, calendars)
        duration = _effective_duration(act, cal)

        # Determine ES from predecessors
        predecessors = list(G.predecessors(act_id))
        if not predecessors:
            # No predecessors — start at project start
            es = cal.next_working_day(project_start)
        else:
            # ES = latest relationship-driven start allowed by predecessors.
            latest = project_start
            for pred_id in predecessors:
                edge_data = G.edges[pred_id, act_id]
                rel_type = _relationship_value(edge_data.get("relationship_type", "FS"))
                lag = edge_data.get("lag_days", 0)

                pred_es, pred_ef = es_ef[pred_id]
                candidate = _successor_start_candidate(
                    rel_type,
                    lag,
                    pred_es,
                    pred_ef,
                    duration,
                    cal,
                )

                if candidate > latest:
                    latest = candidate

            es = cal.next_working_day(latest)

        # Calculate EF
        ef = _finish_from_start(cal, es, duration)

        es_ef[act_id] = (es, ef)

    return es_ef


def backward_pass(
    G: nx.DiGraph,
    es_ef: dict[str, tuple[datetime.date, datetime.date]],
    calendars: Optional[dict[str, WorkingCalendar]] = None,
) -> dict[str, tuple[datetime.date, datetime.date, int, int]]:
    """
    Backward pass: calculate Late Start (LS), Late Finish (LF), Total Float, Free Float.
    
    Returns dict of activity_id -> (LS, LF, total_float, free_float).
    """
    if calendars is None:
        calendars = {}

    ls_lf: dict[str, tuple[datetime.date, datetime.date]] = {}

    # Find the project end date (latest EF)
    project_end = max(ef for _, ef in es_ef.values())

    # Reverse topological order
    try:
        reverse_topo = list(reversed(list(nx.topological_sort(G))))
    except nx.NetworkXUnfeasible:
        raise ValueError("Circular dependency detected")

    for act_id in reverse_topo:
        act: Activity = G.nodes[act_id]["activity"]
        cal = _get_calendar(act.calendar_id, calendars)
        duration = _effective_duration(act, cal)

        # Determine LF from successors
        successors = list(G.successors(act_id))
        if not successors:
            lf = cal.previous_working_day(project_end)
        else:
            earliest_lf = project_end
            for succ_id in successors:
                succ_ls, succ_lf = ls_lf.get(succ_id, (project_end, project_end))
                edge_data = G.edges[act_id, succ_id]
                rel_type = _relationship_value(edge_data.get("relationship_type", "FS"))
                lag = edge_data.get("lag_days", 0)

                candidate_lf = _predecessor_late_finish_candidate(
                    rel_type,
                    lag,
                    succ_ls,
                    succ_lf,
                    duration,
                    cal,
                )
                if candidate_lf < earliest_lf:
                    earliest_lf = candidate_lf

            lf = earliest_lf

        # Calculate LS
        ls = _start_from_finish(cal, lf, duration)

        ls_lf[act_id] = (ls, lf)

    # Calculate float
    results: dict[str, tuple[datetime.date, datetime.date, int, int]] = {}
    for act_id in es_ef:
        es, ef = es_ef[act_id]
        ls, lf = ls_lf[act_id]
        act: Activity = G.nodes[act_id]["activity"]
        cal = _get_calendar(act.calendar_id, calendars)
        duration = _effective_duration(act, cal)
        start_float = cal.working_days_between_exclusive(es, ls)
        finish_float = cal.working_days_between_exclusive(ef, lf)
        total_float = min(start_float, finish_float)

        # Free float: how long this activity can move before any successor's
        # early dates move, evaluated against the actual relationship type.
        successors = list(G.successors(act_id))
        if successors:
            finish_limits = []
            for succ_id in successors:
                succ_es, succ_ef = es_ef[succ_id]
                edge_data = G.edges[act_id, succ_id]
                finish_limits.append(_free_float_finish_limit(
                    _relationship_value(edge_data.get("relationship_type", "FS")),
                    edge_data.get("lag_days", 0),
                    succ_es,
                    succ_ef,
                    duration,
                    cal,
                ))
            free_float = min(
                cal.working_days_between_exclusive(ef, finish_limit)
                for finish_limit in finish_limits
            )
        else:
            free_float = total_float

        results[act_id] = (ls, lf, max(0, total_float), max(0, free_float))

    return results


def pert_duration(optimistic: int, most_likely: int, pessimistic: int) -> tuple[float, float]:
    """
    PERT β-distribution estimate.
    Returns (mean, std_deviation).
    """
    mean = (optimistic + 4 * most_likely + pessimistic) / 6.0
    std = (pessimistic - optimistic) / 6.0
    return mean, std


def calculate_p50_p80(activities: list[Activity]) -> tuple[float, float]:
    """
    Calculate P50 and P80 total project duration using PERT estimates.
    Assumes activities on critical path are independent.
    
    Returns (p50_days, p80_days).
    """
    total_mean = 0.0
    total_variance = 0.0

    critical = [a for a in activities if a.is_critical]
    if not critical:
        critical = activities

    for act in critical:
        opt = act.duration_optimistic_days or act.duration_most_likely_days
        ml = act.duration_most_likely_days
        pess = act.duration_pessimistic_days or act.duration_most_likely_days
        mean, std = pert_duration(opt, ml, pess)
        total_mean += mean
        total_variance += std ** 2

    total_std = math.sqrt(total_variance) if total_variance > 0 else 0

    # P50 ≈ mean (z=0), P80 ≈ mean + 0.84*std
    p50 = total_mean
    p80 = total_mean + 0.84 * total_std

    return p50, p80


def run_cpm(project: Project) -> Project:
    """
    Run full CPM analysis on a project.
    Updates activities in-place with ES, EF, LS, LF, float, and criticality.
    Updates project with P50/P80 completion dates.
    """
    if not project.activities:
        return project

    # Build network
    G = build_network(project.activities)

    # Check for cycles
    cycles = detect_circular_dependencies(G)
    if cycles:
        from .models import ValidationResult, Severity
        project.validation_results.append(
            ValidationResult(
                rule_id="CPM-CYCLE",
                description=f"Circular dependency detected: {cycles[0]}",
                severity=Severity.ERROR,
                affected_activities=[a for cycle in cycles for a in cycle],
                suggested_fix="Remove or re-sequence the circular dependency.",
            )
        )
        return project

    # Initialize calendars
    calendars: dict[str, WorkingCalendar] = {}

    # Forward pass
    es_ef = forward_pass(G, project.project_start_date, calendars)

    # Backward pass
    ls_lf_float = backward_pass(G, es_ef, calendars)

    # Update activities
    act_map = {a.activity_id: a for a in project.activities}
    for act_id, (es, ef) in es_ef.items():
        act = act_map[act_id]
        act.early_start = es
        act.early_finish = ef

        ls, lf, tf, ff = ls_lf_float[act_id]
        act.late_start = ls
        act.late_finish = lf
        act.total_float = tf
        act.free_float = ff
        act.is_critical = (tf == 0)

    cal = _get_calendar(
        project.planning_basis.calendar_id if project.planning_basis else "VIC_5DAY_STANDARD_2026",
        calendars,
    )

    # P50 should be anchored to the CPM network finish, not to the sum of any
    # single activity subset. P80 then adds a PERT-style uncertainty allowance.
    project.p50_completion = max(ef for _, ef in es_ef.values())
    _, p80_days = calculate_p50_p80(project.activities)
    critical_days = sum(
        act.duration_most_likely_days
        for act in project.activities
        if act.is_critical
    )
    network_calendar_days = max(0, (project.p50_completion - project.project_start_date).days)
    class_5_4_uncertainty_days = math.ceil(network_calendar_days * 0.12 * 5 / 7)
    p80_buffer = max(
        5,
        int(math.ceil(p80_days - critical_days)),
        class_5_4_uncertainty_days,
    )
    project.p80_completion = cal.add_working_days(project.p50_completion, p80_buffer)

    return project
