"""Hiring analytics calculations."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from ..config import settings
from ..models import Candidate, CandidateActivity, InterviewFeedback, Position


def compute_analytics(db: Session) -> dict:
    """Compute all hiring metrics."""
    candidates = db.exec(select(Candidate)).all()
    positions = db.exec(select(Position)).all()
    activities = db.exec(select(CandidateActivity)).all()

    active = [c for c in candidates if c.status == "active"]
    hired = [c for c in candidates if c.status == "hired"]
    rejected = [c for c in candidates if c.status == "rejected"]

    # Time-to-hire for hired candidates
    hire_times = []
    for c in hired:
        hire_activities = [
            a for a in activities
            if a.candidate_id == c.id
            and a.activity_type == "stage_change"
            and "Hired" in a.description
        ]
        if hire_activities:
            delta = (hire_activities[0].created_at - c.applied_at).days
            hire_times.append(delta)

    avg_time_to_hire = round(sum(hire_times) / len(hire_times), 1) if hire_times else None

    # Stage distribution
    stage_counts: dict[str, int] = {s: 0 for s in settings.stages}
    for c in active:
        if c.stage in stage_counts:
            stage_counts[c.stage] += 1

    # Time per stage (average days)
    stage_times: dict[str, list[float]] = {s: [] for s in settings.stages}
    for c in candidates:
        c_activities = sorted(
            [a for a in activities if a.candidate_id == c.id and a.activity_type == "stage_change"],
            key=lambda a: a.created_at,
        )
        for i, act in enumerate(c_activities):
            next_time = c_activities[i + 1].created_at if i + 1 < len(c_activities) else datetime.utcnow()
            # Extract the stage from "Moved from X to Y" or "Candidate added at stage: X"
            if "to " in act.description:
                stage_name = act.description.split("to ")[-1]
            elif "stage: " in act.description:
                stage_name = act.description.split("stage: ")[-1]
            else:
                continue
            if stage_name in stage_times:
                days = (next_time - act.created_at).total_seconds() / 86400
                stage_times[stage_name].append(days)

    avg_stage_times = {}
    for stage, times in stage_times.items():
        if times:
            avg_stage_times[stage] = round(sum(times) / len(times), 1)

    # Source effectiveness
    source_counts: dict[str, dict[str, int]] = {}
    for c in candidates:
        src = c.source or "Unknown"
        if src not in source_counts:
            source_counts[src] = {"total": 0, "hired": 0}
        source_counts[src]["total"] += 1
        if c.status == "hired":
            source_counts[src]["hired"] += 1

    # Pipeline pass-through rates
    # Use exact matching: descriptions are "Moved from X to Y" or "Candidate added at stage: Y"
    def _candidate_reached_stage(c, stage, activities):
        for a in activities:
            if a.candidate_id != c.id or a.activity_type != "stage_change":
                continue
            if a.description.endswith(f"to {stage}") or a.description.endswith(f"stage: {stage}"):
                return True
        return False

    pass_through: dict[str, float] = {}
    ordered_stages = settings.stages
    for i, stage in enumerate(ordered_stages[:-1]):
        current = sum(1 for c in candidates if _candidate_reached_stage(c, stage, activities))
        next_stage = ordered_stages[i + 1]
        advanced = sum(1 for c in candidates if _candidate_reached_stage(c, next_stage, activities))
        if current > 0:
            pass_through[f"{stage} -> {next_stage}"] = round((advanced / current) * 100, 1)

    # Per-position stats
    position_stats = []
    for pos in positions:
        pos_candidates = [c for c in candidates if c.position_id == pos.id]
        pos_active = [c for c in pos_candidates if c.status == "active"]
        pos_hired = [c for c in pos_candidates if c.status == "hired"]
        position_stats.append({
            "title": pos.title,
            "status": pos.status,
            "total": len(pos_candidates),
            "active": len(pos_active),
            "hired": len(pos_hired),
        })

    return {
        "total_candidates": len(candidates),
        "active_count": len(active),
        "hired_count": len(hired),
        "rejected_count": len(rejected),
        "avg_time_to_hire": avg_time_to_hire,
        "stage_counts": stage_counts,
        "avg_stage_times": avg_stage_times,
        "source_counts": source_counts,
        "pass_through": pass_through,
        "position_stats": position_stats,
        "open_positions": len([p for p in positions if p.status == "open"]),
    }
