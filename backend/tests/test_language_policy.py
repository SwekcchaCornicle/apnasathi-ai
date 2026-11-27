import sys
import unittest
from pathlib import Path
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.persistence import LANGUAGE_NOTICE, require_supported_language


class LanguagePolicyTests(unittest.TestCase):
    def test_english_and_hindi_are_supported(self):
        self.assertEqual(require_supported_language("en"), "en")
        self.assertEqual(require_supported_language("hi"), "hi")

    def test_regional_variants_normalize_to_supported_base_language(self):
        self.assertEqual(require_supported_language("hi-IN"), "hi")
        self.assertEqual(require_supported_language("en-IN"), "en")

    def test_other_languages_return_launch_notice(self):
        with self.assertRaises(HTTPException) as error:
            require_supported_language("bn")
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(error.exception.detail["code"], "LANGUAGE_NOT_AVAILABLE")
        self.assertEqual(error.exception.detail["message"], LANGUAGE_NOTICE)
        self.assertEqual(error.exception.detail["supported_languages"], ["en", "hi"])


if __name__ == "__main__":
    unittest.main()
