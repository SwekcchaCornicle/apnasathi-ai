
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

# ACM certificate ARN must be supplied through CDK context.
certificate_arn = app.node.try_get_context("certificateArn")

if not isinstance(certificate_arn, str) or not re.fullmatch(
    r"arn:aws:acm:ap-south-1:[0-9]{12}:certificate/[0-9a-fA-F-]{36}", certificate_arn
):
    raise ValueError("Pass a Mumbai ACM certificate ARN using -c certificateArn=YOUR_CERTIFICATE_ARN")

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

network_stack = NetworkStack(
    app,
    "ApnaSathiNetworkStack",
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
    certificate_arn=certificate_arn,
    audio_bucket=infrastructure_stack.audio_bucket,
    desired_count=int(desired_count),
    image_tag=image_tag,
    env=env,
)

app.synth()
