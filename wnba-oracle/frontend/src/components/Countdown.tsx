// Live T-minus to the next cron-job1 fire at 13:00 UTC. Re-renders
// every second; uses a single setInterval so reduced-motion users still
// get an accurate clock without animation.

import { useEffect, useState } from "react";
import { nextFireUTC, formatHMS } from "../lib/scheduling";

export function Countdown() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const target = nextFireUTC(new Date(now));
  const remaining = target.getTime() - now;
  const fireLocal = target.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });

  return (
    <div className="countdown" aria-label="Time until next oracle fire">
      <span className="countdown__caption">Next fire in</span>
      <span className="countdown__value">{formatHMS(remaining)}</span>
      <span className="countdown__sub">at {fireLocal}</span>
    </div>
  );
}
