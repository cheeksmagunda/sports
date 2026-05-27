// Live T-minus to the next lineup freeze (first cron-job2 fire at
// 21:00 UTC). Re-renders every second; uses a single setInterval so
// reduced-motion users still get an accurate clock without animation.

import { useEffect, useState } from "react";
import { nextFreezeUTC, formatHMS } from "../lib/scheduling";

export function Countdown() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const target = nextFreezeUTC(new Date(now));
  const remaining = target.getTime() - now;
  const fireLocal = target.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });

  return (
    <div className="countdown" aria-label="Time until lineup freezes">
      <span className="countdown__caption">Lineup freezes in</span>
      <span className="countdown__value">{formatHMS(remaining)}</span>
      <span className="countdown__sub">at {fireLocal}</span>
    </div>
  );
}
