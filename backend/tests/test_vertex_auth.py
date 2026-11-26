import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from google.auth.exceptions import RefreshError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_model import llm_model, vertex_auth

CONFIG = {
    "type": "external_account",
    "audience": "//iam.googleapis.com/projects/1234/locations/global/workloadIdentityPools/test-pool/providers/test-aws",
    "subject_token_type": "urn:ietf:params:aws:token-type:aws4_request",
    "token_url": "https://sts.googleapis.com/v1/token",
    "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/test@project.iam.gserviceaccount.com:generateAccessToken",
}


class VertexAuthTests(unittest.TestCase):
    def setUp(self):
        vertex_auth.get_vertex_client.cache_clear()
        self.addCleanup(vertex_auth.get_vertex_client.cache_clear)

    def test_local_client_uses_adc_and_caches_initialization(self):
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=True):
            with patch.object(vertex_auth.genai, "Client") as client:
                self.assertIs(vertex_auth.get_vertex_client(), vertex_auth.get_vertex_client())
                client.assert_called_once()
                self.assertTrue(client.call_args.kwargs["vertexai"])
                self.assertNotIn("credentials", client.call_args.kwargs)

    def test_ecs_has_no_adc_fallback(self):
        with patch.dict("os.environ", {"GOOGLE_CLOUD_PROJECT": "test-project",
                                      "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/task"}, clear=True):
            with self.assertRaises(vertex_auth.VertexConfigurationError):
                vertex_auth.get_vertex_client()

    def test_federation_rejects_untrusted_token_destination(self):
        config = {**CONFIG, "token_url": "https://example.test/token"}
        with self.assertRaises(vertex_auth.VertexConfigurationError):
            vertex_auth.ecs_google_credentials(json.dumps(config), "ap-south-1")

    def test_uses_container_role_to_sign_subject_token(self):
        frozen = SimpleNamespace(access_key="test-key", secret_key="test-secret", token="test-session")
        provider = SimpleNamespace(method="container-role", get_frozen_credentials=lambda: frozen)
        with patch.object(vertex_auth.boto3, "Session") as session:
            session.return_value.get_credentials.return_value = provider
            credentials = vertex_auth.ecs_google_credentials(json.dumps(CONFIG), "ap-south-1")
            token = credentials.retrieve_subject_token(None)
            self.assertIn("sts.ap-south-1.amazonaws.com", token)
            provider.method = "env"
            supplier = vertex_auth.EcsTaskCredentials("ap-south-1")
            with self.assertRaises(RefreshError):
                supplier.get_aws_security_credentials(None, None)

    def test_vertex_failure_is_sanitized_and_shopping_can_retry(self):
        with patch.object(llm_model, "get_vertex_client", side_effect=RuntimeError("sensitive upstream detail")):
            with self.assertRaises(llm_model.VertexUnavailable) as error:
                llm_model.classify_intent("sample")
            self.assertNotIn("sensitive", str(error.exception))
            self.assertEqual(llm_model.extract_shopping_items("sample"), [])
