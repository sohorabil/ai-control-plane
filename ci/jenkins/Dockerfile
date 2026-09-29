# Part 10 — Jenkins with the tools our pipeline actually needs baked in.
# The stock jenkins/jenkins:lts image only has git; everything else here
# (docker CLI, kubectl, helm, trivy, terraform, python3) is what the
# Jenkinsfile's 7 stages call directly.
FROM jenkins/jenkins:lts

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg lsb-release python3 python3-venv unzip jq \
    && rm -rf /var/lib/apt/lists/*

# Docker CLI (talks to the host's Docker daemon via the mounted socket —
# see docker-compose.yml's /var/run/docker.sock mount)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# kubectl — talks to the kind cluster via the host's kubeconfig, mounted in
RUN curl -fsSLo /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/$(dpkg --print-architecture)/kubectl" \
    && chmod +x /usr/local/bin/kubectl

# Helm
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# kind CLI — needed for `kind load docker-image` in the staging-deploy stage.
# Pinned to match the host's kind version (v0.33.0): an older kind (v0.24.0,
# tried first) failed with "failed to detect containerd snapshotter" against
# this host's node, which runs containerd v2.3.4 — a newer major version
# kind v0.24.0 predates support for.
RUN curl -fsSLo /usr/local/bin/kind \
        "https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-$(dpkg --print-architecture)" \
    && chmod +x /usr/local/bin/kind

# Trivy
RUN curl -fsSL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
        | sh -s -- -b /usr/local/bin

# Terraform
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_$(dpkg --print-architecture | sed 's/amd64/amd64/;s/arm64/arm64/').zip \
        -o /tmp/terraform.zip \
    && unzip -o /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip

# Docker Desktop's mounted socket is owned by GID 0 on this host; add jenkins
# to that group so it can actually use the Docker CLI installed above.
RUN usermod -aG root jenkins

USER jenkins
