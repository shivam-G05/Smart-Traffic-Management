# Hardware bridge (Milestone 10)

The controller decides the signal; this folder only *shows* that decision on
real lights. Two drivers are provided, and both read the same endpoint
(`GET /api/signals/status`) from a running backend:

| Driver | Board | File |
|---|---|---|
| Python | Raspberry Pi (any model with GPIO) | `gpio_driver.py` |
| Arduino/C++ | ESP32 (or ESP8266 with pin changes) | `esp32_signal_driver/esp32_signal_driver.ino` |

Nothing in `simulation/`, `decision_engine/` or `backend/` changes: the driver
is a client, so it can be restarted, unplugged or swapped without touching the
control logic.

```
backend (laptop / Pi / container)         Pi or ESP32                signal heads
   GET /api/signals/status   ───────►   driver polls at 5 Hz  ───►   LEDs / relays
```

## 1. Wiring (12 LEDs, one set per approach)

Each LED: **long leg (anode) → 220 Ω resistor → GPIO pin**, **short leg
(cathode) → GND rail**. Never connect an LED without its resistor, and use
3.3 V GPIO pins rather than the 5 V rail.

| Approach | Red | Yellow | Green |
|---|---|---|---|
| North | GPIO 17 | GPIO 27 | GPIO 22 |
| South | GPIO 5 | GPIO 6 | GPIO 13 |
| East | GPIO 19 | GPIO 26 | GPIO 21 |
| West | GPIO 20 | GPIO 16 | GPIO 12 |

These are **BCM** numbers (not physical pin positions). To use different pins,
edit `PINS` at the top of `gpio_driver.py` (or `ROADS` in the ESP32 sketch).
Any Pi GND pin (physical 6, 9, 14, 20, 25, 30, 34, 39) feeds the ground rail.

For lamps larger than an LED, drive an opto-isolated relay or solid-state
relay module from the same pins instead — never mains wiring directly.

## 2. Raspberry Pi driver

```bash
sudo apt install -y python3-gpiozero
python3 hardware/gpio_driver.py --self-test                     # check wiring first
python3 hardware/gpio_driver.py --url http://<backend-ip>:8000  # then go live
```

- `--dry-run` prints the states instead of driving pins, so the driver can be
  tested on a laptop with no GPIO at all.
- If the backend is unreachable for three polls in a row, every approach goes
  to **blinking yellow** (the standard "signal out of service" indication)
  rather than freezing on the last state.

### Start automatically on boot

```bash
sudo cp hardware/traffic-signal.service /etc/systemd/system/
sudoedit /etc/systemd/system/traffic-signal.service   # set User, WorkingDirectory, --url
sudo systemctl enable --now traffic-signal
systemctl status traffic-signal
```

## 3. ESP32 driver

Open `esp32_signal_driver/esp32_signal_driver.ino` in the Arduino IDE (board:
"ESP32 Dev Module"), fill in `WIFI_SSID`, `WIFI_PASSWORD` and `BACKEND_HOST`,
then upload. It behaves exactly like the Pi driver, including the blinking
yellow failsafe, and needs no extra libraries.

The ESP32 is a good choice for the lights, but **not** for the camera: a
YOLO-class detector does not fit in its memory. Keep detection on the laptop,
the Pi, or a server, and let the ESP32 drive the signal heads.

## 4. Safety note for a real junction

This bridge is fine for a demo board. On a public road, signal safety must not
depend on software alone: a conflict-monitor unit in hardware has to force
flashing yellow if two conflicting greens ever appear, and the installation
needs approval from the road authority and a qualified electrician for the
mains side.
