const ROAD_ORDER = ["north", "east", "south", "west"];

function formatPct(value) {
  return value === null || value === undefined ? "-" : `${Math.round(value * 100)}%`;
}

function CameraPanel({ name, feed }) {
  return (
    <div className="overflow-hidden rounded-lg border border-white/10 bg-panelmuted">
      <div className="flex items-center justify-between px-3 py-1.5 text-xs">
        <span className="font-medium capitalize text-white/80">{name} CAM</span>
        <div className="flex items-center gap-2">
          {feed?.vision_emergency_detected && (
            <span
              className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-400"
              title="The camera matched an ambulance or fire truck this frame. Display only — never used for signal control."
            >
              CAMERA: EMERGENCY?
            </span>
          )}
          {feed && (
            <span
              className="text-white/40"
              title="Boxes the detector found this frame / real vehicles actually in the camera's view"
            >
              {feed.detected_count} det / {feed.ground_truth_count} gt
            </span>
          )}
        </div>
      </div>
      <div className="aspect-[5/6] w-full bg-black">
        {feed ? (
          <img
            src={`data:image/jpeg;base64,${feed.frame_jpeg_base64}`}
            alt={`${name} camera feed`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-white/30">No signal</div>
        )}
      </div>
      <div className="flex justify-between px-3 py-1.5 text-[11px] text-white/40">
        <span title="Share of drawn boxes that are on real vehicles">
          precision {feed ? formatPct(feed.precision) : "-"}
        </span>
        <span title="Share of real vehicles in view that got a box">recall {feed ? formatPct(feed.recall) : "-"}</span>
      </div>
      <div className="flex justify-between border-t border-white/5 px-3 py-1.5 text-[11px] text-cyan-300/70">
        <span title="Vehicles the tracker is following in this frame">active tracks {feed?.active_tracks ?? "-"}</span>
        <span title="Tracks started since launch, including false alarms">
          total counted {feed?.unique_vehicles_tracked ?? "-"}
        </span>
      </div>
    </div>
  );
}

function KeyItem({ term, wide = false, children }) {
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <dt className="inline font-semibold text-white/65">{term}</dt> <dd className="inline">— {children}</dd>
    </div>
  );
}

export default function CameraFeedGrid({ snapshot, explain }) {
  const roads = snapshot?.roads ?? {};
  const minHits = explain?.tracking?.min_hits;

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/70">
          Live CCTV Feeds — Haar Cascade Detection + ByteTrack
        </h2>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {ROAD_ORDER.map((name) => (
          <CameraPanel key={name} name={name} feed={roads[name]} />
        ))}
      </div>

      <dl className="mt-3 grid gap-x-4 gap-y-1 text-[11px] leading-snug text-white/45 sm:grid-cols-2">
        <KeyItem term="Green box">a detection on a real vehicle</KeyItem>
        <KeyItem term="Orange box">a false alarm — nothing real there</KeyItem>
        <KeyItem term="Gray outline">where the real vehicles actually are</KeyItem>
        <KeyItem term="Number on a box">detector confidence — higher is surer (a score, not a %)</KeyItem>
        <KeyItem term="det / gt">boxes found / real vehicles in view</KeyItem>
        <KeyItem term="Precision">share of boxes that are real vehicles</KeyItem>
        <KeyItem term="Recall">share of real vehicles that got a box</KeyItem>
        <KeyItem term="Cyan #N">
          tracking ID — the same vehicle keeps its number{minHits ? ` once matched in ${minHits} frames` : ""}
        </KeyItem>
        <KeyItem term="Active tracks">vehicles being followed in this frame</KeyItem>
        <KeyItem term="Total counted">tracks started since launch (includes false alarms)</KeyItem>
        <KeyItem term="CAMERA: EMERGENCY?" wide>
          the camera matched an ambulance or fire truck — shown for comparison only; the lights are controlled from
          exact vehicle positions, not from the camera.
        </KeyItem>
      </dl>
      <p className="mt-2 text-[11px] leading-snug text-white/35">
        Classic Haar cascades were trained on real photos, so accuracy on these synthetic frames is genuinely
        limited — the precision and recall shown are the real measured numbers, not placeholders.
      </p>
    </div>
  );
}
