const ROAD_ORDER = ["north", "east", "south", "west"];

function formatPct(value) {
  return value === null || value === undefined ? "-" : `${Math.round(value * 100)}%`;
}

function CameraPanel({ name, feed }) {
  return (
    <div className="overflow-hidden rounded-lg border border-white/10 bg-panelmuted">
      <div className="flex items-center justify-between px-3 py-1.5 text-xs">
        <span className="font-medium capitalize text-white/80">{name} CAM</span>
        {feed && (
          <span className="text-white/40">
            {feed.detected_count} det / {feed.ground_truth_count} gt
          </span>
        )}
      </div>
      <div className="aspect-[5/6] w-full bg-black">
        {feed ? (
          <img
            src={`data:image/jpeg;base64,${feed.frame_jpeg_base64}`}
            alt={`${name} camera feed`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-white/30">
            No signal
          </div>
        )}
      </div>
      <div className="flex justify-between px-3 py-1.5 text-[11px] text-white/40">
        <span>precision {feed ? formatPct(feed.precision) : "-"}</span>
        <span>recall {feed ? formatPct(feed.recall) : "-"}</span>
      </div>
    </div>
  );
}

export default function CameraFeedGrid({ snapshot }) {
  const roads = snapshot?.roads ?? {};

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/70">
          Live CCTV Feeds — Haar Cascade Detection
        </h2>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {ROAD_ORDER.map((name) => (
          <CameraPanel key={name} name={name} feed={roads[name]} />
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-snug text-white/35">
        Green box = detection matched to a real vehicle, orange = unmatched
        (false positive), gray outline = ground truth. Classic Haar cascades
        are a binary vehicle/non-vehicle detector trained on real photos —
        recall against these synthetic frames is genuinely limited; that
        precision/recall readout is the actual number, not a placeholder.
      </p>
    </div>
  );
}
