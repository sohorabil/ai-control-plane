resource "aws_eks_cluster" "main" {
  name     = "${var.project_name}-cluster"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.30"

  vpc_config {
    subnet_ids              = aws_subnet.public[*].id
    endpoint_public_access   = true
    endpoint_private_access  = false
  }

  depends_on = [aws_iam_role_policy_attachment.eks_cluster_policy]
}

# EKS's default node launch template caps the IMDS hop limit at 1, which
# blocks traffic from inside a pod's network namespace (2 hops away) from
# reaching the instance metadata service. That breaks Vertex's Workload
# Identity Federation, which reads AWS role credentials from IMDS to build
# its cross-cloud token. Caught during Part 9 verification ("Unable to
# retrieve AWS role name"); fixed by giving the node group its own launch
# template with hop_limit = 2, the standard fix for EKS + IMDS-from-pod.
resource "aws_launch_template" "eks_nodes" {
  name_prefix = "${var.project_name}-nodes-"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.project_name}-node"
    }
  }
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.project_name}-nodes"
  node_role_arn   = aws_iam_role.eks_nodes.arn
  subnet_ids      = aws_subnet.public[*].id

  scaling_config {
    desired_size = 2
    max_size     = 2
    min_size     = 1
  }

  instance_types = [var.eks_node_instance_type]
  ami_type       = "AL2023_x86_64_STANDARD"

  launch_template {
    id      = aws_launch_template.eks_nodes.id
    version = aws_launch_template.eks_nodes.latest_version
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.ecr_read_only,
  ]
}

resource "aws_eks_pod_identity_association" "gateway" {
  cluster_name    = aws_eks_cluster.main.name
  namespace       = "default"
  service_account = "eacp-gateway"
  role_arn        = data.aws_iam_role.eacp_gateway.arn
}

# The association above only creates the IAM-role-to-service-account mapping.
# Pods still can't fetch credentials from it until the Pod Identity Agent
# DaemonSet is actually running in-cluster to serve the
# 169.254.170.23/v1/credentials endpoint each pod calls. Missing this addon
# causes every boto3 client() call to hang until CredentialRetrievalError
# (connect timeout) — caught during Part 13's real-AWS deploy when the
# gateway crash-looped on import because bedrock.py builds its client eagerly
# at module load time.
resource "aws_eks_addon" "pod_identity_agent" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "eks-pod-identity-agent"
}
