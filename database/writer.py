"""Milestone 8: turns live state/events into persisted rows.

`persist_sample` is called from analytics/collector.py's existing 1Hz
sampling loop, but only every Nth sample (see AnalyticsCollector's
persist_every_n_samples) — writing at full sample rate would hammer the DB
for no benefit. `persist_event` is called immediately/event-driven from
EmergencyPreemptionController's state transitions instead, since a rare,
timing-sensitive event shouldn't wait for the next periodic sample.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import RoadSnapshot, SignalEvent, SimulationRun, Snapshot, _utcnow

SessionFactory = async_sessionmaker[AsyncSession]


async def create_run(session_factory: SessionFactory, controller_type: str) -> int:
    async with session_factory() as session:
        run = SimulationRun(controller_type=controller_type)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def end_run(session_factory: SessionFactory, run_id: int) -> None:
    async with session_factory() as session:
        run = await session.get(SimulationRun, run_id)
        if run is not None:
            run.ended_at = _utcnow()
            await session.commit()


async def persist_sample(session_factory: SessionFactory, run_id: int, state: dict) -> None:
    async with session_factory() as session:
        snapshot = Snapshot(run_id=run_id, sim_time=state["sim_time"])
        session.add(snapshot)
        await session.flush()  # assign snapshot.id before attaching children

        for road_name, road in state["roads"].items():
            session.add(
                RoadSnapshot(
                    snapshot_id=snapshot.id,
                    road_name=road_name,
                    queue_length=road["queue_length"],
                    vehicle_count=road["vehicle_count"],
                    density_score=road["density_score"],
                    light_state=road["light"]["state"],
                    has_emergency_vehicle=road["has_emergency_vehicle"],
                    total_exited=road["total_exited"],
                    total_wait_time_s=road["total_wait_time_s"],
                )
            )
        await session.commit()


async def persist_event(
    session_factory: SessionFactory,
    run_id: int,
    sim_time: float,
    event_type: str,
    phase_name: str,
    road_name: str | None = None,
    details: dict | None = None,
) -> None:
    async with session_factory() as session:
        session.add(
            SignalEvent(
                run_id=run_id,
                sim_time=sim_time,
                road_name=road_name,
                event_type=event_type,
                phase_name=phase_name,
                details=details,
            )
        )
        await session.commit()


async def fetch_road_snapshot_rows(session_factory: SessionFactory, run_id: int) -> list[dict]:
    async with session_factory() as session:
        stmt = (
            select(Snapshot.sim_time, RoadSnapshot)
            .join(RoadSnapshot, RoadSnapshot.snapshot_id == Snapshot.id)
            .where(Snapshot.run_id == run_id)
            .order_by(Snapshot.sim_time)
        )
        result = await session.execute(stmt)
        return [
            {
                "sim_time": sim_time,
                "road_name": rs.road_name,
                "queue_length": rs.queue_length,
                "vehicle_count": rs.vehicle_count,
                "density_score": rs.density_score,
                "light_state": rs.light_state,
                "has_emergency_vehicle": rs.has_emergency_vehicle,
                "total_exited": rs.total_exited,
                "total_wait_time_s": rs.total_wait_time_s,
            }
            for sim_time, rs in result.all()
        ]


async def fetch_signal_events(session_factory: SessionFactory, run_id: int) -> list[dict]:
    async with session_factory() as session:
        stmt = select(SignalEvent).where(SignalEvent.run_id == run_id).order_by(SignalEvent.sim_time)
        result = await session.execute(stmt)
        return [
            {
                "sim_time": e.sim_time,
                "road_name": e.road_name,
                "event_type": e.event_type,
                "phase_name": e.phase_name,
            }
            for e in result.scalars().all()
        ]
