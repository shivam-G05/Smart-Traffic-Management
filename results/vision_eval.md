Vision pipeline on synthetic frames: seeds [1, 2, 3, 4], 9600 frames, 14874 vehicle instances in view (default detector).

| Detector variant | Precision (%) | Recall (%) | Detections/frame | ms/frame |
|---|---|---|---|---|
| Default (3x upscale, equalized) | 4.1 (3.5–5.6) | 8.2 (7.3–9.8) | 3.30 | 635 |
| 2x upscale | 63.3 (46.3–78.0) | 3.7 (2.3–6.4) | 0.09 | 273 |
| No upscaling | 100.0 (100.0–100.0) | 0.0 (0.0–0.0) | 0.00 | 84 |
| No histogram equalization | 100.0 (100.0–100.0) | 0.0 (0.0–0.0) | 0.00 | 346 |

Recall by vehicle class (default detector):

| Class | Instances | Recall (%) |
|---|---|---|
| car | 7888 | 7.1 |
| motorcycle | 3326 | 11.8 |
| auto | 1976 | 7.6 |
| bus | 773 | 7.2 |
| truck | 769 | 7.7 |
| fire_truck | 135 | 3.7 |
| ambulance | 7 | 14.3 |

Recall by distance from the stop line:

| Distance | Instances | Recall (%) |
|---|---|---|
| 0-20 m | 11326 | 5.4 |
| 20-40 m | 1783 | 16.9 |
| 40-60 m | 1765 | 17.4 |

False positives: 30380; 98.6% recur at the same spot in >= 10% of a camera's frames (static background, not vehicles).

| Tracker variant | Coverage (%) | Track precision (%) | Vehicles ever confirmed (%) | ID switches /100 veh. | Speed MAE (m/s) |
|---|---|---|---|---|---|
| ByteTrack-style (two-stage, Kalman) | 0.6 | 0.8 | 1.5 | 0.2 | 0.53 (n=82) |
| Single stage (low-confidence dropped) | 0.5 | 0.6 | 1.0 | 0.2 | 0.16 (n=61) |
| No motion model (last box) | 0.6 | 0.8 | 1.5 | 0.2 | n/a |
| Confirm after 1 match | 2.3 | 2.9 | 35.9 | 6.6 | 0.53 (n=82) |

Mean true speed of the vehicles behind those speed estimates: 0.56 m/s.
Coverage: share of vehicle instances in view with a confirmed track on them. Precision ranges in brackets: lowest-highest seed.
