
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ec2 as ec2,
)
from constructs import Construct

class ApplicationStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        public_subnet_a: ec2.CfnSubnet,
        public_subnet_b: ec2.CfnSubnet,
        private_subnet_a: ec2.CfnSubnet,
        private_subnet_b: ec2.CfnSubnet,
        alb_security_group: ec2.CfnSecurityGroup,
        backend_security_group: ec2.CfnSecurityGroup,
        database,
        certificate_arn: str,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------
        # 1. ECR Repository
        # -------------------------------------------------

        self.repository = ecr.Repository(
            self,
            "BackendRepository",
            repository_name="apnasathi-backend",
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.IMMUTABLE,
            encryption=ecr.RepositoryEncryption.AES_256,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    tag_status=ecr.TagStatus.UNTAGGED,
                    max_image_age=Duration.days(14),
                )
            ],
        )

        # -------------------------------------------------
        # 2. ECS Cluster
        # -------------------------------------------------

        self.cluster = ecs.CfnCluster(
            self,
            "BackendCluster",
            cluster_name="apnasathi-dev-cluster",
            cluster_settings=[
                ecs.CfnCluster.ClusterSettingsProperty(
                    name="containerInsights",
                    value="enabled",
                )
            ],
        )

        # -------------------------------------------------
        # 3. CloudWatch Log Group
        # -------------------------------------------------

        self.log_group = logs.LogGroup(
            self,
            "BackendLogGroup",
            log_group_name="/apnasathi/backend",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # -------------------------------------------------
        # 4. ECS Task Execution Role
        # -------------------------------------------------

        self.execution_role = iam.Role(
            self,
            "BackendExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Allow ECS to retrieve the RDS credentials secret
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    database.database.attr_master_user_secret_secret_arn
                ],
            )
        )

        # -------------------------------------------------
        # 5. ECS Application Task Role
        # -------------------------------------------------

        self.task_role = iam.Role(
            self,
            "BackendTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Add application permissions here later:
        # S3, SQS, SNS, Bedrock, etc.

        # -------------------------------------------------
        # 6. ECS Fargate Task Definition
        # -------------------------------------------------

        self.task_definition = ecs.CfnTaskDefinition(
            self,
            "BackendTaskDefinition",
            family="apnasathi-backend",
            requires_compatibilities=["FARGATE"],
            network_mode="awsvpc",
            cpu="512",
            memory="1024",
            execution_role_arn=self.execution_role.role_arn,
            task_role_arn=self.task_role.role_arn,
            runtime_platform=ecs.CfnTaskDefinition.RuntimePlatformProperty(
                operating_system_family="LINUX",
                cpu_architecture="ARM64",
            ),
            container_definitions=[
                ecs.CfnTaskDefinition.ContainerDefinitionProperty(
                    name="backend",
                    image=f"{self.repository.repository_uri}:v1",
                    essential=True,
                    port_mappings=[
                        ecs.CfnTaskDefinition.PortMappingProperty(
                            container_port=8000,
                            protocol="tcp",
                        )
                    ],
                    environment=[
                        ecs.CfnTaskDefinition.KeyValuePairProperty(
                            name="DB_HOST",
                            value=database.database.attr_endpoint_address,
                        ),
                        ecs.CfnTaskDefinition.KeyValuePairProperty(
                            name="DB_PORT",
                            value="5432",
                        ),
                        ecs.CfnTaskDefinition.KeyValuePairProperty(
                            name="DB_NAME",
                            value="apnasathi",
                        ),
                    ],
                    secrets=[
                        ecs.CfnTaskDefinition.SecretProperty(
                            name="DATABASE_CREDENTIALS",
                            value_from=(
                                database.database
                                .attr_master_user_secret_secret_arn
                            ),
                        )
                    ],
                    log_configuration=(
                        ecs.CfnTaskDefinition.LogConfigurationProperty(
                            log_driver="awslogs",
                            options={
                                "awslogs-group": self.log_group.log_group_name,
                                "awslogs-region": self.region,
                                "awslogs-stream-prefix": "backend",
                            },
                        )
                    ),
                )
            ],
        )

        # -------------------------------------------------
        # 7. Application Load Balancer
        # -------------------------------------------------

        self.load_balancer = elbv2.CfnLoadBalancer(
            self,
            "BackendLoadBalancer",
            name="apnasathi-dev-alb",
            scheme="internet-facing",
            type="application",
            ip_address_type="ipv4",
            subnets=[
                public_subnet_a.ref,
                public_subnet_b.ref,
            ],
            security_groups=[
                alb_security_group.attr_group_id
            ],
        )

        # -------------------------------------------------
        # 8. Target Group
        # -------------------------------------------------

        self.target_group = elbv2.CfnTargetGroup(
            self,
            "BackendTargetGroup",
            name="apnasathi-backend-tg",
            port=8000,
            protocol="HTTP",
            target_type="ip",
            vpc_id=vpc_id, # type: ignore
            health_check_enabled=True,
            health_check_protocol="HTTP",
            health_check_path="/health",
            health_check_port="traffic-port",
            matcher=elbv2.CfnTargetGroup.MatcherProperty(
                http_code="200-399"
            ),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
            health_check_interval_seconds=30,
        )

        # -------------------------------------------------
        # 9. HTTPS Listener
        # -------------------------------------------------

        self.https_listener = elbv2.CfnListener(
            self,
            "HttpsListener",
            load_balancer_arn=self.load_balancer.ref,
            port=443,
            protocol="HTTPS",
            certificates=[
                elbv2.CfnListener.CertificateProperty(
                    certificate_arn=certificate_arn
                )
            ],
            ssl_policy="ELBSecurityPolicy-TLS13-1-2-2021-06",
            default_actions=[
                elbv2.CfnListener.ActionProperty(
                    type="forward",
                    target_group_arn=self.target_group.ref,
                )
            ],
        )

        # -------------------------------------------------
        # 10. HTTP to HTTPS Redirect
        # -------------------------------------------------

        self.http_listener = elbv2.CfnListener(
            self,
            "HttpRedirectListener",
            load_balancer_arn=self.load_balancer.ref,
            port=80,
            protocol="HTTP",
            default_actions=[
                elbv2.CfnListener.ActionProperty(
                    type="redirect",
                    redirect_config=(
                        elbv2.CfnListener.RedirectConfigProperty(
                            protocol="HTTPS",
                            port="443",
                            status_code="HTTP_301",
                        )
                    ),
                )
            ],
        )

        # -------------------------------------------------
        # 11. ECS Fargate Service
        # -------------------------------------------------

        self.service = ecs.CfnService(
            self,
            "BackendService",
            service_name="apnasathi-backend-service",
            cluster=self.cluster.ref,
            task_definition=self.task_definition.ref,
            launch_type="FARGATE",
            desired_count=0,
            health_check_grace_period_seconds=60,
            network_configuration=(
                ecs.CfnService.NetworkConfigurationProperty(
                    awsvpc_configuration=(
                        ecs.CfnService.AwsVpcConfigurationProperty(
                            assign_public_ip="DISABLED",
                            subnets=[
                                private_subnet_a.ref,
                                private_subnet_b.ref,
                            ],
                            security_groups=[
                                backend_security_group.attr_group_id
                            ],
                        )
                    )
                )
            ),
            load_balancers=[
                ecs.CfnService.LoadBalancerProperty(
                    target_group_arn=self.target_group.ref,
                    container_name="backend",
                    container_port=8000,
                )
            ],
        )

        self.service.add_dependency(self.https_listener)

        # -------------------------------------------------
        # 12. Outputs
        # -------------------------------------------------

        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "ECRRepositoryUri",
            value=self.repository.repository_uri,
        )

        CfnOutput(
            self,
            "ECSClusterName",
            value=self.cluster.ref,
        )

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self.load_balancer.attr_dns_name,
        )

    @staticmethod
    def _vpc_id_from_subnet(subnet: ec2.CfnSubnet) -> str:
        return subnet.vpc_id