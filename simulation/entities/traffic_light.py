from dataclasses import dataclass

from simulation.config import LightState


@dataclass
class TrafficLight:
    state: LightState = LightState.RED
    time_in_state_s: float = 0.0

    def set_state(self, new_state: LightState) -> None:
        if new_state != self.state:
            self.state = new_state
            self.time_in_state_s = 0.0

    def tick(self, dt: float) -> None:
        self.time_in_state_s += dt

    def to_state(self) -> dict:
        return {"state": self.state.value, "time_in_state": round(self.time_in_state_s, 2)}
