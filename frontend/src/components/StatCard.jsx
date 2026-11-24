import Icon from "./Icon.jsx";

function StatCard({ label, value, icon, tone, loading }) {
  return (
    <article className="stat-card">
      <div className={`stat-icon ${tone}`}>
        <Icon name={icon} size={20} />
      </div>
      <div className="stat-card-copy">
        <span className="stat-label">{label}</span>
        {loading ? (
          <span className="skeleton stat-skeleton" aria-label="Loading" />
        ) : (
          <strong className="stat-value">{value}</strong>
        )}
      </div>
      <span className="stat-card-corner" aria-hidden="true">
        <Icon name="arrow" size={15} />
      </span>
    </article>
  );
}

export default StatCard;
