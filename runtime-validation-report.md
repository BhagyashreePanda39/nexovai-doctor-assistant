# Runtime Validation Report

**Generated**: 2026-11-24T23:25:00+05:30
**Target**: `E:\medivoice\nexovai-doctor-assistant`

## Summary

| Step | Status | Exit Code | Details |
|---|---|---:|---|
| Startup and live API | PASS | 0 | FastAPI `/health`, doctors, availability, and appointments returned 200. Vite dashboard loaded real API data. CORS allows `http://localhost:5174`. |
| Backend tests | PASS | 0 | 23 tests across six unittest files, including FastAPI route integration and isolated SQLite service/tool scenarios. |
| Frontend tests/build | PASS | 0 | Vitest: 5 passed. Vite production build succeeded; a chunk-size advisory remains. |
| Standalone runtime validation | PASS | 0 | Five assertions passed: frontend build, tests, frontend HTTP 200, doctors API HTTP 200, and appointments API HTTP 200. |
| Browser voice E2E | PARTIAL | — | Dashboard rendered four doctors and 36 slots. A prior connection attempt displayed the API's 503 missing-credentials message. Successful live audio/provider behavior remains unverified. |

**Overall**: NOT READY FOR SIGN-OFF — backend and frontend automated checks pass, and the nine appointment scenarios pass at tool/service level. Successful live Gemini/STT/TTS conversation testing is blocked by missing local provider credentials.

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
  browser-tier: PRIMARY(Playwright) — dashboard opened and rendered live API data
startup: PASS — FastAPI `/health`, doctors, availability, and appointments returned 200; Vite dashboard loaded
integration: PASS — exit_code: 0; backend passed 23 tests; frontend passed 5 tests
build: PASS — `npm run build`; Vite emitted a 733.92 kB main bundle advisory
runtime-plan: PASS — standalone mode, 5 assertions passed, 0 failed
dependencies: PASS — `pip check` found no broken requirements; `npm ls --depth=0` resolved declared packages
security-config: PASS — no local `.env` files or likely hardcoded credentials detected; examples use placeholders
sqlite: PASS — integrity check `ok`; zero foreign-key violations; 4 doctors, 36 slots, 0 appointments
cors: PASS — `http://localhost:5174` is allowed
e2e: PARTIAL — actual voice setup remains blocked by absent local provider credentials; a prior browser attempt displayed the API's 503 configuration detail
overall: NOT READY FOR SIGN-OFF — live ElevenLabs STT/TTS and Gemini behavior are not verified
```

Read-only live API probes returned 200 for `/health`, `/api/doctors`
(4 doctors), `/api/availability` (36 slots), and `/api/appointments` (0
appointments). The live dashboard displayed the same counts. SQLite
`PRAGMA integrity_check` returned `ok`; `PRAGMA foreign_key_check` found no
violations. Tool/API tests use isolated in-memory databases and do not modify
`backend/appointments.db`.

No root, backend, or frontend `.env` file is present. The browser connection
attempt returned HTTP 503 because `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID`, and `GOOGLE_API_KEY` are not configured. No secret values
were read or displayed.

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
| 3 | Blocker to live voice verification | Local ElevenLabs and Google credentials are not configured. | Unresolved environment prerequisite; add credentials locally, then rerun browser voice scenarios. |
| 4 | Medium | Dashboard/API have no authentication; appointment responses expose patient phone numbers. | Demo-only; use mock data and do not expose publicly. |
| 5 | Low | Production Vite build succeeds but warns that the generated JavaScript chunk exceeds 500 kB (733.92 kB before gzip). | Not changed; not a functional blocker for the assignment demo. |
| 6 | Review item | Earlier `npm audit` reported three dependency advisories (one moderate, two critical). | Not upgraded as part of this verification; review/resolve before public deployment. |
