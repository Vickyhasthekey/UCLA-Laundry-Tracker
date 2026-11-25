# infra/ (Member C)

AWS SAM template + config:
- DynamoDB tables, including a rate-limit table with TTL
- API Gateway with throttling
- Lambda
- S3 + CloudFront
- The device-hash secret

Deployment steps go in `../docs/deployment.md`.

Start with [deployment instructions](../docs/deployment.md) and
[verified deployment status](../docs/deployment-status.md).
`demo/` is an isolated Member C integration fixture, not the final A/B application.
It is the default deployed source until their agreed code and API contract arrive.
