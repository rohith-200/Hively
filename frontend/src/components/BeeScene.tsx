import { useEffect, useRef, useState } from "react";

/** Small, dependency-free companion for buttons and WebGL fallbacks. */
export function BeeLoader({ still = false }: { still?: boolean }) {
  return (
    <span className={`bee-loader ${still ? "is-still" : ""}`} aria-hidden="true">
      <i className="bee-wing bee-wing-back" />
      <i className="bee-wing bee-wing-front" />
      <i className="bee-abdomen" />
      <i className="bee-head"><b /></i>
      <i className="bee-antenna" />
    </span>
  );
}

export function BeeScene({
  variant = "welcome", reduced = false, activity = "vision",
}: {
  variant?: "welcome" | "working";
  reduced?: boolean;
  activity?: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const currentActivity = useRef(activity);
  const [ready, setReady] = useState(false);
  useEffect(() => { currentActivity.current = activity; }, [activity]);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let cancelled = false;
    let dispose: (() => void) | undefined;
    setReady(false);
    // The workspace is usable while the small decorative scene loads.
    void import("../lib/beeRenderer").then(({ mountBees }) => {
      if (cancelled) return;
      try {
        dispose = mountBees(element, {
          working: variant === "working", reduced,
          activity: () => currentActivity.current,
          onReady: () => { if (!cancelled) setReady(true); },
          onUnavailable: () => { if (!cancelled) setReady(false); },
        });
      } catch { /* Keep the illustrated bee when WebGL is unavailable. */ }
    }).catch(() => { /* Loading decorations never blocks the form. */ });
    return () => { cancelled = true; dispose?.(); };
  }, [variant, reduced]);
  return (
    <div className={`bee-scene bee-scene-${variant} ${ready ? "is-ready" : ""}`} aria-hidden="true">
      <div className="bee-scene-halo" />
      <div className="bee-scene-canvas" ref={host} />
      {!ready && <div className="bee-scene-fallback"><BeeLoader still={reduced} /></div>}
      <span className="bee-scene-caption">{variant === "working" ? "THE HIVE IS ON IT" : "SMALL TEAM. THOUGHTFUL FINDS."}</span>
    </div>
  );
}
