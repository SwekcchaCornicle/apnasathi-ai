import json
import os
import runpy
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

STACKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STACKS))


class AudioInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use an offline account fixture and no certificate context.
        context = {
            "backendDesiredCount": "1",
            "backendImageTag": "preflight-arm64",
            "cognitoUserPoolId": "ap-south-1_PoolFixture",
            "cognitoClientId": "clientfixture",
            "instagramSecretArn": "arn:aws:secretsmanager:ap-south-1:111111111111:secret:instagram-Ab12Cd",
            "instagramSecretJsonKey": "App secret",
            "instagramApiVersion": "v25.0",
            "instagramImageOrigin": "https://example.test",
            "googleCloudProject": "example-project",
            "googleWifSecretArn": "arn:aws:secretsmanager:ap-south-1:111111111111:secret:vertex-config-Ab12Cd",
        }
        from aws_cdk import App

        with TemporaryDirectory() as directory, patch.dict(os.environ, {"CDK_DEFAULT_ACCOUNT": "111111111111"}):
            with patch("aws_cdk.App", side_effect=lambda: App(context=context, outdir=directory)):
                runpy.run_path(str(STACKS / "app.py"), run_name="__main__")
            cls.templates = {
                name: json.loads((Path(directory) / f"ApnaSathi{name}Stack.template.json").read_text(encoding="utf-8"))
                for name in ("Infrastructure", "Application", "Network", "Database")
            }

        with TemporaryDirectory() as directory, patch.dict(os.environ, {"CDK_DEFAULT_ACCOUNT": "111111111111"}):
            with patch("aws_cdk.App", side_effect=lambda: App(context={**context, "networkEgress": "nat"}, outdir=directory)):
                runpy.run_path(str(STACKS / "app.py"), run_name="__main__")
            cls.nat_network = json.loads((Path(directory) / "ApnaSathiNetworkStack.template.json").read_text(encoding="utf-8"))

    def resources(self, stack, kind):
        return {
            key: value for key, value in self.templates[stack]["Resources"].items()
            if value["Type"] == kind
        }

    def test_instagram_reads_the_selected_json_field(self):
        [task] = self.resources("Application", "AWS::ECS::TaskDefinition").values()
        [container] = task["Properties"]["ContainerDefinitions"]
        secrets = {entry["Name"]: entry["ValueFrom"] for entry in container["Secrets"]}
        self.assertEqual(
            secrets["INSTAGRAM_APP_SECRET"],
            "arn:aws:secretsmanager:ap-south-1:111111111111:secret:instagram-Ab12Cd:App secret::",
        )

    def test_ecs_can_receive_public_cognito_configuration(self):
        tasks = self.resources("Application", "AWS::ECS::TaskDefinition")
        [task] = tasks.values()
        [container] = task["Properties"]["ContainerDefinitions"]
        env = {item["Name"]: item["Value"] for item in container["Environment"]}
        self.assertEqual(env["COGNITO_REGION"], "ap-south-1")
        self.assertEqual(env["COGNITO_USER_POOL_ID"], "ap-south-1_PoolFixture")
        self.assertEqual(env["COGNITO_CLIENT_ID"], "clientfixture")
        self.assertNotIn("COGNITO_CLIENT_SECRET", env)

    def test_audio_bucket_security_and_retention(self):
        buckets = self.resources("Infrastructure", "AWS::S3::Bucket")
        self.assertEqual(len(buckets), 2)
        name, bucket = next((name, value) for name, value in buckets.items() if name.startswith("AudioRecordingsBucket"))
        properties = bucket["Properties"]
        self.assertNotIn("BucketName", properties)
        self.assertNotIn("WebsiteConfiguration", properties)
        self.assertNotIn("LifecycleConfiguration", properties)
        self.assertNotIn("VersioningConfiguration", properties)
        self.assertEqual(bucket["DeletionPolicy"], "Retain")
        self.assertEqual(bucket["UpdateReplacePolicy"], "Retain")
        self.assertEqual(properties["PublicAccessBlockConfiguration"], {
            "BlockPublicAcls": True, "BlockPublicPolicy": True,
            "IgnorePublicAcls": True, "RestrictPublicBuckets": True,
        })
        self.assertEqual(properties["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
                         ["ServerSideEncryptionByDefault"]["SSEAlgorithm"], "AES256")
        for policy in self.resources("Infrastructure", "AWS::S3::BucketPolicy").values():
            if policy["Properties"]["Bucket"] == {"Ref": name}:
                statements = policy["Properties"]["PolicyDocument"]["Statement"]
                self.assertTrue(any(statement["Effect"] == "Deny" and
                                    statement["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}
                                    for statement in statements))
                break
        else:
            self.fail("The audio bucket has no HTTPS-only policy")
        exports = self.templates["Infrastructure"]["Outputs"]
        self.assertEqual(exports["AudioBucketName"]["Export"]["Name"], "ApnaSathiDevAudioBucketName")
        self.assertEqual(exports["AudioBucketArn"]["Export"]["Name"], "ApnaSathiDevAudioBucketArn")
        self.assertTrue(self.resources("Infrastructure", "AWS::ApiGateway::RestApi"))

    def test_s3_permissions_apply_to_the_task_role_only(self):
        roles = self.resources("Application", "AWS::IAM::Role")
        task_role = next(name for name in roles if name.startswith("BackendTaskRole"))
        execution_role = next(name for name in roles if name.startswith("BackendExecutionRole"))
        policies = self.resources("Application", "AWS::IAM::Policy")
        s3_statements = []
        for policy in policies.values():
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
                actions = statement["Action"]
                actions = [actions] if isinstance(actions, str) else actions
                if any(action.startswith("s3:") for action in actions):
                    self.assertEqual(policy["Properties"]["Roles"], [{"Ref": task_role}])
                    s3_statements.append(statement)
        self.assertEqual(len(s3_statements), 1)
        self.assertEqual(set(s3_statements[0]["Action"]), {"s3:GetObject", "s3:PutObject"})
        self.assertIn("AudioRecordingsBucket", json.dumps(s3_statements[0]["Resource"]))
        self.assertIn("/audio/*", json.dumps(s3_statements[0]["Resource"]))
        task = next(iter(self.resources("Application", "AWS::ECS::TaskDefinition").values()))["Properties"]
        self.assertEqual(task["TaskRoleArn"], {"Fn::GetAtt": [task_role, "Arn"]})
        self.assertEqual(task["ExecutionRoleArn"], {"Fn::GetAtt": [execution_role, "Arn"]})
        environment = {entry["Name"]: entry["Value"] for entry in task["ContainerDefinitions"][0]["Environment"]}
        self.assertIn("AudioRecordingsBucket", json.dumps(environment["AUDIO_S3_BUCKET"]))
        self.assertEqual(environment["AWS_REGION"], "ap-south-1")

    def test_both_private_subnets_share_the_gateway_endpoint_route_table(self):
        endpoints = self.resources("Network", "AWS::EC2::VPCEndpoint")
        gateway = next(endpoint["Properties"] for endpoint in endpoints.values()
                       if endpoint["Properties"]["VpcEndpointType"] == "Gateway")
        self.assertEqual(gateway["RouteTableIds"], [{"Ref": "PrivateRouteTable"}])
        associations = self.resources("Network", "AWS::EC2::SubnetRouteTableAssociation")
        private_subnets = {
            entry["Properties"]["SubnetId"]["Ref"] for entry in associations.values()
            if entry["Properties"]["RouteTableId"] == {"Ref": "PrivateRouteTable"}
        }
        self.assertEqual(private_subnets, {"PrivateSubnetA", "PrivateSubnetB"})
        self.assertFalse(self.resources("Network", "AWS::EC2::NatGateway"))

    def test_ecs_memory_autoscaling_matches_live_service(self):
        [target] = self.resources("Application", "AWS::ApplicationAutoScaling::ScalableTarget").values()
        self.assertEqual(target["Properties"]["MinCapacity"], 1)
        self.assertEqual(target["Properties"]["MaxCapacity"], 3)
        self.assertEqual(target["Properties"]["ScalableDimension"], "ecs:service:DesiredCount")
        [policy] = self.resources("Application", "AWS::ApplicationAutoScaling::ScalingPolicy").values()
        config = policy["Properties"]["TargetTrackingScalingPolicyConfiguration"]
        self.assertEqual(config, {
            "PredefinedMetricSpecification": {"PredefinedMetricType": "ECSServiceAverageMemoryUtilization"},
            "TargetValue": 65,
            "ScaleInCooldown": 300,
            "ScaleOutCooldown": 60,
        })

    def test_first_service_rollout_configuration(self):
        service = next(iter(self.resources("Application", "AWS::ECS::Service").values()))["Properties"]
        self.assertEqual(service["DesiredCount"], 1)
        target = next(iter(self.resources("Application", "AWS::ElasticLoadBalancingV2::TargetGroup").values()))
        self.assertEqual(target["Properties"]["HealthCheckPath"], "/api/v1/health")
        task = next(iter(self.resources("Application", "AWS::ECS::TaskDefinition").values()))["Properties"]
        self.assertEqual(task["RuntimePlatform"]["CpuArchitecture"], "ARM64")
        self.assertIn(":preflight-arm64", json.dumps(task["ContainerDefinitions"][0]["Image"]))

    def test_wif_config_uses_secret_and_health_probe(self):
        task = next(iter(self.resources("Application", "AWS::ECS::TaskDefinition").values()))["Properties"]
        backend = task["ContainerDefinitions"][0]
        env = {item["Name"]: item["Value"] for item in backend["Environment"]}
        secrets = {item["Name"]: item["ValueFrom"] for item in backend["Secrets"]}
        self.assertEqual(env["GOOGLE_CLOUD_PROJECT"], "example-project")
        self.assertNotIn("GOOGLE_WIF_CONFIG_JSON", env)
        self.assertTrue(secrets["GOOGLE_WIF_CONFIG_JSON"].endswith("vertex-config-Ab12Cd"))
        self.assertEqual(backend["StopTimeout"], 45)
        self.assertIn("/api/v1/health", backend["HealthCheck"]["Command"][-1])
        roles = self.resources("Application", "AWS::IAM::Role")
        execution = next(name for name in roles if name.startswith("BackendExecutionRole"))
        policies = self.resources("Application", "AWS::IAM::Policy")
        consumers = [
            policy["Properties"]["Roles"]
            for policy in policies.values()
            if "vertex-config-Ab12Cd" in json.dumps(policy["Properties"]["PolicyDocument"])
        ]
        self.assertEqual(consumers, [[{"Ref": execution}]])

    def test_nat_opt_in_only_changes_private_egress(self):
        resources = self.nat_network["Resources"]
        self.assertEqual(resources["DevelopmentNatGateway"]["Properties"]["SubnetId"], {"Ref": "PublicSubnetA"})
        route = resources["PrivateNatDefaultRoute"]["Properties"]
        self.assertEqual(route["NatGatewayId"], {"Ref": "DevelopmentNatGateway"})
        self.assertEqual(route["RouteTableId"], {"Ref": "PrivateRouteTable"})
        self.assertEqual(resources["S3GatewayEndpoint"]["Properties"]["RouteTableIds"], [{"Ref": "PrivateRouteTable"}])

    def test_http_listener_and_private_fargate(self):
        listeners = self.resources("Application", "AWS::ElasticLoadBalancingV2::Listener")
        self.assertEqual(len(listeners), 1)
        name, listener = next(iter(listeners.items()))
        props = listener["Properties"]
        self.assertEqual((props["Protocol"], props["Port"]), ("HTTP", 80))
        self.assertNotIn("Certificates", props)
        self.assertEqual(props["DefaultActions"], [
            {"Type": "forward", "TargetGroupArn": {"Ref": "BackendTargetGroup"}}
        ])
        service = next(iter(self.resources("Application", "AWS::ECS::Service").values()))
        self.assertIn(name, service["DependsOn"])
        config = service["Properties"]
        self.assertEqual(config["LoadBalancers"][0]["ContainerPort"], 8000)
        self.assertEqual(config["DeploymentConfiguration"]["DeploymentCircuitBreaker"],
                         {"Enable": True, "Rollback": True})
        vpc = config["NetworkConfiguration"]["AwsvpcConfiguration"]
        self.assertEqual(vpc["AssignPublicIp"], "DISABLED")
        self.assertEqual(len(vpc["Subnets"]), 2)
        self.assertTrue(all("PrivateSubnet" in json.dumps(subnet) for subnet in vpc["Subnets"]))
        groups = self.resources("Network", "AWS::EC2::SecurityGroup")
        backend_ingress = groups["BackendSecurityGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual(len(backend_ingress), 1)
        self.assertEqual(backend_ingress[0]["FromPort"], 8000)
        self.assertEqual(backend_ingress[0]["SourceSecurityGroupId"], {"Fn::GetAtt": ["ALBSecurityGroup", "GroupId"]})
        alb_ingress = groups["ALBSecurityGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual([rule["FromPort"] for rule in alb_ingress], [80])
