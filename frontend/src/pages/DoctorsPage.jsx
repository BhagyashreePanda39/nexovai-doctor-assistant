import EmptyState from "../components/EmptyState.jsx";
import Icon from "../components/Icon.jsx";

function getInitials(name) {
  return name
    .replace(/^Dr\.?\s*/i, "")
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase();
}

function DoctorsPage({ doctors, loading }) {
  return (
    <div className="page-content">
      <section className="page-intro-row">
        <div>
          <span className="section-eyebrow">CARE TEAM</span>
          <h2>Doctors</h2>
          <p>Specialists available through the NexovAI appointment desk.</p>
        </div>
        {!loading && (
          <div className="result-count">
            <strong>{doctors.length}</strong>
            <span>{doctors.length === 1 ? "doctor" : "doctors"}</span>
          </div>
        )}
      </section>

      {loading ? (
        <div className="doctor-grid">
          {[0, 1, 2, 3].map((item) => (
            <div className="doctor-card doctor-card-loading" key={item}>
              <span className="skeleton doctor-avatar-skeleton" />
              <span className="skeleton doctor-line wide" />
              <span className="skeleton doctor-line" />
              <span className="skeleton doctor-line short" />
            </div>
          ))}
        </div>
      ) : doctors.length === 0 ? (
        <EmptyState
          description="Doctor profiles will appear when the clinic directory has data."
          title="No doctors to display"
        />
      ) : (
        <div className="doctor-grid">
          {doctors.map((doctor, index) => (
            <article className="doctor-card" key={doctor.id}>
              <div className={`doctor-avatar avatar-tone-${index % 4}`}>
                {getInitials(doctor.name)}
              </div>
              <div className="doctor-card-title">
                <h3>{doctor.name}</h3>
                <span className="speciality-pill">{doctor.speciality}</span>
              </div>
              <div className="doctor-card-divider" />
              <div className="doctor-details">
                <span>
                  <Icon name="availability" size={16} />
                  <strong>{doctor.experience}</strong> years experience
                </span>
                <span>
                  <span className="fee-symbol">₹</span>
                  <strong>{doctor.consultation_fee}</strong> consultation
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

export default DoctorsPage;
