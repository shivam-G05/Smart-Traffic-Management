from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import settings
from app.simulation_runner import SimulationRunner
from app.vision_runner import VisionRunner
from app.ws.connection_manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.connection_manager = ConnectionManager()
    app.state.simulation_runner = SimulationRunner(app.state.connection_manager)
    app.state.simulation_runner.start()

    app.state.vision_connection_manager = ConnectionManager()
    app.state.vision_runner = VisionRunner(
        app.state.simulation_runner, app.state.vision_connection_manager
    )
    app.state.vision_runner.start()

    yield

    await app.state.vision_runner.stop()
    await app.state.simulation_runner.stop()


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
