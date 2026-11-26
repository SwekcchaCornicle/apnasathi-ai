from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    Tags,
    aws_apigateway as apigateway,
    aws_s3 as s3,
)
from constructs import Construct


class InfrastructureStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        apna_sathi_bucket = s3.Bucket(
            self,
            "ApnaSathiBucket",
            enforce_ssl=True,
        )

        self.audio_bucket = s3.Bucket(
            self,
            "AudioRecordingsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        Tags.of(self.audio_bucket).add("Project", "ApnaSathiAI")
        Tags.of(self.audio_bucket).add("Environment", "dev")
        Tags.of(self.audio_bucket).add("Purpose", "AudioRecordings")
        CfnOutput(self, "AudioBucketName", value=self.audio_bucket.bucket_name,
                  export_name="ApnaSathiDevAudioBucketName")
        CfnOutput(self, "AudioBucketArn", value=self.audio_bucket.bucket_arn,
                  export_name="ApnaSathiDevAudioBucketArn")

        api = apigateway.RestApi(
            self,
            "ApnaSathiRestApi",
            rest_api_name="apna-sathi-api",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=["POST", "OPTIONS"],
                allow_headers=["Content-Type"],
            ),
        )

        # Lambda resources and the API integration are disabled for now.
        # from aws_cdk import aws_lambda as _lambda
        # apna_sathi_lambda = _lambda.Function(
        #     self,
        #     "ApnaSathiLambda",
        #     function_name="apna-sathi-lambda",
        #     runtime=_lambda.Runtime.PYTHON_3_12,
        #     handler="apna_sathi_lambda.lambda_handler",
        #     code=_lambda.Code.from_asset("lambdas/apna_sathi_lambda"),
        # )
        # playlist_resource = api.root.add_resource("playlist")
        # playlist_resource.add_method(
        #     "POST",
        #     apigateway.LambdaIntegration(apna_sathi_lambda),
        # )

        CfnOutput(self, "ApnaSathiApiUrl", value=api.url)
        CfnOutput(
            self,
            "ApnaSathiBucketName",
            value=apna_sathi_bucket.bucket_name,
        )
