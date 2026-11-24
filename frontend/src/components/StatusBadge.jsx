function StatusBadge({ status }) {
  const isCancelled = status === "cancelled";
  const isBooked = status === "booked" || status === true;
  const label = isCancelled ? "Cancelled" : isBooked ? "Booked" : "Available";
  const tone = isCancelled ? "cancelled" : isBooked ? "booked" : "available";
  return (
    <span className={`status-badge ${tone}`}>
      <span className="status-badge-dot" />
      {label}
    </span>
  );
}

export default StatusBadge;
