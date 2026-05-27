// Provenance band. Model artifact + payout regime + app version. Low-key
// row for "what produced these picks?" — not for daily reading.

import type { FrozenLineup } from "../lib/api";

interface Props {
  lineup: FrozenLineup | null;
  appVersion: string;
}

function shorten(hex: string, n = 12): string {
  if (!hex) return "—";
  return hex.length <= n ? hex : hex.slice(0, n);
}

export function Footer({ lineup, appVersion }: Props) {
  return (
    <footer className="footer" aria-label="Lineup provenance">
      <div className="footer__left">
        <span className="footer__dot" aria-hidden="true" />
        <span>Live &middot; honoring freeze semantics</span>
      </div>
      <div className="footer__right">
        <span>
          model{" "}
          <span className="footer__sha">{shorten(lineup?.model_sha ?? "")}</span>
        </span>
        <span className="footer__sep" aria-hidden="true" />
        <span>
          regime{" "}
          <span className="footer__sha">
            {lineup?.payout_regime ?? "—"}
          </span>
        </span>
        <span className="footer__sep" aria-hidden="true" />
        <span>{appVersion}</span>
      </div>
    </footer>
  );
}
