# Runtime Validation Report

**Generated**: 2026-11-25T00:52:00+05:30
**Target**: `E:\medivoice\nexovai-doctor-assistant`

## Summary

| Step | Status | Exit Code | Details |
|---|---|---:|---|
| Startup and live API | PASS | 0 | FastAPI `/health`, doctors, availability, and appointments returned 200. Vite dashboard loaded real API data. CORS allows `http://localhost:5174`. |
| Backend tests | PASS | 0 | 23 tests across six unittest files, including FastAPI route integration and isolated SQLite service/tool scenarios. |
| Frontend tests/build | PASS | 0 | Vitest: 5 passed. Vite production build succeeded; a chunk-size advisory remains. |
| Standalone runtime validation | PASS | 0 | Five assertions passed: frontend build, tests, frontend HTTP 200, doctors API HTTP 200, and appointments API HTTP 200. |
| Browser voice E2E | FAIL / PARTIAL | — | WebRTC connected and Gemini ran. The browser emitted one transcript, but ElevenLabs rejected the configured voice ID and produced no audio. Controlled STT accuracy, TTS playback, and voice booking remain unverified. |

**Overall**: NOT READY FOR SIGN-OFF — backend and frontend checks pass, and the nine appointment scenarios pass at tool/service level. The live browser call connected, but the voice ID must be corrected before an end-to-end voice conversation can pass.

## Scenario Checklist

| # | Scenario | Result | Evidence |
|---:|---|---|---|
| 1 | Successful cardiology booking, spoken phone, phone readback, slot choice, separate booking confirmation, SQLite persistence | PASS* | `test_successful_booking_persists_after_both_confirmations` |
| 2 | Find existing appointments, select one, confirm cancellation, release only the selected slot | PASS* | `test_successful_cancellation_finds_and_releases_owned_booking` |
| 3 | Invalid phone blocks booking and cancellation with a clear validation message | PASS | `test_invalid_phone_blocks_booking`, `test_invalid_phone_blocks_cancellation` |
| 4 | No available slots returns an empty result without inventing options | PASS | `test_no_available_slots_are_reported_without_invention` |
| 5 | Invalid doctor is distinguished from an unavailable slot | PASS | `test_invalid_doctor_is_reported_for_search_and_booking` |
| 6 | Already-booked slot is rejected and only real alternatives are returned | PASS | `test_already_booked_slot_returns_an_available_alternative`, `test_slot_that_becomes_unavailable_returns_real_alternatives` |
| 7 | No active appointment for the confirmed phone is reported | PASS | `test_missing_appointment_is_reported_after_phone_confirmation` |
| 8 | Another caller's appointment cannot be cancelled or disclosed | PASS | `test_cannot_cancel_appointment_owned_by_another_phone`, `test_cancellation_does_not_expose_another_phone_appointments` |
| 9 | Declining phone, booking, or cancellation confirmation does not mutate data | PASS | `test_declining_phone_readback_prevents_booking`, `test_user_change_of_mind_does_not_book`, `test_declining_cancellation_preserves_booking` |

`*` PASS at tool/service/SQLite integration level using simulated transcript
messages. These are not claims of live Gemini interpretation or microphone
testing.

## Environment and Evidence

```text
environment:
  docker: UNAVAILABLE — docker info reported the daemon was not responding
  node: AVAILABLE — v22.17.1
  playwright: AVAILABLE — shared VS Code Playwright browser used for browser validation
  infra-tier: FALLBACK(embedded/in-memory) — SQLite is the application's database; Docker is unavailable
  browser-tier: PRIMARY(Playwright) — dashboard opened; call reached Connected before TTS failure
startup: PASS — FastAPI `/health`, doctors, availability, and appointments returned 200; Vite dashboard loaded
integration: PASS — exit_code: 0; backend passed 23 tests; frontend passed 5 tests
build: PASS — `npm run build`; Vite emitted a 733.92 kB main bundle advisory
runtime-plan: PASS — standalone mode, 5 assertions passed, 0 failed
dependencies: PASS — `pip check` found no broken requirements; `npm ls --depth=0` resolved declared packages
security-config: PASS — root `.env` and `backend/.env` are ignored by Git; no secret values were printed
sqlite: PASS — integrity check `ok`; zero foreign-key violations; 4 doctors, 36 slots, 0 appointments
cors: PASS — `http://localhost:5174` is allowed
configuration: PARTIAL — root `.env` exists and has variables required by this code; `backend/.env` is absent; code expects `GOOGLE_API_KEY`, not `GEMINI_API_KEY`
e2e: FAIL/PARTIAL — WebRTC connected, Google LLM request ran, one transcript emitted, ElevenLabs rejected the configured voice ID; no TTS audio
overall: NOT READY FOR SIGN-OFF — the assistant did not speak; user-spoken STT and full conversation are not verified
```

Read-only live API probes returned 200 for `/health`, `/api/doctors`
(4 doctors), `/api/availability` (36 slots), and `/api/appointments` (0
appointments). The live dashboard displayed the same counts. SQLite
`PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` found no
violations. Tool/API tests use isolated in-memory databases and do not modify
`backend/appointments.db`.

The project-root `.env` exists and the backend loaded its expected settings;
`backend/.env` does not exist. `backend/app/main.py` loads the root `.env`, and
`backend/app/voice/pipeline.py` expects `GOOGLE_API_KEY` (not
`GEMINI_API_KEY`). No secret values were read or displayed. The latest browser
attempt reached Connected and Gemini processed the greeting, but the
ElevenLabs service rejected the configured voice ID as unavailable, so TTS
produced no audio. One transcript was emitted, but no controlled phrase was
used to verify STT accuracy.

## Fixes Made

- Invalid phone inputs now produce the phone-format validation message rather
  than a generic Pydantic length error.
- Unknown doctor IDs/names now produce an explicit not-found result.
- A clear “no” or “I changed my mind” clears the pending operation and does
  not repeat the confirmation request or change the database.
- The frontend no longer claims appointment changes are unsupported.
- The browser uses Pipecat's current `webrtcRequestParams` option and displays
  the server's response detail instead of `[object Response]`.

## Issues Found

| # | Severity | Description | Status |
|---:|---|---|---|
| 1 | High | Phone validation was generic for short numbers; invalid doctor lookup looked like a slot conflict; declines left confusing pending prompts. | Fixed and covered by tests. |
| 2 | Medium | Frontend text said appointments could not be changed, and connection errors hid backend detail. | Fixed; browser shows actionable missing-key message. |
| 3 | Blocker to live voice verification | ElevenLabs rejected the configured voice ID as nonexistent/unavailable; no audio was returned. | Select a valid voice available in the same ElevenLabs account/workspace as the API key, update root `.env`, restart FastAPI, and retry. |
| 4 | Medium | Dashboard/API have no authentication; appointment responses expose patient phone numbers. | Demo-only; use mock data and do not expose publicly. |
| 5 | Low | Production Vite build succeeds but warns that the generated JavaScript chunk exceeds 500 kB (733.92 kB before gzip). | Not changed; not a functional blocker for the assignment demo. |
| 6 | Review item | Earlier `npm audit` reported three dependency advisories (one moderate, two critical). | Not upgraded as part of this verification; review/resolve before public deployment. |
