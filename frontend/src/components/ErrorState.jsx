import Icon from "./Icon.jsx";

function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state" role="alert">
      <span className="error-state-icon">
        <Icon name="alert" size={20} />
      </span>
      <div>
        <strong>We couldn’t load the clinic data.</strong>
        <p>{message}</p>
        <button className="link-button" onClick={onRetry} type="button">
          Try again
          <Icon name="chevron" size={15} />
        </button>
      </div>
    </div>
  );
}

export default ErrorState;
