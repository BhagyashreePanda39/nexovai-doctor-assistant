import AppointmentsTable from "../components/AppointmentsTable.jsx";

function AppointmentsPage({
  appointments,
  loading,
  pendingId,
  cancellingId,
  actionError,
  recentAction,
  onCancel,
  onConfirmCancel,
  onKeepAppointment,
}) {
  const activeCount = appointments.filter(
    (appointment) => appointment.status === "booked",
  ).length;

  return (
    <div className="page-content">
      <section className="page-intro-row">
        <div>
          <span className="section-eyebrow">PATIENT SCHEDULE</span>
          <h2>Appointments</h2>
          <p>Bookings and cancellations recorded by the appointment desk.</p>
        </div>
        {!loading && (
          <div className="active-count">
            <span className="active-count-dot" />
            <strong>{activeCount}</strong>
            <span>active</span>
          </div>
        )}
      </section>

      <section className="surface-card appointment-list-card">
        <div className="card-heading">
          <div>
            <span className="section-eyebrow">ALL RECORDS</span>
            <h3>Appointment history</h3>
          </div>
          {!loading && (
            <span className="table-record-count">
              {appointments.length} records
            </span>
          )}
        </div>
        <AppointmentsTable
          actionError={actionError}
          appointments={appointments}
          cancellingId={cancellingId}
          loading={loading}
          onCancel={onCancel}
          onConfirmCancel={onConfirmCancel}
          onKeepAppointment={onKeepAppointment}
          pendingId={pendingId}
          recentAction={recentAction}
          showActions
        />
      </section>
    </div>
  );
}

export default AppointmentsPage;
