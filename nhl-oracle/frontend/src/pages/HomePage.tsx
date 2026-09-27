import { Link } from "react-router-dom";
import { Shell } from "../components/Shell";
import { localSlateDate } from "../lib/api";

export function HomePage() {
  const today = localSlateDate();

  return (
    <Shell eyebrow="Scaffold">
      <section className="hero">
        <p className="hero__kicker">Sports Oracle · NHL</p>
        <h1 className="hero__title">NHL Oracle</h1>
        <p className="hero__lede">
          Dark-ice shell for the future five-card ordered recommendations.
          Hosted API and freeze path are not live yet; this frontend is a
          deployable Vite+React scaffold only.
        </p>
        <div className="hero__actions">
          <Link className="btn btn--primary" to={`/slate/${today}`}>
            Open today&rsquo;s slate
          </Link>
          <Link className="btn btn--ghost" to="/health">
            Check /health
          </Link>
        </div>
      </section>
    </Shell>
  );
}
