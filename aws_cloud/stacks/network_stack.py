
from aws_cdk import (
    Stack,
    CfnOutput,
    CfnTag,
    aws_ec2 as ec2,
)
from constructs import Construct


class NetworkStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        # ==========================================
        # 1. VPC
        # ==========================================

        self.vpc = ec2.CfnVPC(
            self,
            "ApnaSathiVPC",
            cidr_block="10.20.0.0/16",
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags=[
                CfnTag(key="Name", value="apnasathi-vpc"),
                CfnTag(key="Project", value="ApnaSathiAI"),
                CfnTag(key="Environment", value="dev"),
            ],
        )

        # ==========================================
        # 2. INTERNET GATEWAY
        # ==========================================

        self.internet_gateway = ec2.CfnInternetGateway(
            self,
            "ApnaSathiInternetGateway",
            tags=[
                CfnTag(key="Name", value="apnasathi-igw"),
            ],
        )

        self.gateway_attachment = ec2.CfnVPCGatewayAttachment(
            self,
            "AttachInternetGateway",
            vpc_id=self.vpc.ref,
            internet_gateway_id=self.internet_gateway.ref,
        )

        # ==========================================
        # 3. PUBLIC SUBNETS
        # ==========================================

        self.public_subnet_a = ec2.CfnSubnet(
            self,
            "PublicSubnetA",
            vpc_id=self.vpc.ref,
            cidr_block="10.20.1.0/24",
            availability_zone="ap-south-1a",
            map_public_ip_on_launch=True,
            tags=[
                CfnTag(key="Name", value="apnasathi-public-a"),
            ],
        )

        self.public_subnet_b = ec2.CfnSubnet(
            self,
            "PublicSubnetB",
            vpc_id=self.vpc.ref,
            cidr_block="10.20.2.0/24",
            availability_zone="ap-south-1b",
            map_public_ip_on_launch=True,
            tags=[
                CfnTag(key="Name", value="apnasathi-public-b"),
            ],
        )

        # ==========================================
        # 4. PRIVATE SUBNETS
        # ==========================================

        self.private_subnet_a = ec2.CfnSubnet(
            self,
            "PrivateSubnetA",
            vpc_id=self.vpc.ref,
            cidr_block="10.20.11.0/24",
            availability_zone="ap-south-1a",
            map_public_ip_on_launch=False,
            tags=[
                CfnTag(key="Name", value="apnasathi-private-a"),
            ],
        )

        self.private_subnet_b = ec2.CfnSubnet(
            self,
            "PrivateSubnetB",
            vpc_id=self.vpc.ref,
            cidr_block="10.20.12.0/24",
            availability_zone="ap-south-1b",
            map_public_ip_on_launch=False,
            tags=[
                CfnTag(key="Name", value="apnasathi-private-b"),
            ],
        )

        # ==========================================
        # 5. PUBLIC ROUTE TABLE
        # ==========================================

        self.public_route_table = ec2.CfnRouteTable(
            self,
            "PublicRouteTable",
            vpc_id=self.vpc.ref,
            tags=[
                CfnTag(
                    key="Name",
                    value="apnasathi-public-rt",
                ),
            ],
        )

        self.public_internet_route = ec2.CfnRoute(
            self,
            "PublicInternetRoute",
            route_table_id=self.public_route_table.ref,
            destination_cidr_block="0.0.0.0/0",
            gateway_id=self.internet_gateway.ref,
        )

        self.public_internet_route.add_dependency(
            self.gateway_attachment
        )

        self.public_association_a = (
            ec2.CfnSubnetRouteTableAssociation(
                self,
                "PublicRouteAssociationA",
                subnet_id=self.public_subnet_a.ref,
                route_table_id=self.public_route_table.ref,
            )
        )

        self.public_association_b = (
            ec2.CfnSubnetRouteTableAssociation(
                self,
                "PublicRouteAssociationB",
                subnet_id=self.public_subnet_b.ref,
                route_table_id=self.public_route_table.ref,
            )
        )

        # ==========================================
        # 6. PRIVATE ROUTE TABLE
        # ==========================================

        self.private_route_table = ec2.CfnRouteTable(
            self,
            "PrivateRouteTable",
            vpc_id=self.vpc.ref,
            tags=[
                CfnTag(
                    key="Name",
                    value="apnasathi-private-rt",
                ),
            ],
        )

        # No NAT Gateway and no public internet route.

        self.private_association_a = (
            ec2.CfnSubnetRouteTableAssociation(
                self,
                "PrivateRouteAssociationA",
                subnet_id=self.private_subnet_a.ref,
                route_table_id=self.private_route_table.ref,
            )
        )

        self.private_association_b = (
            ec2.CfnSubnetRouteTableAssociation(
                self,
                "PrivateRouteAssociationB",
                subnet_id=self.private_subnet_b.ref,
                route_table_id=self.private_route_table.ref,
            )
        )

        # ==========================================
        # 7. ALB SECURITY GROUP
        # ==========================================

        self.alb_security_group = ec2.CfnSecurityGroup(
            self,
            "ALBSecurityGroup",
            group_description="Public HTTPS and HTTP access for ALB",
            vpc_id=self.vpc.ref,
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=443,
                    to_port=443,
                    cidr_ip="0.0.0.0/0",
                    description="HTTPS traffic",
                ),
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=80,
                    to_port=80,
                    cidr_ip="0.0.0.0/0",
                    description="HTTP redirect traffic",
                ),
            ],
            tags=[
                CfnTag(
                    key="Name",
                    value="apnasathi-alb-sg",
                ),
            ],
        )

        # ==========================================
        # 8. BACKEND SECURITY GROUP
        # ==========================================

        self.backend_security_group = ec2.CfnSecurityGroup(
            self,
            "BackendSecurityGroup",
            group_description="FastAPI access only from ALB",
            vpc_id=self.vpc.ref,
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=8000,
                    to_port=8000,
                    source_security_group_id=(
                        self.alb_security_group.attr_group_id
                    ),
                    description="FastAPI from ALB",
                ),
            ],
            tags=[
                CfnTag(
                    key="Name",
                    value="apnasathi-backend-sg",
                ),
            ],
        )

        # ==========================================
        # 9. RDS SECURITY GROUP
        # ==========================================

        self.rds_security_group = ec2.CfnSecurityGroup(
            self,
            "RDSSecurityGroup",
            group_description="PostgreSQL access only from backend",
            vpc_id=self.vpc.ref,
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=5432,
                    to_port=5432,
                    source_security_group_id=(
                        self.backend_security_group.attr_group_id
                    ),
                    description="PostgreSQL from backend",
                ),
            ],
            tags=[
                CfnTag(
                    key="Name",
                    value="apnasathi-rds-sg",
                ),
            ],
        )

        # ==========================================
        # 10. VPC ENDPOINT SECURITY GROUP
        # ==========================================

        self.endpoint_security_group = ec2.CfnSecurityGroup(
            self,
            "EndpointSecurityGroup",
            group_description="HTTPS access to AWS VPC endpoints",
            vpc_id=self.vpc.ref,
            security_group_ingress=[
                ec2.CfnSecurityGroup.IngressProperty(
                    ip_protocol="tcp",
                    from_port=443,
                    to_port=443,
                    source_security_group_id=(
                        self.backend_security_group.attr_group_id
                    ),
                    description="HTTPS from ECS backend",
                ),
            ],
            tags=[
                CfnTag(
                    key="Name",
                    value="apnasathi-endpoint-sg",
                ),
            ],
        )

        # ==========================================
        # 11. INTERFACE VPC ENDPOINTS
        # ==========================================

        def create_interface_endpoint(
            logical_id: str,
            service: str,
        ):

            endpoint = ec2.CfnVPCEndpoint(
                self,
                logical_id,
                vpc_id=self.vpc.ref,
                service_name=(
                    f"com.amazonaws.{self.region}.{service}"
                ),
                vpc_endpoint_type="Interface",
                subnet_ids=[
                    self.private_subnet_a.ref,
                    self.private_subnet_b.ref,
                ],
                security_group_ids=[
                    self.endpoint_security_group.attr_group_id
                ],
                private_dns_enabled=True,
            )

            return endpoint

        self.ecr_api_endpoint = create_interface_endpoint(
            "ECRApiEndpoint",
            "ecr.api",
        )

        self.ecr_docker_endpoint = create_interface_endpoint(
            "ECRDockerEndpoint",
            "ecr.dkr",
        )

        self.logs_endpoint = create_interface_endpoint(
            "CloudWatchLogsEndpoint",
            "logs",
        )

        self.secrets_endpoint = create_interface_endpoint(
            "SecretsManagerEndpoint",
            "secretsmanager",
        )

        self.sts_endpoint = create_interface_endpoint(
            "STSEndpoint",
            "sts",
        )

        # ==========================================
        # 12. S3 GATEWAY ENDPOINT
        # ==========================================

        self.s3_endpoint = ec2.CfnVPCEndpoint(
            self,
            "S3GatewayEndpoint",
            vpc_id=self.vpc.ref,
            service_name=f"com.amazonaws.{self.region}.s3",
            vpc_endpoint_type="Gateway",
            route_table_ids=[
                self.private_route_table.ref,
            ],
        )

        # ==========================================
        # 13. CLOUDFORMATION OUTPUTS
        # ==========================================

        CfnOutput(
            self,
            "VpcId",
            value=self.vpc.ref,
        )

        CfnOutput(
            self,
            "PublicSubnetAId",
            value=self.public_subnet_a.ref,
        )

        CfnOutput(
            self,
            "PublicSubnetBId",
            value=self.public_subnet_b.ref,
        )

        CfnOutput(
            self,
            "PrivateSubnetAId",
            value=self.private_subnet_a.ref,
        )

        CfnOutput(
            self,
            "PrivateSubnetBId",
            value=self.private_subnet_b.ref,
        )

        CfnOutput(
            self,
            "InternetGatewayId",
            value=self.internet_gateway.ref,
        )

        CfnOutput(
            self,
            "PublicRouteTableId",
            value=self.public_route_table.ref,
        )

        CfnOutput(
            self,
            "PrivateRouteTableId",
            value=self.private_route_table.ref,
        )

        CfnOutput(
            self,
            "ALBSecurityGroupId",
            value=self.alb_security_group.attr_group_id,
        )

        CfnOutput(
            self,
            "BackendSecurityGroupId",
            value=self.backend_security_group.attr_group_id,
        )

        CfnOutput(
            self,
            "RDSSecurityGroupId",
            value=self.rds_security_group.attr_group_id,
        )
