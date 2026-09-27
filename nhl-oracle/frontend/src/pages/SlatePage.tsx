import { useParams } from "react-router-dom";
import { Shell } from "../components/Shell";
import { localSlateDate } from "../lib/api";

export function SlatePage() {
  const { date } = useParams<{ date: string }>();
  const slateDate = date ?? localSlateDate();

  return (
    <Shell eyebrow="Slate">
      <section className="panel">
        <p className="panel__kicker">Slate placeholder</p>
        <h1 className="panel__title">{slateDate}</h1>
        <p className="panel__body">
          Pool context, tip times, and the frozen five-card lineup will render
          here once the NHL hosted API serves{" "}
          <code>/slate/{"{date}"}</code> and <code>/lineup/{"{date}"}</code>.
          Client stubs already call those routes; no contest entry from this UI.
        </p>
        <ul className="panel__meta">
          <li>Format: five_card_ordered (Week 2 contract)</li>
          <li>Boost regime: none (pre-boost until every team has played)</li>
          <li>Contest entry: false</li>
        </ul>
      </section>
    </Shell>
  );
}
