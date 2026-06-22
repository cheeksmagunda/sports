// Live T-minus to the tip-relative lineup freeze. The target is
// freeze_target_utc from the /slate API (first_tip - freeze_lead_minutes,
// D104); there is no hardcoded clock. Re-renders every second via a single
// setInterval. When the target is unknown (job1 has not captured today's tips
// yet, or there is no slate) we show a neutral caption, not a misleading
// number.

import { useEffect, useState } from "react";
import { formatHMS, msUntil } from "../lib/scheduling";

interface Props {
  targetUtc: string | null;
}

export function Countdown({ targetUtc }: Props) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const remaining = msUntil(targetUtc, now);

  if (remaining === null) {
    return (
      <div className="countdown" aria-label="Waiting for today's slate">
        <span className="countdown__caption">
          Lineup freezes ~40 min before first tip
        </span>
      </div>
    );
  }

  const freezeLocal = new Date(targetUtc as string).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });

  return (
    <div className="countdown" aria-label="Time until lineup freezes">
      <span className="countdown__caption">
        {remaining > 0 ? "Lineup freezes in" : "Freezing the lineup"}
      </span>
      <span className="countdown__value">{formatHMS(remaining)}</span>
      <span className="countdown__sub">at {freezeLocal}</span>
    </div>
  );
}
