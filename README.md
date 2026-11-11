# UCLA Laundry Tracker

UCLA Hill laundry machines are often broken or have inconsistent settings. This app lets residents **report broken machines** and **see recent reports and machine status**, so everyone can avoid the bad ones.

**Current goal: the reporting system.** Students pick a room → pick a machine → report an issue → see recent reports.

## Stack

React + Vite (frontend) · Node.js/TypeScript on AWS Lambda · API Gateway · DynamoDB · S3 + CloudFront · deployed with AWS SAM

## Repo layout

| Folder | Owner | What goes there |
|---|---|---|
| `frontend/` | Member A | React + Vite web app |
| `backend/` | Member B | Lambda handlers + seed script |
| `data/` | Member B | Mock/seed data (rooms, machines, sample reports) |
| `infra/` | Member C | SAM template + config |
| `docs/` | B + C | `api.md` (B), `deployment.md` (C) |

## Task split

### How reporting works

A report is one sentence: *"I used **this machine** on **this setting** and it came out **this way**"*, or *"**this machine** didn't work: **symptoms**"*.
**Reports are buttons only for now, with no typing.** Every field is a choice from a fixed list, which keeps reports fast, easy to count, and free of spam or personal info.
Machine status (**Works / Caution / Broken / Unknown**, plus a short reason like "No heat") is **computed from recent reports**:
- Evidence fades with time, so a machine nobody reports on drifts back to Unknown.
- Only each device's latest report counts.
- The newest report gets extra weight, so "works now" beats an older "broken".

Each machine has a short code (e.g. `rw15`) so a QR sticker can open its page directly.

### Member A: frontend (`frontend/`)
- [ ] Initialize React/Vite
- [ ] Room list (grouped by hall)
- [ ] Room page: machine cards with status badge + reason + "last report 3h ago", summary line ("5 of 6 dryers working"), washer/dryer filter
- [ ] Machine page (`/m/:code`): status, recent reports, "Report" button; `?r=1` opens the report form directly (for QR stickers)
- [ ] **Report form, buttons only (no text box), ≤3 taps:** outcome ("Worked fine" / "Problem") → setting used or symptom buttons → submit
- [ ] If the machine is already flagged, lead with **"Still broken?" / "Works now"**
- [ ] Undo toast after submitting
- [ ] Anonymous device ID: random UUID in localStorage, sent as the `X-Device-Id` header on every request
- [ ] Loading / empty / error / submitting / success states
- [ ] Build on mock data from `data/`, then connect to the API through `VITE_API_BASE_URL`

**Done when:** you can scan-or-tap to a machine, report in 3 taps, and see its status update, on a phone against the deployed API.

### Member B: backend + data (`backend/`, `data/`, `docs/api.md`)
- [ ] **First:** API contract in `docs/api.md` (routes, request/response shapes, outcome/symptom lists, error format)
- [ ] Mock data in `data/`: real Hill rooms, machines with codes + labels matching the physical numbers, sample reports
- [ ] Endpoints:
  - `GET /rooms`
  - `GET /rooms/{roomId}/machines`: machines with status, reason, last report age, plus the room summary
  - `GET /machines/{code}`: machine, status, recent reports
  - `POST /machines/{code}/reports`: create a report and recompute the machine's status
  - `DELETE /reports/{id}`: undo (soft delete: set `undoneAt`, keep the row)
  - `GET /health`
- [ ] **Status function** (pure + unit-tested): time decay, latest-report-per-device, recency tiebreak. Recompute on each write and save the result on the machine. When reading, show Unknown if the last report is too old.
- [ ] Validation: only accept values from the fixed outcome / setting / symptom lists. No free-text fields for now. Server sets ID, `createdAt`, and `deviceHash` (hash of `X-Device-Id` + a secret).
- [ ] Rate limits: 1 report per device per machine per 3 min, 30 per device per day, 300 per IP per day (IP from API Gateway). Also a honeypot field.
- [ ] Seed script that loads `data/` into DynamoDB
- [ ] Test valid and invalid requests; add example requests and responses to `docs/api.md`

**Done when:** all endpoints work on the deployed API, status changes correctly as reports come in, and the data is seeded.

### Member C: AWS + integration (`infra/`)
- [x] Initialize repo structure
- [ ] SAM template:
  - DynamoDB: rooms, machines (lookup by room and by code), reports (by machine + time, by device + time), and a rate-limit table with TTL
  - API Gateway with throttling
  - Lambdas
  - S3 + CloudFront
- [ ] Store the device-hash secret in SSM Parameter Store or Secrets Manager; pass it to the Lambdas
- [ ] Deploy the dev stack early and share the API URL
- [ ] Configure IAM (least privilege), CORS (allow the `X-Device-Id` header), logs
- [ ] Deploy the frontend (build → S3 sync → CloudFront invalidation)
- [ ] Write `docs/deployment.md`
- [ ] Run the full browser demo

**Done when:** there's a public HTTPS URL and the deploy steps are repeatable.

### Later phases (not now)
"Same here" votes on reports, flagging, admin (hide report, mark fixed, out of order), the "I started it" timer, push alerts, busy hours, and AI setting suggestions.

## Order of work

1. B shares the API contract + mock data (day 1)
2. A builds the UI on mock data · B builds endpoints + status function · C sets up AWS
3. C deploys the dev API → A connects to it
4. C deploys the frontend → full demo

## How we work

- Only edit the folders you own.
- Work on a branch, open a PR, and get one review before merging.
- If the API contract changes, tell the team first.
