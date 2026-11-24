import EmptyState from "./EmptyState.jsx";
import Icon from "./Icon.jsx";
import StatusBadge from "./StatusBadge.jsx";

function formatAppointmentDate(appointment) {
  const value = new Date(
    `${appointment.appointment_date}T${appointment.appointment_time}`,
  );
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(value);
}

function formatAppointmentTime(appointment) {
  const value = new Date(
    `${appointment.appointment_date}T${appointment.appointment_time}`,
  );
  return new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
  }).format(value);
}

function AppointmentsTable({
  appointments,
  loading,
  showActions = false,
  pendingId,
  cancellingId,
  actionError,
  onCancel,
  onConfirmCancel,
  onKeepAppointment,
  recentAction,
}) {
  if (loading) {
    return (
      <div className="table-loading" aria-label="Loading appointments">
        {[0, 1, 2, 3].map((row) => (
          <span className="skeleton table-skeleton-row" key={row} />
        ))}
      </div>
    );
  }

  if (appointments.length === 0) {
    return (
      <EmptyState
        compact
        description="Appointments will appear here after they are booked."
        title="No appointments yet"
      />
    );
  }

  return (
    <>
      {actionError && (
        <p className="inline-error" role="alert">
          {actionError}
        </p>
      )}
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Patient</th>
              <th>Doctor</th>
              <th>Date &amp; time</th>
              <th>Status</th>
              {showActions && <th className="action-heading">Action</th>}
            </tr>
          </thead>
          <tbody>
            {appointments.map((appointment) => {
              const isPending = pendingId === appointment.id;
              const isRecent = recentAction?.appointment.id === appointment.id;
              return (
                <tr
                  className={isRecent ? "appointment-row-recent" : undefined}
                  key={appointment.id}
                >
                  <td>
                    <div className="patient-cell">
                      <span className="patient-avatar">
                        {(appointment.patient_name || "P")
                          .trim()
                          .charAt(0)
                          .toUpperCase()}
                      </span>
                      <span className="cell-stack">
                        <strong>
                          {appointment.patient_name || "Patient"}
                        </strong>
                        <small>{appointment.phone_number}</small>
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="doctor-cell">
                      {appointment.doctor.name}
                    </span>
                    <small className="table-subtext">
                      {appointment.doctor.speciality}
                    </small>
                  </td>
                  <td>
                    <span className="cell-stack">
                      <strong>{formatAppointmentDate(appointment)}</strong>
                      <small>{formatAppointmentTime(appointment)}</small>
                    </span>
                  </td>
                  <td>
                    <div className="appointment-status-cell">
                      <StatusBadge status={appointment.status} />
                      {isRecent && (
                        <span
                          className={`recent-appointment-label recent-appointment-${recentAction.type}`}
                        >
                          {recentAction.type === "booked"
                            ? "Just booked"
                            : "Just cancelled"}
                        </span>
                      )}
                    </div>
                  </td>
                  {showActions && (
                    <td className="action-cell">
                      {appointment.status === "booked" && (
                        isPending ? (
                          <span className="confirm-actions">
                            <button
                              className="text-button danger"
                              disabled={cancellingId === appointment.id}
                              onClick={() => onConfirmCancel(appointment)}
                              type="button"
                            >
                              {cancellingId === appointment.id
                                ? "Cancelling..."
                                : "Confirm"}
                            </button>
                            <button
                              className="text-button"
                              onClick={onKeepAppointment}
                              type="button"
                            >
                              Keep
                            </button>
                          </span>
                        ) : (
                          <button
                            className="text-button danger"
                            onClick={() => onCancel(appointment.id)}
                            type="button"
                          >
                            <Icon name="close" size={15} />
                            Cancel
                          </button>
                        )
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default AppointmentsTable;
