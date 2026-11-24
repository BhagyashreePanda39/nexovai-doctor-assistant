import { afterEach, describe, expect, it, vi } from "vitest";

import {
  cancelAppointment,
  findRecentAppointmentChange,
  getDashboardData,
} from "./api.js";

function jsonResponse(body, status = 200) {
  return {
    json: async () => body,
    ok: status >= 200 && status < 300,
    status,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("dashboard API service", () => {
  it("combines available slots with active bookings but not cancelled appointments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(jsonResponse([{ id: 1, name: "Dr. Rao" }]))
        .mockResolvedValueOnce(
          jsonResponse([
            {
              id: 14,
              slot_id: 2,
              doctor_id: 1,
              appointment_date: "2026-11-25",
              appointment_time: "10:00:00",
              status: "booked",
              doctor: { id: 1, name: "Dr. Rao", speciality: "Cardiology" },
            },
            {
              id: 15,
              slot_id: 3,
              doctor_id: 1,
              appointment_date: "2026-11-25",
              appointment_time: "11:00:00",
              status: "cancelled",
              doctor: { id: 1, name: "Dr. Rao", speciality: "Cardiology" },
            },
          ]),
        )
        .mockResolvedValueOnce(
          jsonResponse([
            {
              id: 1,
              doctor_id: 1,
              appointment_date: "2026-11-25",
              appointment_time: "09:00:00",
              is_booked: false,
              doctor: { id: 1, name: "Dr. Rao", speciality: "Cardiology" },
            },
            {
              id: 3,
              doctor_id: 1,
              appointment_date: "2026-11-25",
              appointment_time: "11:00:00",
              is_booked: false,
              doctor: { id: 1, name: "Dr. Rao", speciality: "Cardiology" },
            },
          ]),
        ),
    );

    const data = await getDashboardData();

    expect(data.slots.map((slot) => [slot.id, slot.is_booked])).toEqual([
      [1, false],
      [2, true],
      [3, false],
    ]);
    expect(data.appointments[0].status).toBe("booked");
  });

  it("sends the appointment phone number and id to the cancellation endpoint", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({ message: "Cancelled" }));
    vi.stubGlobal("fetch", fetch);

    await cancelAppointment("+15551234567", 42);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/appointments\/cancel$/),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          phone_number: "+15551234567",
          appointment_id: 42,
        }),
      }),
    );
  });

  it("surfaces API errors instead of treating cancellation as successful", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: "Appointment already cancelled." }, 409),
      ),
    );

    await expect(cancelAppointment("9876543210", 42)).rejects.toThrow(
      "Appointment already cancelled.",
    );
  });

  it("finds a newly booked appointment after refreshing dashboard data", () => {
    const appointment = {
      id: 43,
      status: "booked",
      doctor: { name: "Dr. Rao" },
    };

    expect(findRecentAppointmentChange([], [appointment])).toEqual({
      type: "booked",
      appointment,
    });
  });

  it("finds a booking cancellation and ignores unchanged appointments", () => {
    const previousAppointment = { id: 42, status: "booked" };
    const cancelledAppointment = { id: 42, status: "cancelled" };

    expect(
      findRecentAppointmentChange(
        [previousAppointment],
        [cancelledAppointment],
      ),
    ).toEqual({ type: "cancelled", appointment: cancelledAppointment });
    expect(
      findRecentAppointmentChange(
        [previousAppointment],
        [{ ...previousAppointment }],
      ),
    ).toBeNull();
  });
});
