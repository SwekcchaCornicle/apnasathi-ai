
import os

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

if not certificate_arn:
    raise ValueError(
        "Missing ACM certificate ARN. "
        "Pass it using -c certificateArn=YOUR_CERTIFICATE_ARN"
    )

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

app.synth()
