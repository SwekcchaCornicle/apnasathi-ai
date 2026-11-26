from aws_cdk import (
    CfnOutput,
    Stack,
    aws_apigateway as apigateway,
    aws_s3 as s3,
)
from constructs import Construct


class ApnaSathiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        apna_sathi_bucket = s3.Bucket(
            self,
            "ApnaSathiBucket",
            enforce_ssl=True,
        )

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
