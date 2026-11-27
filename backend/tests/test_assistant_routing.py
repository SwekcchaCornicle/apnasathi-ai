import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.assistant import is_action_request


class AssistantRoutingTests(unittest.TestCase):
    def test_english_actions_bypass_semantic_reuse(self):
        for message in ["open Instagram", "use WhatsApp", "send this message", "order milk", "book a cab", "post this photo"]:
            with self.subTest(message=message):
                self.assertTrue(is_action_request(message))

    def test_hindi_actions_bypass_semantic_reuse(self):
        for message in ["इंस्टाग्राम खोलो", "मुझे दूध मंगाओ", "मैसेज भेजो", "फोटो पोस्ट करो"]:
            with self.subTest(message=message):
                self.assertTrue(is_action_request(message))

    def test_informational_questions_can_use_semantic_reuse(self):
        self.assertFalse(is_action_request("What is cloud computing?"))
        self.assertFalse(is_action_request("क्लाउड कंप्यूटिंग क्या है?"))


if __name__ == "__main__":
    unittest.main()
