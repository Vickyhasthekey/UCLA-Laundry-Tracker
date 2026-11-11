# infra/ (Member C)

AWS SAM template + config:
- DynamoDB tables, including a rate-limit table with TTL
- API Gateway with throttling
- Lambda
- S3 + CloudFront
- The device-hash secret

Deployment steps go in `../docs/deployment.md`.
