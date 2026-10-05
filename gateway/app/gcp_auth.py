"""Shared Google Cloud OAuth token helper — extracted from app/providers/vertex.py
in Part 12 so the Analyst Agent's BigQuery REST calls can reuse the exact
same (already hardened) auth path, instead of either depending on
google-cloud-bigquery (which conflicts with this project's OpenTelemetry
deps — see Part 12 PROGRESS.md) or duplicating this logic.

This is the same code that handles: local dev (gcloud ADC), and on real AWS
(Part 9 onward) cross-cloud Workload Identity Federation through EKS Pod
Identity — including the google-auth library gotcha where
Credentials.from_info() silently discards a custom AWS credential supplier.
"""
import json
import os

import boto3
import google.auth
import google.auth.aws
import google.auth.exceptions
import google.auth.transport.requests

_credentials = None


class _PodIdentitySupplier(google.auth.aws.AwsSecurityCredentialsSupplier):
    def get_aws_security_credentials(self, context, request):
        try:
            creds = boto3.Session().get_credentials().get_frozen_credentials()
        except Exception as exc:
            raise google.auth.exceptions.RefreshError(exc, retryable=True)
        return google.auth.aws.AwsSecurityCredentials(
            creds.access_key, creds.secret_key, creds.token
        )

    def get_aws_region(self, context, request):
        return os.environ.get("AWS_REGION") or boto3.Session().region_name


def get_access_token() -> str:
    global _credentials
    if _credentials is None:
        wif_config_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if wif_config_path and os.path.exists(wif_config_path):
            with open(wif_config_path) as f:
                config_info = json.load(f)
            _credentials = google.auth.aws.Credentials(
                audience=config_info["audience"],
                subject_token_type=config_info["subject_token_type"],
                token_url=config_info["token_url"],
                service_account_impersonation_url=config_info.get(
                    "service_account_impersonation_url"
                ),
                aws_security_credentials_supplier=_PodIdentitySupplier(),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            _credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
    if not _credentials.valid:
        _credentials.refresh(google.auth.transport.requests.Request())
    return _credentials.token
