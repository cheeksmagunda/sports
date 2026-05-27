// Full-bleed oracle loader. Two modes:
//
//   1. intro:   brief first-mount hold so the page never flashes the
//               bare canvas before the first round-trip resolves.
//   2. waiting: production "no lineup yet" state — pre-fire or
//               between fires. Shows a T-minus countdown.

import { useEffect, useState } from "react";
import { Countdown } from "./Countdown";

const ROTATION = [
  "READING THE SLATE",
  "CONSULTING THE ORACLE",
  "CALCULATING EDGE",
  "ANALYZING MATCHUPS",
  "PROJECTING VALUE",
  "SCANNING THE FIVE",
] as const;

const ROTATION_INTERVAL_MS = 1800;

interface Props {
  visible: boolean;
  fading?: boolean;
  mode?: "intro" | "waiting";
}

export function OracleLoader({
  visible,
  fading = false,
  mode = "waiting",
}: Props) {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (!visible) return;
    setIdx(0);
    const id = setInterval(() => {
      setIdx((p) => (p + 1) % ROTATION.length);
    }, ROTATION_INTERVAL_MS);
    return () => clearInterval(id);
  }, [visible]);

  if (!visible) return null;

  return (
    <div
      className="oracle-loader"
      role="status"
      aria-live="polite"
      data-fading={fading ? "true" : "false"}
      data-mode={mode}
    >
      <div className="oracle-loader__inner">
        <div className="pyramid-loader" aria-hidden="true">
          <div className="wrap">
            <span className="side side-1" />
            <span className="side side-2" />
            <span className="side side-3" />
            <span className="side side-4" />
            <span className="shadow" />
          </div>
        </div>
        <h2 key={ROTATION[idx]} className="oracle-message">
          {ROTATION[idx]}
        </h2>
        {mode === "waiting" ? (
          <Countdown />
        ) : (
          <span className="oracle-label">Loading the oracle</span>
        )}
      </div>
    </div>
  );
}
