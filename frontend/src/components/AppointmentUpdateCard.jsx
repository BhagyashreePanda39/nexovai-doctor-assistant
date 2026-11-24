import Icon from "./Icon.jsx";

function AppointmentUpdateCard({ update, onDismiss }) {
  const { appointment, type } = update;
  const appointmentDate = new Date(
    `${appointment.appointment_date}T${appointment.appointment_time}`,
  );
  const formattedDate = new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(appointmentDate);
  const formattedTime = new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
  }).format(appointmentDate);
  const isBooking = type === "booked";

  return (
    <aside
      aria-live="polite"
      className={`appointment-update-card appointment-update-${type}`}
      role="status"
    >
      <span className="appointment-update-icon">
        <Icon name={isBooking ? "check" : "calendar"} size={19} />
      </span>
      <div className="appointment-update-copy">
        <strong>
          Appointment {isBooking ? "booked" : "cancelled"}
        </strong>
        <span>
          {appointment.doctor.name} · {formattedDate} at {formattedTime}
        </span>
      </div>
      <button
        aria-label="Dismiss appointment update"
        className="appointment-update-dismiss"
        onClick={onDismiss}
        type="button"
      >
        <Icon name="close" size={17} />
      </button>
    </aside>
  );
}

export default AppointmentUpdateCard;
