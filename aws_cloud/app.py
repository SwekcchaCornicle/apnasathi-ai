
import os
import re

import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.database_stack import DatabaseStack
from stacks.application_stack import ApplicationStack
from stacks.infrastructure_stack import InfrastructureStack


app = cdk.App()

# AWS environment
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region="ap-south-1",
)

# Keep infrastructure-only development synths safe until an image has been published.
desired_count = str(app.node.try_get_context("backendDesiredCount") or "0")
if desired_count not in {"0", "1", "2", "3"}:
    raise ValueError("backendDesiredCount must be between 0 and 3.")
image_tag = app.node.try_get_context("backendImageTag")
if image_tag is None:
    if int(desired_count) > 0:
        raise ValueError("Set backendImageTag to the published ECR image tag before starting ECS.")
    image_tag = "v1"
if not isinstance(image_tag, str) or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}", image_tag):
    raise ValueError("backendImageTag must be a valid Docker image tag.")

cognito_user_pool = app.node.try_get_context("cognitoUserPoolId")
cognito_client_id = app.node.try_get_context("cognitoClientId")
if bool(cognito_user_pool) != bool(cognito_client_id):
    raise ValueError("Set both cognitoUserPoolId and cognitoClientId.")
if cognito_user_pool and (
    not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]_[A-Za-z0-9]+", str(cognito_user_pool))
    or not re.fullmatch(r"[a-zA-Z0-9]{1,128}", str(cognito_client_id))
):
    raise ValueError("Set valid Cognito user pool and public app client identifiers.")


# -------------------------------------------------
# Stack 1: Network
# -------------------------------------------------

egress_mode = app.node.try_get_context("networkEgress") or "none"
if egress_mode not in {"none", "nat", "proxy"}:
    raise ValueError("networkEgress must be none, nat, or proxy.")
proxy_url = app.node.try_get_context("backendHttpsProxy")
if (egress_mode == "proxy") != bool(proxy_url) or (
    proxy_url and not re.fullmatch(r"https?://[a-zA-Z0-9.-]+:[0-9]{1,5}", proxy_url)
):
    raise ValueError("Proxy mode requires backendHttpsProxy=http://HOST:PORT without credentials.")

google_project = app.node.try_get_context("googleCloudProject")
google_location = app.node.try_get_context("googleCloudLocation") or "global"
wif_secret_arn = app.node.try_get_context("googleWifSecretArn")
if bool(google_project) != bool(wif_secret_arn):
    raise ValueError("Set both googleCloudProject and googleWifSecretArn for ECS Vertex access.")
if wif_secret_arn and not re.fullmatch(
    rf"arn:aws:secretsmanager:ap-south-1:{env.account or '[0-9]{12}'}:secret:[A-Za-z0-9/_+=.@-]+-[A-Za-z0-9]{{6}}",
    wif_secret_arn,
):
    raise ValueError("googleWifSecretArn must be a complete Secrets Manager ARN in this AWS account and region.")

watchmode_secret_arn = app.node.try_get_context("watchmodeSecretArn")
if watchmode_secret_arn and not re.fullmatch(
    rf"arn:aws:secretsmanager:ap-south-1:{env.account or '[0-9]{{12}}'}:secret:[A-Za-z0-9/_+=.@-]+-[A-Za-z0-9]{{6}}",
    watchmode_secret_arn,
):
    raise ValueError("watchmodeSecretArn must be a complete Secrets Manager ARN.")

instagram_secret_arn = app.node.try_get_context("instagramSecretArn")
instagram_secret_json_key = app.node.try_get_context("instagramSecretJsonKey")
if instagram_secret_json_key and (
    not instagram_secret_arn or not re.fullmatch(r"[A-Za-z0-9 _.-]+", instagram_secret_json_key)
):
    raise ValueError("Set a valid JSON key alongside the Instagram secret ARN.")
instagram_api_version = app.node.try_get_context("instagramApiVersion")

whatsapp_secret_arn = app.node.try_get_context("whatsappSecretArn")
if whatsapp_secret_arn and not re.fullmatch(
    rf"arn:aws:secretsmanager:ap-south-1:{env.account or '[0-9]{{12}}'}:secret:[A-Za-z0-9/_+=.@-]+-[A-Za-z0-9]{{6}}",
    whatsapp_secret_arn,
):
    raise ValueError("whatsappSecretArn must be a complete Secrets Manager ARN in this AWS account and region.")

instagram_image_origin = app.node.try_get_context("instagramImageOrigin")
instagram_config = (instagram_secret_arn, instagram_api_version, instagram_image_origin)
if any(instagram_config) and (
    not all(instagram_config)
    or not re.fullmatch(r"v[0-9]+\.[0-9]+", instagram_api_version)
    or not re.fullmatch(r"https://[A-Za-z0-9.-]+", instagram_image_origin)
    or not re.fullmatch(
        rf"arn:aws:secretsmanager:ap-south-1:{env.account or '[0-9]{{12}}'}:secret:[A-Za-z0-9/_+=.@-]+-[A-Za-z0-9]{{6}}",
        instagram_secret_arn,
    )
):
    raise ValueError("Set a complete Instagram secret ARN, Meta API version, and public HTTPS image origin.")

network_stack = NetworkStack(
    app,
    "ApnaSathiNetworkStack",
    enable_nat=egress_mode == "nat",
    env=env,
)

# -------------------------------------------------
# Stack 2: Database
# -------------------------------------------------

database_stack = DatabaseStack(
    app,
    "ApnaSathiDatabaseStack",
    private_subnet_a=network_stack.private_subnet_a,
    private_subnet_b=network_stack.private_subnet_b,
    rds_security_group=network_stack.rds_security_group,
    env=env,
)

# -------------------------------------------------
# Stack 4: Shared Infrastructure
# -------------------------------------------------

infrastructure_stack = InfrastructureStack(
    app,
    "ApnaSathiInfrastructureStack",
    env=env,
)

# -------------------------------------------------
# Stack 3: Application
# -------------------------------------------------

application_stack = ApplicationStack(
    app,
    "ApnaSathiApplicationStack",
    public_subnet_a=network_stack.public_subnet_a,
    public_subnet_b=network_stack.public_subnet_b,
    private_subnet_a=network_stack.private_subnet_a,
    private_subnet_b=network_stack.private_subnet_b,
    alb_security_group=network_stack.alb_security_group,
    backend_security_group=network_stack.backend_security_group,
    vpc_id=network_stack.vpc.ref,
    database=database_stack,
    audio_bucket=infrastructure_stack.audio_bucket,
    desired_count=int(desired_count),
    image_tag=image_tag,
    google_project=google_project,
    google_location=google_location,
    wif_secret_arn=wif_secret_arn,
    https_proxy=proxy_url,
    cognito_user_pool=cognito_user_pool,
    cognito_client_id=cognito_client_id,
    watchmode_secret_arn=watchmode_secret_arn,
    instagram_secret_arn=instagram_secret_arn,
    instagram_secret_json_key=instagram_secret_json_key,
    instagram_api_version=instagram_api_version,
    instagram_image_origin=instagram_image_origin,
    whatsapp_secret_arn=whatsapp_secret_arn,
    env=env,
)

app.synth()
