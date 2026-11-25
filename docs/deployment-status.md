# Verified Member C deployment

Verified November 24, 2026 (America/Los_Angeles).

- Website: https://d3bvrtwy8zl95x.cloudfront.net
- API: https://fq3o8fahel.execute-api.us-east-2.amazonaws.com
- Health: https://fq3o8fahel.execute-api.us-east-2.amazonaws.com/health
- Stack: `laundry-dev`; Region: `us-east-2`; CLI profile: `laundry-dev`.
- GitHub branch: `Vicky`. No direct merge to main.

## Results

- SAM lint passed, build succeeded, CloudFormation creation and CORS update succeeded.
- Four project-specific cfn-guard rules passed: private encrypted bucket,
  data retention, rate-table TTL, and secret references rather than plaintext.
  These limited rules do not constitute a complete compliance certification.
- Six Moto tests passed: persistence/privacy, atomic rate rejection, expiry before
  physical TTL deletion, daily device quota, IP quota/day rollover, invalid input.
- Sixteen live HTTP checks passed: health, rooms, machines, invalid/missing device,
  invalid choice, honeypot, free text, unknown machine, successful save, duplicate
  rejection, immediate readback, identifier privacy, allowed/denied CORS origins,
  public HTTPS website, and denied direct S3 access.
- Live DynamoDB TTL status is ENABLED on `expiresAt`.
- Live Lambda log streams exist; API and Lambda logs retain seven days.
- Browser at 390 x 844: submitted NOT_DRYING on demo dryer, reloaded and saw the
  report, then verified the duplicate report received the rate-limit message.
  No horizontal overflow or uncaught JavaScript errors. The intentionally rejected
  POST produces an expected 429 network entry in the browser console.
- A fresh independent browser context also saw the stored report.

## Checklist boundary

Infrastructure, secret storage, demo deployment, IAM/CORS/logging, demo frontend
publish, repeatable steps, and the infrastructure browser demo are implemented.
The public site deliberately says it is a Member C test fixture using demo data.

A's React build and B's final backend/contract are not present in GitHub main at
the time of verification. Their full code-based machine route, status algorithm,
undo, and outcome/setting choices are not implemented by this fixture. Final
product integration is pending that handoff. See deployment.md for swap steps.

The older root frontend/backend/data/scripts remain local historical scaffolding;
they are not part of this branch's deployment or this Member C commit.

## Operations

The project was on the active FREE plan when checked; resources consume credits
and may accrue charges. Inspect spend in AWS Settings > Billing. No durable
custom CloudTrail trail was found; reduced auditability is documented.

Keep this development stack for team integration. Tables, website bucket and
secret have retention policies; stack deletion alone does not remove all stored
data or all charges. Cleanup requires an explicit decision and a retained-resource
inventory. No resources were deleted during this work.
