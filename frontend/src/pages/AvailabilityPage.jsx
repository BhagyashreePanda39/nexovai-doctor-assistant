import { useMemo, useState } from "react";

import EmptyState from "../components/EmptyState.jsx";
import Icon from "../components/Icon.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

function formatDate(value) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function AvailabilityPage({ doctors, slots, loading }) {
  const [doctorFilter, setDoctorFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("");
  const filteredSlots = useMemo(
    () =>
      slots.filter(
        (slot) =>
          (doctorFilter === "all" ||
            String(slot.doctor_id) === doctorFilter) &&
          (!dateFilter || slot.appointment_date === dateFilter),
      ),
    [dateFilter, doctorFilter, slots],
  );

  return (
    <div className="page-content">
      <section className="page-intro-row">
        <div>
          <span className="section-eyebrow">SCHEDULE</span>
          <h2>Availability</h2>
          <p>Open times and confirmed appointments across the care team.</p>
        </div>
        <div className="schedule-summary">
          <span className="schedule-legend">
            <i className="legend-dot available" />
            Available
          </span>
          <span className="schedule-legend">
            <i className="legend-dot booked" />
            Booked
          </span>
        </div>
      </section>

      <section className="surface-card schedule-card">
        <div className="schedule-toolbar">
          <div className="filter-control">
            <label htmlFor="doctor-filter">Doctor</label>
            <select
              id="doctor-filter"
              onChange={(event) => setDoctorFilter(event.target.value)}
              value={doctorFilter}
            >
              <option value="all">All doctors</option>
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-control date-filter">
            <label htmlFor="date-filter">Appointment date</label>
            <input
              id="date-filter"
              onChange={(event) => setDateFilter(event.target.value)}
              type="date"
              value={dateFilter}
            />
          </div>
          <div className="schedule-total">
            <span>{loading ? "—" : filteredSlots.length}</span>
            <small>slots shown</small>
          </div>
        </div>

        {loading ? (
          <div className="table-loading" aria-label="Loading availability">
            {[0, 1, 2, 3, 4].map((row) => (
              <span className="skeleton table-skeleton-row" key={row} />
            ))}
          </div>
        ) : filteredSlots.length === 0 ? (
          <EmptyState
            compact
            description="Try another date or doctor to see scheduled times."
            title="No slots found"
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table availability-table">
              <thead>
                <tr>
                  <th>Doctor</th>
                  <th>Speciality</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredSlots.map((slot) => (
                  <tr key={`${slot.doctor_id}-${slot.id}`}>
                    <td>
                      <div className="doctor-table-cell">
                        <span className="doctor-mini-avatar">
                          {slot.doctor.name
                            .replace(/^Dr\.?\s*/i, "")
                            .charAt(0)}
                        </span>
                        <strong>{slot.doctor.name}</strong>
                      </div>
                    </td>
                    <td>{slot.doctor.speciality}</td>
                    <td>{formatDate(slot.appointment_date)}</td>
                    <td>
                      {new Intl.DateTimeFormat("en-IN", {
                        hour: "numeric",
                        minute: "2-digit",
                      }).format(
                        new Date(
                          `${slot.appointment_date}T${slot.appointment_time}`,
                        ),
                      )}
                    </td>
                    <td>
                      <StatusBadge status={slot.is_booked} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="availability-note">
        <Icon name="availability" size={17} />
        <span>
          Booked times come from active appointments; cancelled slots are shown
          as available again.
        </span>
      </div>
    </div>
  );
}

export default AvailabilityPage;
