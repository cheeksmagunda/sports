// Error / no-lineup block. Single retry affordance when the parent
// provides one.

import { Icon } from "./Icon";

interface Props {
  title: string;
  copy: string;
  detail?: string | null;
  onRetry?: () => void;
}

export function ErrorState({ title, copy, detail, onRetry }: Props) {
  return (
    <div className="error-state" role="alert" aria-live="assertive">
      <span className="error-state__icon" aria-hidden="true">
        <Icon name="warn" size={20} />
      </span>
      <h2 className="error-state__title">{title}</h2>
      <p className="error-state__copy">{copy}</p>
      {detail ? <p className="error-state__detail">{detail}</p> : null}
      {onRetry ? (
        <div className="error-state__actions">
          <button
            type="button"
            className="error-state__retry"
            onClick={onRetry}
          >
            Try again
          </button>
        </div>
      ) : null}
    </div>
  );
}
