// Header nav item: a quiet dot that only calls attention to itself when
// there's something to see. Only error/critical escalate color -- "ok"
// and "warn" both render as the same neutral quiet state.

import { Link } from "react-router-dom";
import { useWatchdogStatus } from "../hooks/useWatchdogStatus";

export function WatchdogDot() {
  const status = useWatchdogStatus();
  const severity = status === "critical" || status === "error" ? status : "quiet";

  const label =
    severity === "critical"
      ? "Watchdog: critical event, see system status"
      : severity === "error"
        ? "Watchdog: error event, see system status"
        : "Watchdog: no active alerts";

  return (
    <Link
      to="/system"
      className="watchdog-dot"
      data-severity={severity}
      aria-label={label}
      title={label}
    >
      <span className="watchdog-dot__mark" aria-hidden="true" />
    </Link>
  );
}
