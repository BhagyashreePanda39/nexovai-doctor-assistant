import Icon from "./Icon.jsx";

function Topbar({ title, subtitle, refreshing, onRefresh }) {
  const currentDate = new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date());

  return (
    <header className="topbar">
      <div className="topbar-title">
        <span className="topbar-kicker">CLINIC WORKSPACE</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="topbar-actions">
        <div className="today-chip">
          <Icon name="calendar" size={17} />
          <span>{currentDate}</span>
        </div>
        <button
          aria-label="Refresh dashboard data"
          className={`icon-button${refreshing ? " is-refreshing" : ""}`}
          disabled={refreshing}
          onClick={onRefresh}
          title="Refresh data"
          type="button"
        >
          <Icon name="refresh" size={18} />
        </button>
        <div className="workspace-profile">
          <span className="profile-avatar">N</span>
          <span className="profile-label">
            <strong>Care team</strong>
            <small>Workspace</small>
          </span>
        </div>
      </div>
    </header>
  );
}

export default Topbar;
