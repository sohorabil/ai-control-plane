variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "eacp"
}

variable "vpc_cidr" {
  default = "10.20.0.0/16"
}

variable "eks_node_instance_type" {
  # Cheapest reasonable instance type — matches the project's cost-conscious
  # rule. Sized for a demo cluster, not production load.
  default = "t3.medium"
}

variable "rds_instance_class" {
  # Smallest Postgres-compatible instance; matches "cheapest tier" rule.
  default = "db.t4g.micro"
}
