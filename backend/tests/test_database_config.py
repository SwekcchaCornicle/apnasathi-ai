import json
import os
import unittest
from unittest.mock import patch

from sqlalchemy.engine import URL

from database.session import _database_url


class DatabaseConfigurationTests(unittest.TestCase):
    def test_builds_url_from_rds_secret(self):
        secret = {"username": "app_user", "password": "p@ss/word", "host": "db.example.test", "port": 5432, "dbname": "apnasathi"}
        with patch.dict(os.environ, {"DATABASE_CREDENTIALS": json.dumps(secret), "DB_SSL": "true"}, clear=True):
            url = _database_url()
        self.assertIsInstance(url, URL)
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.username, "app_user")
        self.assertEqual(url.password, "p@ss/word")
        self.assertEqual(url.database, "apnasathi")
        self.assertEqual(url.query["sslmode"], "require")

    def test_direct_url_is_supported(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+psycopg://user:pass@localhost/apnasathi"}, clear=True):
            self.assertEqual(_database_url(), "postgresql+psycopg://user:pass@localhost/apnasathi")

    def test_missing_configuration_fails_clearly(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Database is not configured"):
                _database_url()


if __name__ == "__main__":
    unittest.main()
