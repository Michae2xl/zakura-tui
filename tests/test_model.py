import pytest

from zakura_tui.model import (
    HealthObservation,
    NodeState,
    ServiceObservation,
    SyncObservation,
    resolve_snapshot,
)


ACTIVE = ServiceObservation(exists=True, active=True, detail="active")
INACTIVE = ServiceObservation(exists=True, active=False, detail="inactive")
READY = HealthObservation(reachable=True, ready=True, detail="ok", observed_at=100.0)
NOT_READY = HealthObservation(
    reachable=True, ready=False, detail="503", observed_at=100.0
)
UNREACHABLE = HealthObservation(
    reachable=False, ready=False, detail="timeout", observed_at=100.0
)
SYNC = SyncObservation(
    sync_percent=81.25,
    current_height=3_400_000,
    remaining_blocks=12_000,
    network_upgrade="Nu6_2",
    latest_activity="block 3,400,000 verified",
    observed_at=100.0,
)


@pytest.mark.parametrize(
    ("service", "health", "now", "expected"),
    [
        (INACTIVE, READY, 100.0, NodeState.STOPPED),
        (ACTIVE, READY, 100.0, NodeState.READY),
        (ACTIVE, NOT_READY, 100.0, NodeState.SYNCING),
        (ACTIVE, None, 105.0, NodeState.SYNCING),
        (ACTIVE, UNREACHABLE, 120.0, NodeState.DEGRADED),
    ],
)
def test_state_resolution_priority(service, health, now, expected) -> None:
    snapshot = resolve_snapshot(
        service=service,
        health=health,
        sync=SYNC,
        now=now,
        started_at=100.0,
        startup_grace_seconds=15.0,
        health_stale_seconds=10.0,
    )
    assert snapshot.state is expected


def test_active_node_without_health_or_sync_data_is_starting() -> None:
    snapshot = resolve_snapshot(
        service=ACTIVE,
        health=None,
        sync=SyncObservation(),
        now=105.0,
        started_at=100.0,
        startup_grace_seconds=15.0,
        health_stale_seconds=10.0,
    )
    assert snapshot.state is NodeState.STARTING
    assert snapshot.status_message == "WAITING FOR NODE"


def test_old_health_observation_is_degraded() -> None:
    snapshot = resolve_snapshot(
        service=ACTIVE,
        health=HealthObservation(True, False, "old", observed_at=80.0),
        sync=SYNC,
        now=100.0,
        started_at=0.0,
        startup_grace_seconds=15.0,
        health_stale_seconds=10.0,
    )
    assert snapshot.state is NodeState.DEGRADED
    assert snapshot.status_message == "HEALTH STALE"


def test_stale_ready_observation_cannot_force_ready() -> None:
    snapshot = resolve_snapshot(
        service=ACTIVE,
        health=HealthObservation(True, True, "ok", observed_at=80.0),
        sync=SYNC,
        now=100.0,
        started_at=0.0,
        startup_grace_seconds=15.0,
        health_stale_seconds=10.0,
    )
    assert snapshot.state is NodeState.DEGRADED
    assert snapshot.status_message == "HEALTH STALE"


def test_reducer_preserves_operator_diagnostics() -> None:
    snapshot = resolve_snapshot(
        service=ACTIVE,
        health=NOT_READY,
        sync=SYNC,
        now=100.0,
        started_at=100.0,
        startup_grace_seconds=15.0,
        health_stale_seconds=10.0,
        diagnostics=("WAITING FOR LOG: /tmp/zakurad.log",),
    )
    assert snapshot.state is NodeState.SYNCING
    assert snapshot.diagnostics == ("WAITING FOR LOG: /tmp/zakurad.log",)
