from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import settings
from app.simulation_runner import SimulationRunner
from app.ws.connection_manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.connection_manager = ConnectionManager()
    app.state.simulation_runner = SimulationRunner(app.state.connection_manager)
    app.state.simulation_runner.start()
    yield
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
