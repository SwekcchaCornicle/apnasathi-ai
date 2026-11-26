"""Vertex credentials for local ADC and ECS task-role federation."""

import json
import os
import re
from functools import lru_cache

import boto3
from google import genai
from google.auth import aws
from google.auth.exceptions import RefreshError
from google.genai import types

_CLOUD_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_STS_URL = "https://sts.googleapis.com/v1/token"
_AUDIENCE = re.compile(
    r"//iam\.googleapis\.com/projects/\d+/locations/global/workloadIdentityPools/[\w-]+/providers/[\w-]+"
)
_IMPERSONATION = re.compile(
    r"https://iamcredentials\.googleapis\.com/v1/projects/-/serviceAccounts/"
    r"[\w.%+@-]+\.iam\.gserviceaccount\.com:generateAccessToken"
)


class VertexConfigurationError(RuntimeError):
    """Vertex deployment configuration is absent or invalid."""


class EcsTaskCredentials(aws.AwsSecurityCredentialsSupplier):
    def __init__(self, region: str):
        self.region = region
        self.session = boto3.Session()

    def get_aws_region(self, context, request):
        return self.region

    def get_aws_security_credentials(self, context, request):
        try:
            credentials = self.session.get_credentials()
            if credentials is not None and credentials.method == "container-role":
                frozen = credentials.get_frozen_credentials()
                if frozen.token:
                    return aws.AwsSecurityCredentials(frozen.access_key, frozen.secret_key, frozen.token)
        except Exception:
            raise RefreshError("ECS task credentials could not be retrieved.") from None
        raise RefreshError("An ECS task role with temporary credentials is required.")


def ecs_google_credentials(raw_config: str, region: str):
    try:
        config = json.loads(raw_config)
    except ValueError:
        raise VertexConfigurationError("The Vertex federation configuration is invalid.") from None
    if not isinstance(config, dict):
        raise VertexConfigurationError("The Vertex federation configuration is invalid.")
    audience = config.get("audience")
    impersonation = config.get("service_account_impersonation_url")
    if not (
        config.get("type") == "external_account"
        and config.get("subject_token_type") == "urn:ietf:params:aws:token-type:aws4_request"
        and config.get("token_url") == _STS_URL
        and isinstance(audience, str) and _AUDIENCE.fullmatch(audience)
        and isinstance(impersonation, str) and _IMPERSONATION.fullmatch(impersonation)
        and re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region)
    ):
        raise VertexConfigurationError("The Vertex federation configuration is invalid.")
    # The generated AWS JSON includes EC2 IMDS URLs. ECS uses boto3's container-role provider instead.
    return aws.Credentials(
        audience=audience,
        subject_token_type=config["subject_token_type"],
        token_url=_STS_URL,
        service_account_impersonation_url=impersonation,
        aws_security_credentials_supplier=EcsTaskCredentials(region),
        scopes=[_CLOUD_SCOPE],
    )


@lru_cache(maxsize=1)
def get_vertex_client():
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"
    if not project:
        raise VertexConfigurationError("GOOGLE_CLOUD_PROJECT is required.")
    config = os.getenv("GOOGLE_WIF_CONFIG_JSON")
    ecs = "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI" in os.environ or "AWS_CONTAINER_CREDENTIALS_FULL_URI" in os.environ
    if ecs and not config:
        raise VertexConfigurationError("ECS requires Vertex Workload Identity Federation configuration.")
    options = {}
    if config:
        options["credentials"] = ecs_google_credentials(config, os.getenv("AWS_REGION", ""))
    return genai.Client(
        vertexai=True, project=project, location=location,
        http_options=types.HttpOptions(timeout=30000), **options,
    )
