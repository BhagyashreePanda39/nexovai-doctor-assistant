import Icon from "./Icon.jsx";

const navigation = [
  { id: "overview", label: "Overview", icon: "overview" },
  { id: "doctors", label: "Doctors", icon: "doctors" },
  { id: "appointments", label: "Appointments", icon: "appointments" },
  { id: "availability", label: "Availability", icon: "availability" },
];

function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="sidebar">
      <a className="brand" href="#overview" onClick={() => onNavigate("overview")}>
        <span className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span className="brand-copy">
          <strong>NexovAI</strong>
          <small>CARE OPERATIONS</small>
        </span>
      </a>

      <div className="sidebar-section-label">WORKSPACE</div>
      <nav className="primary-nav" aria-label="Main navigation">
        {navigation.map((item) => (
          <button
            aria-current={activePage === item.id ? "page" : undefined}
            className={`nav-item${activePage === item.id ? " active" : ""}`}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            <Icon name={item.icon} size={19} />
            <span>{item.label}</span>
            {activePage === item.id && <span className="nav-active-mark" />}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-mark">
          <Icon name="mic" size={17} />
        </div>
        <div>
          <strong>Voice assistant</strong>
          <span>Browser-based care</span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
