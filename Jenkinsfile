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
        // "localhost" from inside the Jenkins container means the container
        // itself, not the host running the gateway's kind pod -- confirmed
        // during Part 10 setup that host.docker.internal is what actually
        // reaches it from here.
        GATEWAY_URL  = "http://host.docker.internal:8000"
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
                // evals/runner.py must run with the repo ROOT as cwd (it does
                // `sys.path.insert(..., ".../gateway")` internally, and
                // "python -m evals.runner" needs evals/ to be a sibling of
                // the cwd, not the other way around) -- caught by this
                // part's first real Jenkins run: stage 4 failed with
                // "ModuleNotFoundError: No module named 'evals'" when this
                // was run from inside gateway/.
                //
                // --quality-floor is required here: without it, runner.py
                // always exits 0 regardless of score (its original design —
                // it was only ever run manually and read by a human before
                // this part). Verified this the hard way: a deliberately
                // 0%-scoring golden file still exited 0 until this flag was
                // added, which would have made this whole stage a no-op gate.
                sh '''
                    gateway/.ci-venv/bin/python -m evals.runner mock --judge-provider mock --golden-file evals/ci_smoke.jsonl --quality-floor 0.80
                '''
            }
        }

        stage('5. AI Code Review Comment') {
            steps {
                // Uses our own gateway (mock provider — free, no live
                // credentials needed inside Jenkins) to draft a review
                // comment. GATEWAY_URL points at the gateway running in the
                // local kind cluster (see PROGRESS.md Part 10).
                //
                // Build #2 broke here: the diff --stat output contains a
                // real newline, which naive shell string interpolation into
                // a JSON literal doesn't escape, so curl sent invalid JSON
                // every time. Fixed by using jq to build the payload
                // properly instead of hand-rolling JSON in a shell string.
                sh '''
                    DIFF_SUMMARY=$(git diff HEAD~1 HEAD --stat || echo 'no previous commit to diff')
                    PROMPT="Review this diff summary for risk: ${DIFF_SUMMARY}"
                    PAYLOAD=$(jq -n --arg provider "mock" --arg prompt "$PROMPT" '{provider:$provider,prompt:$prompt}')
                    curl -sS -X POST "${GATEWAY_URL:-http://localhost:8000}/v1/chat/playground" \
                      -H 'Content-Type: application/json' \
                      -d "$PAYLOAD" \
                      || echo 'AI review call failed (non-blocking for this part) — see console log'
                '''
            }
        }

        stage('6. Deploy to kind (staging)') {
            steps {
                // Build #4 broke here: eacp-staging is a brand-new namespace,
                // and Kubernetes Secrets are namespace-scoped -- the
                // eacp-secrets Secret created back in Part 8 only exists in
                // "default", so the pod failed with CreateContainerConfigError
                // ("secret eacp-secrets not found"). Fixed by copying the
                // existing Secret's data into the target namespace before
                // deploying, rather than hardcoding any secret value here
                // (keeps "secrets never in code" intact -- this reads the
                // real values from the cluster, never writes them to disk).
                //
                // Image is tagged with the unique Jenkins build number, not
                // a static ":staging" tag -- verified by hand that a static
                // tag is a real bug, not a theoretical one: with
                // imagePullPolicy: IfNotPresent (k8s/eacp-chart's default),
                // rebuilding and reloading an image under the SAME tag does
                // NOT make the node's cached layer update, so a second
                // `helm upgrade` with an unchanged tag reports success and
                // even creates a new pod, but that pod silently runs the
                // OLD code. Confirmed this by deploying v1, rebuilding v2
                // under the same tag, and finding the "upgraded" pod still
                // had v1's code. A unique tag per build forces a real pull.
                sh '''
                    kubectl create namespace eacp-staging --dry-run=client -o yaml | kubectl apply -f -
                    kubectl get secret eacp-secrets -n default -o json \
                      | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.annotations)' \
                      | kubectl apply -n eacp-staging -f -

                    docker build -t eacp-gateway:build-${BUILD_NUMBER} ./gateway
                    kind load docker-image eacp-gateway:build-${BUILD_NUMBER} --name eacp-local
                    helm upgrade --install eacp-staging ./k8s/eacp-chart \
                      --namespace eacp-staging \
                      --set gateway.image=eacp-gateway:build-${BUILD_NUMBER} \
                      --set gateway.nodePort=30081
                    kubectl rollout status deployment/gateway -n eacp-staging --timeout=90s
                '''
            }
        }

        stage('7. Promote staging -> live') {
            steps {
                // Same namespace-scoped-Secret fix as stage 6 — eacp-prod
                // needs its own copy of eacp-secrets too.
                //
                // Health check uses in-cluster Service DNS, not a host port —
                // eacp-staging's NodePort (30081) was never added to kind's
                // extraPortMappings (only 30080, from Part 8, is mapped to
                // the host), so it's unreachable from the host/Jenkins
                // container directly. A temporary pod inside the cluster can
                // always reach it via cluster DNS regardless of host mappings.
                sh '''
                    kubectl run staging-healthcheck --rm -i --restart=Never --image=curlimages/curl -n eacp-staging \
                      -- curl -sS -f -m 10 http://gateway.eacp-staging.svc.cluster.local:8000/health

                    kubectl create namespace eacp-prod --dry-run=client -o yaml | kubectl apply -f -
                    kubectl get secret eacp-secrets -n default -o json \
                      | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.annotations)' \
                      | kubectl apply -n eacp-prod -f -

                    helm upgrade --install eacp-prod ./k8s/eacp-chart \
                      --namespace eacp-prod \
                      --set gateway.image=eacp-gateway:build-${BUILD_NUMBER} \
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
            sh 'docker rmi eacp-gateway:ci-scan eacp-gateway:build-${BUILD_NUMBER} || true'
        }
    }
}
