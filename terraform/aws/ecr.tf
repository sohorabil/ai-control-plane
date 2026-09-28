# Container registry for the gateway image (built in Part 8, pushed here in
# Part 9 when we actually deploy to EKS).

resource "aws_ecr_repository" "gateway" {
  name                 = "${var.project_name}-gateway"
  image_tag_mutability = "IMMUTABLE" # prevents accidentally overwriting a deployed tag

  image_scanning_configuration {
    scan_on_push = true # Trivy-equivalent basic scanning; Part 8's Trivy runs in CI too
  }
}
