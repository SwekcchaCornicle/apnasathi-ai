
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
if not re.fullmatch(r"[0-9]+", desired_count):
    raise ValueError("backendDesiredCount must be a non-negative integer.")
image_tag = app.node.try_get_context("backendImageTag")
if image_tag is None:
    if int(desired_count) > 0:
        raise ValueError("Set backendImageTag to the published ECR image tag before starting ECS.")
    image_tag = "v1"
if not isinstance(image_tag, str) or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}", image_tag):
    raise ValueError("backendImageTag must be a valid Docker image tag.")

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
    env=env,
)

app.synth()
