# Terraform

## aws/

Describes the production AWS infrastructure (VPC, ECR, EKS cluster + node
group, IAM roles, RDS Postgres, Secrets Manager) that Part 9/13 deploy to.
**Applied once, then destroyed, in Part 9** (2026-09-28) — `terraform apply`
was run with explicit confirmation, verified end-to-end on real EKS (see
PROGRESS.md Part 9 for details), then `terraform destroy` immediately after,
per the project's cost rule ("stop billed resources right after testing,
same session"). Currently back to **zero resources / $0 running cost** —
state is empty. Running `terraform apply` here again creates real, billed
AWS resources (EKS + RDS + running EC2 nodes are not free) and should only
happen with explicit confirmation.

**Lesson learned the hard way**: only ever run `terraform destroy` to tear
this down — an `apply` run to "fix" a small out-of-band issue (like an ECR
repo needing a manual force-delete first) can silently recreate everything
else in the plan instead. If something needs manual cleanup outside
Terraform, do it via the AWS CLI directly and leave this folder's Terraform
commands to `plan`/`destroy` only until ready for a real, intentional apply.

To (re-)generate the plan without applying anything:
```
cd terraform/aws
terraform init
terraform plan
```

To apply for real (costs money — see PROGRESS.md Part 9 for the cost
breakdown from the last run):
```
cd terraform/aws
terraform apply
# ... do the work, verify ...
terraform destroy   # immediately after, same session
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
