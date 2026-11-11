# backend/ (Member B)

Lambda handlers (Node.js/TypeScript):
- Endpoints: rooms, room machines, machine by code, create report, undo report, health
- The status function: computes Works / Caution / Broken / Unknown from recent reports
- Rate limiting
- The seed script that loads `../data/` into DynamoDB

The API contract lives in `../docs/api.md`. The full task list is in the root README.
