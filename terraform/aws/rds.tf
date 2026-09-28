resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnets"
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow Postgres access only from the EKS cluster's security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.main.vpc_config[0].cluster_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "random_password" "rds_password" {
  length  = 24
  special = false # avoid characters that need URL-encoding in DATABASE_URL
}

resource "aws_secretsmanager_secret" "rds_password" {
  name = "${var.project_name}/rds-password"
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id     = aws_secretsmanager_secret.rds_password.id
  secret_string = random_password.rds_password.result
}

resource "aws_db_instance" "main" {
  identifier             = "${var.project_name}-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.rds_instance_class
  allocated_storage      = 20 # smallest billable increment
  db_name                = "eacp"
  username               = "eacp"
  password               = random_password.rds_password.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = true # acceptable for a demo/learning DB, not production
  publicly_accessible    = false

  tags = {
    Name = "${var.project_name}-postgres"
  }
}
