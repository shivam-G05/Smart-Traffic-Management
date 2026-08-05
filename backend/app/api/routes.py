from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/intersection/state")
async def intersection_state(request: Request):
    runner = request.app.state.simulation_runner
    return runner.latest_state


@router.get("/signals/status")
async def signals_status(request: Request):
    runner = request.app.state.simulation_runner
    state = runner.latest_state
    if not state:
        return {"active_phase": None, "roads": {}}
    return {
        "active_phase": state.get("active_phase"),
        "controller": state.get("controller"),
        "roads": {
            name: {
                "light": road["light"]["state"],
                "queue_length": road["queue_length"],
                "has_emergency_vehicle": road["has_emergency_vehicle"],
            }
            for name, road in state.get("roads", {}).items()
        },
    }
