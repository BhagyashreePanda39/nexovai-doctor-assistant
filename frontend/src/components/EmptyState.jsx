function EmptyState({ title, description, compact = false }) {
  return (
    <div className={`empty-state${compact ? " compact" : ""}`}>
      <span className="empty-state-mark" aria-hidden="true">
        <span />
        <span />
      </span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

export default EmptyState;
