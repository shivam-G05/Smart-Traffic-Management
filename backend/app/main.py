import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from analytics.collector import AnalyticsCollector
from database import writer
from database.session import Database

from app.api.routes import router as api_router
from app.comparison import build_comparison_snapshot
from app.core.config import settings
from app.core.controller_factory import build_controller
from app.event_recorder import EventRecorder
from app.simulation_runner import SimulationRunner
from app.vision_runner import VisionRunner
from app.ws.connection_manager import ConnectionManager

logger = logging.getLogger("main")

_OTHER_CONTROLLER_TYPE = {"fixed": "adaptive", "adaptive": "fixed"}


async def _run_comparison_loop(app: FastAPI, interval: float = 1.0) -> None:
    while True:
        try:
            app.state.latest_comparison = build_comparison_snapshot(
                app.state.analytics_collector,
                app.state.shadow_analytics_collector,
                app.state.primary_controller_type,
                app.state.shadow_controller_type,
            )
            await app.state.comparison_connection_manager.broadcast_json(app.state.latest_comparison)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Comparison broadcast failed; continuing")
            await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database = Database(settings.database_url)
    await app.state.database.init()
    app.state.run_id = await writer.create_run(app.state.database.session_factory, settings.controller_type)
    event_recorder = EventRecorder(app.state.database.session_factory, app.state.run_id)

    app.state.connection_manager = ConnectionManager()
    app.state.simulation_runner = SimulationRunner(
        app.state.connection_manager,
        controller=build_controller(settings.controller_type, on_event=event_recorder.record),
        seed=settings.comparison_seed,
    )
    app.state.simulation_runner.start()

    app.state.vision_connection_manager = ConnectionManager()
    app.state.vision_runner = VisionRunner(
        app.state.simulation_runner, app.state.vision_connection_manager
    )
    app.state.vision_runner.start()

    async def _persist_sample(state: dict) -> None:
        await writer.persist_sample(app.state.database.session_factory, app.state.run_id, state)

    app.state.analytics_connection_manager = ConnectionManager()
    app.state.analytics_collector = AnalyticsCollector(
        app.state.simulation_runner,
        manager=app.state.analytics_connection_manager,
        on_sample=_persist_sample,
    )
    app.state.analytics_collector.start()

    # Milestone 9: a shadow simulation running the *other* controller type
    # against the exact same seed, so vehicle arrivals match and the
    # controller is the only variable in the comparison. The primary
    # dashboard (above) is completely unaffected by any of this.
    app.state.primary_controller_type = settings.controller_type
    app.state.shadow_controller_type = _OTHER_CONTROLLER_TYPE[settings.controller_type]

    app.state.shadow_connection_manager = ConnectionManager()
    app.state.shadow_runner = SimulationRunner(
        app.state.shadow_connection_manager,
        controller=build_controller(app.state.shadow_controller_type),
        seed=settings.comparison_seed,
    )
    app.state.shadow_runner.start()

    app.state.shadow_analytics_collector = AnalyticsCollector(app.state.shadow_runner)
    app.state.shadow_analytics_collector.start()

    app.state.comparison_connection_manager = ConnectionManager()
    app.state.latest_comparison = {}
    app.state.comparison_task = asyncio.create_task(_run_comparison_loop(app))

    yield

    app.state.comparison_task.cancel()
    try:
        await app.state.comparison_task
    except asyncio.CancelledError:
        pass
    await app.state.shadow_analytics_collector.stop()
    await app.state.shadow_runner.stop()
    await app.state.analytics_collector.stop()
    await app.state.vision_runner.stop()
    await app.state.simulation_runner.stop()
    await writer.end_run(app.state.database.session_factory, app.state.run_id)
    await app.state.database.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws/simulation")
async def simulation_socket(websocket: WebSocket):
    manager: ConnectionManager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    runner: SimulationRunner = websocket.app.state.simulation_runner
    if runner.latest_state:
        await websocket.send_json(runner.latest_state)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/simulation/shadow")
async def simulation_shadow_socket(websocket: WebSocket):
    manager: ConnectionManager = websocket.app.state.shadow_connection_manager
    await manager.connect(websocket)
    runner: SimulationRunner = websocket.app.state.shadow_runner
    if runner.latest_state:
        await websocket.send_json(runner.latest_state)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/vision")
async def vision_socket(websocket: WebSocket):
    manager: ConnectionManager = websocket.app.state.vision_connection_manager
    await manager.connect(websocket)
    runner: VisionRunner = websocket.app.state.vision_runner
    if runner.latest_snapshot:
        await websocket.send_json(runner.latest_snapshot)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/analytics")
async def analytics_socket(websocket: WebSocket):
    manager: ConnectionManager = websocket.app.state.analytics_connection_manager
    await manager.connect(websocket)
    collector: AnalyticsCollector = websocket.app.state.analytics_collector
    snapshot = collector.latest_snapshot()
    if snapshot:
        await websocket.send_json(snapshot)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/comparison")
async def comparison_socket(websocket: WebSocket):
    manager: ConnectionManager = websocket.app.state.comparison_connection_manager
    await manager.connect(websocket)
    if websocket.app.state.latest_comparison:
        await websocket.send_json(websocket.app.state.latest_comparison)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
