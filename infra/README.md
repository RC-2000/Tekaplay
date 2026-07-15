# Infrastructure

Current targets (zero-ops, low-cost tier):

| Concern        | Provider              | Swap-to (AWS)     |
|----------------|-----------------------|-------------------|
| Postgres       | Neon                  | RDS               |
| Redis          | Upstash               | ElastiCache       |
| Object storage | Cloudflare R2         | S3                |
| Compute        | Docker (any host)     | ECS Fargate       |
| CDN / DNS      | Cloudflare            | CloudFront / ALB  |
| Queues         | Redis (Celery broker) | SQS               |
| Observability  | Sentry + Grafana Cloud| CloudWatch + X-Ray|

Every provider above is consumed through a neutral interface (SQLAlchemy URL,
Redis URL, S3-compatible client, Celery broker URL). Migration to AWS is a
configuration change plus IaC — no application code changes. Terraform modules
land here in the infrastructure slice.
