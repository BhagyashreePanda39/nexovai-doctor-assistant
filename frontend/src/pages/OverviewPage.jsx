import AppointmentsTable from "../components/AppointmentsTable.jsx";
import Icon from "../components/Icon.jsx";
import StatCard from "../components/StatCard.jsx";

function OverviewPage({
  doctors,
  appointments,
  availableSlots,
  loading,
  onTryVoice,
  onNavigate,
  recentAction,
}) {
  const cancelledCount = appointments.filter(
    (appointment) => appointment.status === "cancelled",
  ).length;
  const recentAppointments = [...appointments]
    .sort((left, right) => right.id - left.id)
    .slice(0, 5);

  return (
    <div className="page-content">
      <section className="welcome-row">
        <div>
          <span className="section-eyebrow">OVERVIEW</span>
          <h2>Care, in clear view.</h2>
          <p>Today’s clinic activity, organized in one place.</p>
        </div>
        <button className="button button-primary" onClick={onTryVoice} type="button">
          <Icon name="mic" size={17} />
          Try voice assistant
        </button>
      </section>

      <section aria-label="Clinic summary" className="stat-grid">
        <StatCard
          icon="doctors"
          label="Doctors"
          loading={loading}
          tone="blue"
          value={doctors.length}
        />
        <StatCard
          icon="appointments"
          label="Appointments"
          loading={loading}
          tone="violet"
          value={appointments.length}
        />
        <StatCard
          icon="availability"
          label="Available slots"
          loading={loading}
          tone="teal"
          value={availableSlots.length}
        />
        <StatCard
          icon="check"
          label="Cancelled"
          loading={loading}
          tone="amber"
          value={cancelledCount}
        />
      </section>

      <section className="overview-grid">
        <article className="surface-card recent-card">
          <div className="card-heading">
            <div>
              <span className="section-eyebrow">ACTIVITY</span>
              <h3>Recent appointments</h3>
            </div>
            <button
              className="link-button"
              onClick={() => onNavigate("appointments")}
              type="button"
            >
              View all
              <Icon name="chevron" size={16} />
            </button>
          </div>
          <AppointmentsTable
            appointments={recentAppointments}
            loading={loading}
            recentAction={recentAction}
          />
        </article>

        <article className="voice-promo">
          <div className="voice-promo-orbit" aria-hidden="true">
            <span />
            <span />
          </div>
          <span className="voice-promo-kicker">
            <span className="promo-live-dot" />
            VOICE APPOINTMENT DESK
          </span>
          <div className="voice-promo-content">
            <h3>Let patients book by simply speaking.</h3>
            <p>
              Check real doctor availability, then book or cancel with clear
              confirmations.
            </p>
          </div>
          <button
            className="voice-promo-button"
            onClick={onTryVoice}
            type="button"
          >
            Start a conversation
            <Icon name="arrow" size={17} />
          </button>
          <div className="voice-promo-footer">
            <span>Powered by NexovAI</span>
            <Icon name="mic" size={16} />
          </div>
        </article>
      </section>

      <section className="quick-links">
        <button className="quick-link" onClick={() => onNavigate("doctors")} type="button">
          <span className="quick-link-icon blue">
            <Icon name="doctors" size={18} />
          </span>
          <span>
            <strong>Explore doctors</strong>
            <small>Meet the care team</small>
          </span>
          <Icon name="chevron" size={17} />
        </button>
        <button
          className="quick-link"
          onClick={() => onNavigate("availability")}
          type="button"
        >
          <span className="quick-link-icon teal">
            <Icon name="availability" size={18} />
          </span>
          <span>
            <strong>Check availability</strong>
            <small>See open appointment times</small>
          </span>
          <Icon name="chevron" size={17} />
        </button>
      </section>
    </div>
  );
}

export default OverviewPage;
