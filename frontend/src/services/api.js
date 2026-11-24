export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch (error) {
    throw new Error(
      `Could not reach the API at ${API_BASE_URL}. Check that the backend is running and try again.`,
      { cause: error },
    );
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).filter(Boolean).join(" ")
      : detail;
    throw new Error(
      typeof message === "string"
        ? message
        : `The API request failed with status ${response.status}.`,
    );
  }
  return body;
}

export async function getDashboardData() {
  const [doctors, appointments, availableSlots] = await Promise.all([
    request("/api/doctors"),
    request("/api/appointments"),
    request("/api/availability"),
  ]);

  const combinedSlots = new Map(
    availableSlots.map((slot) => [slot.id, slot]),
  );
  for (const appointment of appointments) {
    if (appointment.status === "booked") {
      combinedSlots.set(appointment.slot_id, {
        ...appointment,
        id: appointment.slot_id,
        appointment_id: appointment.id,
        is_booked: true,
      });
    }
  }

  return {
    doctors,
    appointments,
    slots: [...combinedSlots.values()].sort((left, right) => {
      const byDate = left.appointment_date.localeCompare(
        right.appointment_date,
      );
      if (byDate !== 0) {
        return byDate;
      }
      const byTime = left.appointment_time.localeCompare(
        right.appointment_time,
      );
      return byTime || left.doctor_id - right.doctor_id;
    }),
  };
}

export function findRecentAppointmentChange(
  previousAppointments,
  nextAppointments,
) {
  const previousById = new Map(
    previousAppointments.map((appointment) => [appointment.id, appointment]),
  );
  const changedAppointment = nextAppointments
    .filter((appointment) => {
      const previous = previousById.get(appointment.id);
      return (
        (appointment.status === "booked" &&
          (!previous || previous.status !== "booked")) ||
        (appointment.status === "cancelled" && previous?.status === "booked")
      );
    })
    .sort((left, right) => right.id - left.id)[0];

  if (!changedAppointment) {
    return null;
  }

  return {
    type: changedAppointment.status === "booked" ? "booked" : "cancelled",
    appointment: changedAppointment,
  };
}

export function cancelAppointment(phoneNumber, appointmentId) {
  return request("/api/appointments/cancel", {
    method: "POST",
    body: JSON.stringify({
      phone_number: phoneNumber,
      appointment_id: appointmentId,
    }),
  });
}
