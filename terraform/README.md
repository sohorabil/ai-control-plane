# Terraform

## aws/

Describes the production AWS infrastructure (VPC, ECR, EKS cluster + node
group, IAM roles, RDS Postgres, Secrets Manager) that Part 9/13 will actually
deploy to. **Plan-only for now** — `terraform plan` has been run and
validated (24 resources, 0 errors), but nothing has been applied. Running
`terraform apply` here creates real, billed AWS resources (EKS + RDS + a
running EC2 node are not free) and should only happen with explicit
confirmation, in Part 9.

To (re-)generate the plan without applying anything:
```
cd terraform/aws
terraform init
terraform plan
```

## gcp/

Describes GCP resources. Unlike the AWS folder, the BigQuery datasets here
**have been applied** (`eacp_usage_analytics`, `eacp_eval_history`) since
they're within BigQuery's free tier (1TB queries/mo, 10GB storage/mo) —
matches the brief's "apply only the free GCP pieces" instruction. The
Workload Identity Federation pool/provider/service account from Part 5 were
created manually via `gcloud` CLI commands (not Terraform) at the time —
not reflected here yet; a future pass could bring them under Terraform
management for consistency.
