
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_applicationautoscaling as scaling,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ec2 as ec2,
    aws_s3 as s3,
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
        vpc_id: str,
        database,
        audio_bucket: s3.IBucket,
        desired_count: int,
        image_tag: str,
        google_project: str | None = None,
        google_location: str = "global",
        wif_secret_arn: str | None = None,
        https_proxy: str | None = None,
        cognito_user_pool: str | None = None,
        cognito_client_id: str | None = None,
        watchmode_secret_arn: str | None = None,
        instagram_secret_arn: str | None = None,
        instagram_secret_json_key: str | None = None,
        instagram_api_version: str | None = None,
        instagram_image_origin: str | None = None,
        whatsapp_secret_arn: str | None = None,
        google_calendar_secret_arn: str | None = None,
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

        self.task_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:PutObject", "s3:GetObject"],
            resources=[audio_bucket.arn_for_objects("audio/*")],
        ))

        # -------------------------------------------------
        # 6. ECS Fargate Task Definition
        # -------------------------------------------------

        google_environment = {}
        google_secrets = []
        if google_project and wif_secret_arn:
            google_environment = {"GOOGLE_CLOUD_PROJECT": google_project, "GOOGLE_CLOUD_LOCATION": google_location}
            self.execution_role.add_to_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"], resources=[wif_secret_arn],
            ))
            google_secrets.append(ecs.CfnTaskDefinition.SecretProperty(
                name="GOOGLE_WIF_CONFIG_JSON", value_from=wif_secret_arn,
            ))
        if https_proxy:
            google_environment.update(
                HTTPS_PROXY=https_proxy,
                NO_PROXY="localhost,127.0.0.1,169.254.170.2,169.254.170.23,169.254.169.254,.amazonaws.com",
            )

        watchmode_secrets = []
        if watchmode_secret_arn:
            self.execution_role.add_to_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"], resources=[watchmode_secret_arn],
            ))
            watchmode_secrets.append(ecs.CfnTaskDefinition.SecretProperty(
                name="WATCHMODE_API_KEY", value_from=watchmode_secret_arn,
            ))

        instagram_environment = {}
        instagram_secrets = []
        if instagram_secret_arn:
            instagram_environment = {
                "INSTAGRAM_API_VERSION": instagram_api_version,
                "INSTAGRAM_IMAGE_ORIGIN": instagram_image_origin,
            }
            self.execution_role.add_to_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"], resources=[instagram_secret_arn],
            ))
            secret_reference = instagram_secret_arn
            if instagram_secret_json_key:
                secret_reference = f"{secret_reference}:{instagram_secret_json_key}::"
            instagram_secrets.append(ecs.CfnTaskDefinition.SecretProperty(
                name="INSTAGRAM_APP_SECRET", value_from=secret_reference,
            ))

        whatsapp_secrets = []
        if whatsapp_secret_arn:
            self.execution_role.add_to_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"], resources=[whatsapp_secret_arn],
            ))
            for env_name, json_key in (
                ("WHATSAPP_ACCESS_TOKEN", "access_token"),
                ("WHATSAPP_PHONE_NUMBER_ID", "phone_number_id"),
                ("WHATSAPP_REMINDER_TEMPLATE", "reminder_template"),
                ("WHATSAPP_GRAPH_API_VERSION", "graph_api_version"),
                ("WHATSAPP_TEMPLATE_LANGUAGE", "template_language"),
            ):
                whatsapp_secrets.append(ecs.CfnTaskDefinition.SecretProperty(
                    name=env_name, value_from=f"{whatsapp_secret_arn}:{json_key}::",
                ))

        google_calendar_secrets = []
        if google_calendar_secret_arn:
            self.execution_role.add_to_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"], resources=[google_calendar_secret_arn],
            ))
            for env_name, json_key in (
                ("GOOGLE_CALENDAR_CLIENT_ID", "client_id"),
                ("GOOGLE_CALENDAR_CLIENT_SECRET", "client_secret"),
                ("GOOGLE_CALENDAR_REDIRECT_URI", "redirect_uri"),
                ("GOOGLE_TOKEN_ENCRYPTION_KEY", "token_encryption_key"),
            ):
                google_calendar_secrets.append(ecs.CfnTaskDefinition.SecretProperty(
                    name=env_name, value_from=f"{google_calendar_secret_arn}:{json_key}::",
                ))

        cognito_environment = {}
        if cognito_user_pool and cognito_client_id:
            cognito_environment = {
                "COGNITO_REGION": cognito_user_pool.split("_", 1)[0],
                "COGNITO_USER_POOL_ID": cognito_user_pool,
                "COGNITO_CLIENT_ID": cognito_client_id,
            }

        self.task_definition = ecs.CfnTaskDefinition(
            self,
            "BackendTaskDefinition",
            family="apnasathi-backend",
            requires_compatibilities=["FARGATE"],
            network_mode="awsvpc",
            cpu="512",
            memory="2048",
            execution_role_arn=self.execution_role.role_arn,
            task_role_arn=self.task_role.role_arn,
            runtime_platform=ecs.CfnTaskDefinition.RuntimePlatformProperty(
                operating_system_family="LINUX",
                cpu_architecture="ARM64",
            ),
            container_definitions=[
                ecs.CfnTaskDefinition.ContainerDefinitionProperty(
                    name="backend",
                    image=f"{self.repository.repository_uri}:{image_tag}",
                    essential=True,
                    stop_timeout=45,
                    health_check=ecs.CfnTaskDefinition.HealthCheckProperty(
                        command=["CMD", "python", "-c",
                                 "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).close()"],
                        interval=30, timeout=5, retries=3, start_period=120,
                    ),
                    port_mappings=[
                        ecs.CfnTaskDefinition.PortMappingProperty(
                            container_port=8000,
                            protocol="tcp",
                        )
                    ],
                    environment=[
                        *(ecs.CfnTaskDefinition.KeyValuePairProperty(name=name, value=value)
                          for name, value in (google_environment | cognito_environment | instagram_environment).items()),
                        ecs.CfnTaskDefinition.KeyValuePairProperty(
                            name="AUDIO_S3_BUCKET", value=audio_bucket.bucket_name,
                        ),
                        ecs.CfnTaskDefinition.KeyValuePairProperty(
                            name="AWS_REGION", value=self.region,
                        ),
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
                        *google_secrets,
                        *instagram_secrets,
                        *whatsapp_secrets,
                        *google_calendar_secrets,
                        *watchmode_secrets,
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
        # 6b. WhatsApp reminder worker (only when configured)
        # -------------------------------------------------
        if whatsapp_secret_arn:
            self.reminder_task_definition = ecs.CfnTaskDefinition(
                self, "ReminderWorkerTaskDefinition",
                family="apnasathi-reminder-worker",
                requires_compatibilities=["FARGATE"], network_mode="awsvpc",
                cpu="256", memory="512",
                execution_role_arn=self.execution_role.role_arn,
                task_role_arn=self.task_role.role_arn,
                runtime_platform=ecs.CfnTaskDefinition.RuntimePlatformProperty(
                    operating_system_family="LINUX", cpu_architecture="ARM64",
                ),
                container_definitions=[
                    ecs.CfnTaskDefinition.ContainerDefinitionProperty(
                        name="reminder-worker",
                        image=f"{self.repository.repository_uri}:{image_tag}",
                        essential=True,
                        command=["python", "-m", "workers.reminder_worker"],
                        environment=[
                            ecs.CfnTaskDefinition.KeyValuePairProperty(name="AWS_REGION", value=self.region),
                            ecs.CfnTaskDefinition.KeyValuePairProperty(name="DB_HOST", value=database.database.attr_endpoint_address),
                            ecs.CfnTaskDefinition.KeyValuePairProperty(name="DB_PORT", value="5432"),
                            ecs.CfnTaskDefinition.KeyValuePairProperty(name="DB_NAME", value="apnasathi"),
                            *(ecs.CfnTaskDefinition.KeyValuePairProperty(name=name, value=value) for name, value in ({"HTTPS_PROXY": https_proxy, "NO_PROXY": "localhost,127.0.0.1,169.254.170.2,169.254.170.23,169.254.169.254,.amazonaws.com"}.items() if https_proxy else [])),
                        ],
                        secrets=[
                            *whatsapp_secrets,
                            ecs.CfnTaskDefinition.SecretProperty(
                                name="DATABASE_CREDENTIALS",
                                value_from=database.database.attr_master_user_secret_secret_arn,
                            ),
                        ],
                        log_configuration=ecs.CfnTaskDefinition.LogConfigurationProperty(
                            log_driver="awslogs",
                            options={
                                "awslogs-group": self.log_group.log_group_name,
                                "awslogs-region": self.region,
                                "awslogs-stream-prefix": "reminder-worker",
                            },
                        ),
                    )
                ],
            )
            self.reminder_worker_service = ecs.CfnService(
                self, "ReminderWorkerService",
                service_name="apnasathi-reminder-worker",
                cluster=self.cluster.ref,
                task_definition=self.reminder_task_definition.ref,
                launch_type="FARGATE", desired_count=1,
                deployment_configuration=ecs.CfnService.DeploymentConfigurationProperty(
                    deployment_circuit_breaker=ecs.CfnService.DeploymentCircuitBreakerProperty(
                        enable=True, rollback=True,
                    )
                ),
                network_configuration=ecs.CfnService.NetworkConfigurationProperty(
                    awsvpc_configuration=ecs.CfnService.AwsVpcConfigurationProperty(
                        assign_public_ip="DISABLED",
                        subnets=[private_subnet_a.ref, private_subnet_b.ref],
                        security_groups=[backend_security_group.attr_group_id],
                    )
                ),
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
            vpc_id=vpc_id,
            health_check_enabled=True,
            health_check_protocol="HTTP",
            health_check_path="/api/v1/health",
            health_check_port="traffic-port",
            matcher=elbv2.CfnTargetGroup.MatcherProperty(
                http_code="200-399"
            ),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
            health_check_interval_seconds=30,
        )

        # -------------------------------------------------
        # 9. HTTP forwarding listener
        # Keep the port 80 logical ID so CloudFormation can update it in place.
        self.http_listener = elbv2.CfnListener(
            self,
            "HttpRedirectListener",
            load_balancer_arn=self.load_balancer.ref,
            port=80,
            protocol="HTTP",
            default_actions=[
                elbv2.CfnListener.ActionProperty(
                    type="forward", target_group_arn=self.target_group.ref,
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
            desired_count=desired_count,
            deployment_configuration=ecs.CfnService.DeploymentConfigurationProperty(
                deployment_circuit_breaker=ecs.CfnService.DeploymentCircuitBreakerProperty(
                    enable=True,
                    rollback=True,
                )
            ),
            health_check_grace_period_seconds=120,
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

        self.service.add_dependency(self.http_listener)

        if desired_count:
            target = scaling.CfnScalableTarget(
                self, "BackendScalingTarget",
                service_namespace="ecs",
                scalable_dimension="ecs:service:DesiredCount",
                resource_id=f"service/{self.cluster.ref}/{self.service.attr_name}",
                min_capacity=1,
                max_capacity=3,
                role_arn=f"arn:{self.partition}:iam::{self.account}:role/aws-service-role/ecs.application-autoscaling.amazonaws.com/AWSServiceRoleForApplicationAutoScaling_ECSService",
            )
            scaling.CfnScalingPolicy(
                self, "BackendMemoryScalingPolicy",
                policy_name="apnasathi-memory-target",
                policy_type="TargetTrackingScaling",
                scaling_target_id=target.ref,
                target_tracking_scaling_policy_configuration=scaling.CfnScalingPolicy.TargetTrackingScalingPolicyConfigurationProperty(
                    predefined_metric_specification=scaling.CfnScalingPolicy.PredefinedMetricSpecificationProperty(
                        predefined_metric_type="ECSServiceAverageMemoryUtilization",
                    ),
                    target_value=65,
                    scale_out_cooldown=60,
                    scale_in_cooldown=300,
                ),
            )

        # -------------------------------------------------
        # 12. Outputs
        # -------------------------------------------------

        from aws_cdk import CfnOutput

        CfnOutput(self, "BackendTaskRoleArn", value=self.task_role.role_arn)
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