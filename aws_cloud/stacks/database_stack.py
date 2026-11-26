
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_rds as rds,
)
from constructs import Construct


class DatabaseStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        private_subnet_a: ec2.CfnSubnet,
        private_subnet_b: ec2.CfnSubnet,
        rds_security_group: ec2.CfnSecurityGroup,
        **kwargs
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        # ==========================================
        # 1. DATABASE SUBNET GROUP
        # ==========================================

        self.db_subnet_group = rds.CfnDBSubnetGroup(
            self,
            "ApnaSathiDBSubnetGroup",

            db_subnet_group_description=(
                "Private subnets for ApnaSathi PostgreSQL"
            ),

            subnet_ids=[
                private_subnet_a.ref,
                private_subnet_b.ref,
            ],

            tags=[
                {
                    "key": "Name",
                    "value": "apnasathi-db-subnet-group",
                },
                {
                    "key": "Project",
                    "value": "ApnaSathiAI",
                },
            ],
        )

        # ==========================================
        # 2. RDS POSTGRESQL DATABASE
        # ==========================================

        self.database = rds.CfnDBInstance(
            self,
            "ApnaSathiDatabase",

            db_instance_identifier="apnasathi-dev-db",

            engine="postgres",
            engine_version="17.12",
            db_instance_class="db.t4g.micro",

            db_name="apnasathi",
            master_username="apnasathi_admin",

            # AWS generates and manages the password
            manage_master_user_password=True,

            # Storage
            allocated_storage=20,
            max_allocated_storage=100,
            storage_type="gp3",
            storage_encrypted=True,

            # Network
            db_subnet_group_name=self.db_subnet_group.ref,
            vpc_security_groups=[
                rds_security_group.attr_group_id
            ],
            publicly_accessible=False,
            port="5432",

            # Development configuration
            multi_az=False,
            backup_retention_period=1,
            auto_minor_version_upgrade=True,
            deletion_protection=False,
            copy_tags_to_snapshot=True,

            tags=[
                {
                    "key": "Name",
                    "value": "apnasathi-dev-db",
                },
                {
                    "key": "Project",
                    "value": "ApnaSathiAI",
                },
                {
                    "key": "Environment",
                    "value": "dev",
                },
            ],
        )

        # Ensure subnet group is created first
        self.database.add_dependency(
            self.db_subnet_group
        )

        # Preserve database using a final snapshot
        self.database.apply_removal_policy(
            RemovalPolicy.SNAPSHOT
        )

        # ==========================================
        # 3. CLOUDFORMATION OUTPUTS
        # ==========================================

        CfnOutput(
            self,
            "DatabaseIdentifier",
            value=self.database.db_instance_identifier,
        )

        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=self.database.attr_endpoint_address,
        )

        CfnOutput(
            self,
            "DatabasePort",
            value=self.database.attr_endpoint_port,
        )

        CfnOutput(
            self,
            "DatabaseName",
            value="apnasathi",
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=(
                self.database
                .attr_master_user_secret_secret_arn
            ),
        )
