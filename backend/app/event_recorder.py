"""Bridges EmergencyPreemptionController's synchronous on_event callback
(invoked from inside the synchronous physics tick, see SimulationRunner)
to the async database writer, by scheduling a task rather than awaiting
inline — the tick loop itself must never block on a DB write.
"""

import asyncio

from database import writer


class EventRecorder:
    def __init__(self, session_factory, run_id: int):
        self.session_factory = session_factory
        self.run_id = run_id

    def record(self, sim_time: float, event_type: str, phase_name: str, road_name: str | None) -> None:
        asyncio.create_task(
            writer.persist_event(
                self.session_factory,
                self.run_id,
                sim_time=sim_time,
                event_type=event_type,
                phase_name=phase_name,
                road_name=road_name,
            )
        )
