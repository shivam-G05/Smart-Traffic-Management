"""Virtual camera + detector constants.

The camera's contract is "render a road's approach given its public state
dict" — the same dict a real CCTV integration would eventually replace with
an actual frame grab. `vision/` depends only on that dict shape (plus the
shared STOP_LINE_POS_M geometry constant) and never touches simulation
entities/logic directly, which is what makes swapping in real cameras later
a config change instead of a rewrite.
"""

from pathlib import Path

FRAME_WIDTH_PX = 200
FRAME_HEIGHT_PX = 240
VIEW_DISTANCE_M = 60.0  # how far back from the stop line the camera sees
PX_PER_M = FRAME_HEIGHT_PX / VIEW_DISTANCE_M

LANE_WIDTH_PX = 90
LANES_PER_ROAD = 2

CASCADE_PATH = Path(__file__).parent / "models" / "cars.xml"

# Haar cascade tuning. The cascade's own training window is 20x20, close to
# or larger than our rendered vehicles at native resolution, so frames are
# upscaled before detection (see detector.py) and minSize is expressed in
# that upscaled space.
UPSCALE_FACTOR = 3
DETECT_SCALE_FACTOR = 1.05
DETECT_MIN_NEIGHBORS = 2
DETECT_MIN_SIZE_PX = (20, 20)

# A detection counts as matching a ground-truth vehicle if the detection's
# center falls within the vehicle's box, padded by this many pixels. Used
# only to *label* a detection with a vehicle type for display, and for the
# honesty metrics (precision/recall) surfaced in the UI — never fed back
# into what was actually detected. Center-containment rather than IoU
# because detection boxes come out of the cascade far smaller than a
# vehicle's actual footprint (its 20x20 training window downscaled through
# our upscale-then-detect step), so IoU against the full vehicle box would
# almost never clear a meaningful threshold even for a correct hit.
MATCH_PADDING_PX = 4

VISION_BROADCAST_HZ = 2
