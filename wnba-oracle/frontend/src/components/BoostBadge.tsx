// "Boost" pill — surfaces card_boost when the platform multiplier is non
// zero. WNBA contract emits boost as an additive bonus over baseline 1.0
// (e.g. 0.5 = +50%), so we render +Nx for visual parity with the slot
// score block.

import { Icon } from "./Icon";

interface Props {
  cardBoost: number;
}

export function BoostBadge({ cardBoost }: Props) {
  const label = `+${cardBoost.toFixed(2)}x`;
  return (
    <span className="boost-badge" title={`Card boost ${label}`}>
      <Icon name="bolt" />
      <span>{label}</span>
    </span>
  );
}
