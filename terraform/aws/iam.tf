# EKS control plane role — least privilege: only the AWS-managed policy EKS
# itself requires to run the cluster control plane.
resource "aws_iam_role" "eks_cluster" {
  name = "${var.project_name}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  role       = aws_iam_role.eks_cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# EKS node group role — only what worker nodes need to join the cluster and
# pull images, nothing else.
resource "aws_iam_role" "eks_nodes" {
  name = "${var.project_name}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_worker_node_policy" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "ecr_read_only" {
  role       = aws_iam_role.eks_nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# EKS Pod Identity association for the gateway workload — this is the AWS
# role the gateway pods actually run as, already created manually in Part 5
# (eacp-gateway-role) for the Vertex WIF trust chain. Referenced here, not
# recreated, so Part 5's WIF trust relationship stays valid.
data "aws_iam_role" "eacp_gateway" {
  name = "eacp-gateway-role"
}

resource "aws_iam_role_policy_attachment" "gateway_secrets_read" {
  role       = data.aws_iam_role.eacp_gateway.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
  # NOTE: SecretsManagerReadWrite is broader than ideal — a tighter policy
  # scoped to just this project's secret ARNs should replace this before
  # any real production use. Flagged here rather than silently accepted.
}
