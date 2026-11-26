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
        # A synthetic account and certificate let CloudFormation templates synthesize offline.
        context = {
            "certificateArn": "arn:aws:acm:ap-south-1:111111111111:certificate/00000000-0000-0000-0000-000000000000",
            "backendDesiredCount": "1",
            "backendImageTag": "preflight-arm64",
        }
        from aws_cdk import App

        with TemporaryDirectory() as directory, patch.dict(os.environ, {"CDK_DEFAULT_ACCOUNT": "111111111111"}):
            with patch("aws_cdk.App", side_effect=lambda: App(context=context, outdir=directory)):
                runpy.run_path(str(STACKS / "app.py"), run_name="__main__")
            cls.templates = {
                name: json.loads((Path(directory) / f"ApnaSathi{name}Stack.template.json").read_text(encoding="utf-8"))
                for name in ("Infrastructure", "Application", "Network", "Database")
            }

    def resources(self, stack, kind):
        return {
            key: value for key, value in self.templates[stack]["Resources"].items()
            if value["Type"] == kind
        }

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

    def test_first_service_rollout_configuration(self):
        service = next(iter(self.resources("Application", "AWS::ECS::Service").values()))["Properties"]
        self.assertEqual(service["DesiredCount"], 1)
        target = next(iter(self.resources("Application", "AWS::ElasticLoadBalancingV2::TargetGroup").values()))
        self.assertEqual(target["Properties"]["HealthCheckPath"], "/api/v1/health")
        task = next(iter(self.resources("Application", "AWS::ECS::TaskDefinition").values()))["Properties"]
        self.assertEqual(task["RuntimePlatform"]["CpuArchitecture"], "ARM64")
        self.assertIn(":preflight-arm64", json.dumps(task["ContainerDefinitions"][0]["Image"]))
