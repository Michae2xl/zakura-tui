from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NodeState(StrEnum):
    STARTING = "starting"
    SYNCING = "syncing"
    READY = "ready"
    DEGRADED = "degraded"
    STOPPED = "stopped"


@dataclass(frozen=True)
class ServiceObservation:
    exists: bool
    active: bool
    detail: str


@dataclass(frozen=True)
class HealthObservation:
    reachable: bool
    ready: bool
    detail: str
    observed_at: float


@dataclass(frozen=True)
class SyncObservation:
    sync_percent: float | None = None
    current_height: int | None = None
    remaining_blocks: int | None = None
    network_upgrade: str | None = None
    latest_activity: str | None = None
    observed_at: float | None = None


@dataclass(frozen=True)
class TipObservation:
    height: int | None
    error: str | None
    observed_at: float


@dataclass(frozen=True)
class NodeSnapshot:
    state: NodeState
    service: ServiceObservation
    health: HealthObservation | None
    sync: SyncObservation
    status_message: str
    diagnostics: tuple[str, ...] = ()


def resolve_snapshot(
    *,
    service: ServiceObservation,
    health: HealthObservation | None,
    sync: SyncObservation,
    now: float,
    started_at: float,
    startup_grace_seconds: float,
    health_stale_seconds: float,
    diagnostics: tuple[str, ...] = (),
) -> NodeSnapshot:
    health_is_stale = (
        health is not None and now - health.observed_at > health_stale_seconds
    )
    if not service.exists or not service.active:
        state, message = NodeState.STOPPED, "SERVICE STOPPED"
    elif health is not None and health.ready and not health_is_stale:
        state, message = NodeState.READY, "SYNCHRONIZED"
    else:
        health_failed = health is None or not health.reachable or health_is_stale
        within_grace = now - started_at <= startup_grace_seconds
        if health_is_stale and not within_grace:
            state, message = NodeState.DEGRADED, "HEALTH STALE"
        elif health_failed and not within_grace:
            state, message = NodeState.DEGRADED, "HEALTH UNAVAILABLE"
        elif sync.sync_percent is not None:
            state, message = NodeState.SYNCING, "CATCHING UP"
        elif health_failed:
            state, message = NodeState.STARTING, "WAITING FOR NODE"
        else:
            state, message = NodeState.STARTING, "WAITING FOR SYNC DATA"
    return NodeSnapshot(state, service, health, sync, message, diagnostics)
