from __future__ import annotations

from .model import (
    HealthObservation,
    NodeSnapshot,
    NodeState,
    ServiceObservation,
    SyncObservation,
)


def demo_snapshot(name: str) -> NodeSnapshot:
    active = ServiceObservation(True, True, "active")
    sync = SyncObservation(
        sync_percent=99.824,
        current_height=3_407_462,
        remaining_blocks=5_928,
        network_upgrade="Nu6_2",
        latest_activity="17:02:09 block 3,407,462 verified",
        observed_at=100.0,
    )
    if name == "starting":
        return NodeSnapshot(
            NodeState.STARTING,
            active,
            None,
            SyncObservation(),
            "WAITING FOR NODE",
        )
    if name == "syncing":
        return NodeSnapshot(
            NodeState.SYNCING,
            active,
            HealthObservation(True, False, "503", 100.0),
            sync,
            "CATCHING UP",
        )
    if name == "ready":
        ready_sync = SyncObservation(
            sync_percent=100.0,
            current_height=3_413_390,
            remaining_blocks=0,
            network_upgrade="Nu6_2",
            latest_activity="17:02:23 chain tip synchronized",
            observed_at=100.0,
        )
        return NodeSnapshot(
            NodeState.READY,
            active,
            HealthObservation(True, True, "ok", 100.0),
            ready_sync,
            "SYNCHRONIZED",
        )
    if name == "degraded":
        return NodeSnapshot(
            NodeState.DEGRADED,
            active,
            HealthObservation(False, False, "connection refused", 100.0),
            sync,
            "HEALTH UNAVAILABLE",
        )
    if name == "stopped":
        service = ServiceObservation(True, False, "inactive")
        return NodeSnapshot(
            NodeState.STOPPED,
            service,
            None,
            SyncObservation(),
            "SERVICE STOPPED",
        )
    raise ValueError(f"unsupported demo state: {name}")


class DemoMonitor:
    def __init__(self, state: str) -> None:
        self.snapshot = demo_snapshot(state)

    def poll(self) -> NodeSnapshot:
        return self.snapshot

    def close(self) -> None:
        return None
