"""Milestone 8: SQLAlchemy 2.0 models.

Two-table snapshot split (Snapshot + RoadSnapshot) rather than one wide
table repeating each of the 4 roads' columns — avoids denormalized
repetition and matches the per-road query shape analytics/collector.py
already needs.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    controller_type: Mapped[str] = mapped_column(String(64))

    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="run")
    events: Mapped[list["SignalEvent"]] = relationship(back_populates="run")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id"))
    sim_time: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    run: Mapped["SimulationRun"] = relationship(back_populates="snapshots")
    road_snapshots: Mapped[list["RoadSnapshot"]] = relationship(back_populates="snapshot")


class RoadSnapshot(Base):
    __tablename__ = "road_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"))
    road_name: Mapped[str] = mapped_column(String(16))
    queue_length: Mapped[int] = mapped_column(Integer)
    vehicle_count: Mapped[int] = mapped_column(Integer)
    density_score: Mapped[float] = mapped_column(Float)
    light_state: Mapped[str] = mapped_column(String(16))
    has_emergency_vehicle: Mapped[bool] = mapped_column(Boolean)
    total_exited: Mapped[int] = mapped_column(Integer)
    total_wait_time_s: Mapped[float] = mapped_column(Float)

    snapshot: Mapped["Snapshot"] = relationship(back_populates="road_snapshots")


class SignalEvent(Base):
    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id"))
    sim_time: Mapped[float] = mapped_column(Float)
    road_name: Mapped[str | None] = mapped_column(String(16), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    phase_name: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    run: Mapped["SimulationRun"] = relationship(back_populates="events")
