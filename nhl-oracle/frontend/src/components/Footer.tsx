interface Props {
  appVersion: string;
  apiStatus: string;
}

export function Footer({ appVersion, apiStatus }: Props) {
  return (
    <footer className="footer" aria-label="App provenance">
      <div className="footer__left">
        <span className="footer__dot" aria-hidden="true" />
        <span>Scaffold &middot; five-card ordered</span>
      </div>
      <div className="footer__right">
        <span>
          api <span className="footer__sha">{apiStatus}</span>
        </span>
        <span className="footer__sep" aria-hidden="true" />
        <span>{appVersion}</span>
      </div>
    </footer>
  );
}
