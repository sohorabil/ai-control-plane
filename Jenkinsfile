// Part 10 — CI/CD with AI gates.
//
// ONE pipeline, run once per push/PR, made of 7 ordered stages. If any stage
// fails, the pipeline stops there — later stages never run, and nothing gets
// promoted. See architecture.md for how these stages fit into the overall
// system, and PROGRESS.md (Part 10) for the reasoning behind each choice.
//
// Every stage here is free/local (pytest, ruff, trivy, terraform validate,
// the mock-provider eval smoke test, kind) — no AWS/GCP resources are
// touched, matching this part's $0 cost scope.

pipeline {
    agent any

    environment {
        // Fake-but-valid values so gateway modules can be imported (e.g.
        // app/db.py calls create_engine() at import time) without needing a
        // live Postgres/Redis inside the Jenkins container for stages that
        // never actually query either.
        DATABASE_URL = "postgresql+psycopg://fake:fake@localhost/fake"
        REDIS_URL    = "redis://localhost:6379/0"
    }

    stages {
        stage('1. Lint + Test') {
            steps {
                dir('gateway') {
                    sh '''
                        python3 -m venv .ci-venv
                        .ci-venv/bin/pip install -q -r requirements-dev.txt
                        .ci-venv/bin/ruff check app/
                        .ci-venv/bin/python -m pytest tests/ -v
                    '''
                }
            }
        }

        stage('2. Security Scan (Trivy)') {
            steps {
                dir('gateway') {
                    sh '''
                        docker build -t eacp-gateway:ci-scan .
                        trivy image --exit-code 0 --severity HIGH,CRITICAL eacp-gateway:ci-scan
                    '''
                }
            }
        }

        stage('3. Validate Infra (Terraform)') {
            steps {
                sh '''
                    cd terraform/aws && terraform init -backend=false -input=false && terraform validate
                    cd ../gcp && terraform init -backend=false -input=false && terraform validate
                '''
            }
        }

        stage('4. AI Breakage Check (eval gate)') {
            steps {
                sh '''
                    cd gateway && ../gateway/.ci-venv/bin/pip install -q -r requirements-dev.txt
                    ./.ci-venv/bin/python -m evals.runner mock --judge-provider mock --golden-file ../evals/ci_smoke.jsonl
                '''
            }
        }

        stage('5. AI Code Review Comment') {
            steps {
                script {
                    def diffSummary = sh(
                        script: "git diff HEAD~1 HEAD --stat || echo 'no previous commit to diff'",
                        returnStdout: true
                    ).trim()
                    // Uses our own gateway (mock provider — free, no live
                    // credentials needed inside Jenkins) to draft a review
                    // comment. GATEWAY_URL points at the gateway running in
                    // the local kind cluster (see PROGRESS.md Part 10).
                    sh """
                        curl -sS -X POST \${GATEWAY_URL:-http://localhost:8000}/v1/chat/playground \
                          -H 'Content-Type: application/json' \
                          -d '{"provider":"mock","prompt":"Review this diff summary for risk: ${diffSummary}"}' \
                          || echo 'AI review call failed (non-blocking for this part) — see console log'
                    """
                }
            }
        }

        stage('6. Deploy to kind (staging)') {
            steps {
                sh '''
                    docker build -t eacp-gateway:staging ./gateway
                    kind load docker-image eacp-gateway:staging --name eacp-local
                    helm upgrade --install eacp-staging ./k8s/eacp-chart \
                      --namespace eacp-staging --create-namespace \
                      --set gateway.image=eacp-gateway:staging \
                      --set gateway.nodePort=30081
                    kubectl rollout status deployment/gateway -n eacp-staging --timeout=90s
                '''
            }
        }

        stage('7. Promote staging -> live') {
            steps {
                sh '''
                    curl -sS -f http://localhost:30081/health
                    helm upgrade --install eacp-prod ./k8s/eacp-chart \
                      --namespace eacp-prod --create-namespace \
                      --set gateway.image=eacp-gateway:staging \
                      --set gateway.nodePort=30080
                    kubectl rollout status deployment/gateway -n eacp-prod --timeout=90s
                '''
            }
        }
    }

    post {
        failure {
            echo 'Pipeline failed — see the failed stage above. Nothing after that stage ran, and eacp-prod was not touched if the failure was at or before stage 6.'
        }
        always {
            sh 'docker rmi eacp-gateway:ci-scan eacp-gateway:staging || true'
        }
    }
}
