"""Raspberry Pi signal-head driver.

Reads the live light state from the running backend and mirrors it on GPIO
pins (LEDs for the demo model, relays for bigger lamps). The controller logic
is untouched: this only reflects whatever the backend already decided.

    python3 hardware/gpio_driver.py --url http://192.168.1.5:8000
    python3 hardware/gpio_driver.py --dry-run          # no Pi needed, prints only
    python3 hardware/gpio_driver.py --self-test        # cycle every LED once

Failsafe: if the backend cannot be reached, every approach is driven to a
blinking yellow (the standard "signal out of service" indication) instead of
freezing on the last state.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# BCM pin numbers: road -> (red, yellow, green). Change these to match wiring.
PINS = {
    "north": (17, 27, 22),
    "south": (5, 6, 13),
    "east": (19, 26, 21),
    "west": (20, 16, 12),
}
COLORS = ("red", "yellow", "green")
POLL_HZ = 5.0
BLINK_HZ = 1.0
REQUEST_TIMEOUT_S = 2.0
FAILS_BEFORE_FAILSAFE = 3  # one slow reply must not trigger the failsafe


class Outputs:
    """GPIO outputs, or console output when --dry-run / gpiozero is missing."""

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self._last = None
        if dry_run:
            self.leds = None
            return
        from gpiozero import LED  # imported here so a laptop can run --dry-run

        self.leds = {road: {c: LED(pin) for c, pin in zip(COLORS, pins)} for road, pins in PINS.items()}

    def set(self, states: dict) -> None:
        """states: {"north": "red"|"yellow"|"green"|"off", ...}"""
        if states == self._last:
            return
        self._last = dict(states)
        if self.dry_run:
            print("  ".join(f"{road[:1].upper()}={state:6}" for road, state in states.items()), flush=True)
            return
        for road, state in states.items():
            for color, led in self.leds[road].items():
                led.on() if color == state else led.off()

    def close(self) -> None:
        if self.leds:
            for road in self.leds.values():
                for led in road.values():
                    led.close()


def fetch_states(url: str, timeout: float) -> dict | None:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/signals/status", timeout=timeout) as response:
            payload = json.load(response)
        return {road: info["light"] for road, info in payload["roads"].items()}
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None


def self_test(out: Outputs) -> None:
    for color in COLORS:
        out.set({road: color for road in PINS})
        print(f"all {color}")
        time.sleep(1.0)
    for road in PINS:
        for color in COLORS:
            out.set({r: (color if r == road else "off") for r in PINS})
            print(f"{road} {color}")
            time.sleep(0.4)
    out.set({road: "off" for road in PINS})


def run(url: str, out: Outputs) -> None:
    period = 1.0 / POLL_HZ
    offline_since = None
    fails = 0
    while True:
        states = fetch_states(url, timeout=REQUEST_TIMEOUT_S)
        now = time.monotonic()
        if states is None:
            fails += 1
            if fails < FAILS_BEFORE_FAILSAFE:
                time.sleep(period)
                continue
            if offline_since is None:
                offline_since = now
                print(f"backend unreachable at {url} — blinking yellow", file=sys.stderr, flush=True)
            on = int(now * BLINK_HZ) % 2 == 0
            out.set({road: ("yellow" if on else "off") for road in PINS})
        else:
            fails = 0
            if offline_since is not None:
                print("backend back online", file=sys.stderr, flush=True)
                offline_since = None
            out.set({road: states.get(road, "red") for road in PINS})
        time.sleep(period)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend base URL (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true", help="print states instead of driving GPIO pins")
    parser.add_argument("--self-test", action="store_true", help="cycle every LED once and exit")
    args = parser.parse_args()

    out = Outputs(dry_run=args.dry_run)
    try:
        if args.self_test:
            self_test(out)
        else:
            run(args.url, out)
    except KeyboardInterrupt:
        pass
    finally:
        out.set({road: "off" for road in PINS})
        out.close()


if __name__ == "__main__":
    main()
