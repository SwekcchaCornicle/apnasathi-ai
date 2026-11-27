import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from embeddings import e5
from services import answer_reuse


class FakeEmbeddingModel:
    def __init__(self):
        self.inputs = []

    def embed(self, texts):
        values = list(texts)
        self.inputs.extend(values)
        yield [3.0] + [0.0] * 767


class E5EmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeEmbeddingModel()
        self.model_patch = patch.object(e5, "_model", return_value=self.fake)
        self.model_patch.start()
        self.addCleanup(self.model_patch.stop)

    def test_query_prefix_and_normalization(self):
        vector = e5.embed_query("  नमस्ते  ")
        self.assertEqual(self.fake.inputs, ["query: नमस्ते"])
        self.assertEqual(len(vector), 768)
        self.assertEqual(vector[0], 1.0)

    def test_passage_prefix_and_normalization(self):
        vector = e5.embed_passage("Question: hello\\nAnswer: hi")
        self.assertEqual(self.fake.inputs, ["passage: Question: hello\\nAnswer: hi"])
        self.assertEqual(len(vector), 768)
        self.assertEqual(vector[0], 1.0)

    def test_empty_input_is_rejected(self):
        with self.assertRaises(ValueError):
            e5.embed_query("  ")

    def test_wrong_dimensions_fail_closed(self):
        with patch.object(e5, "_model") as model:
            model.return_value.embed.return_value = iter([[0.1, 0.2]])
            with self.assertRaisesRegex(RuntimeError, "expected 768"):
                e5.embed_query("hello")


class AnswerReusePolicyTests(unittest.TestCase):
    def test_question_normalization(self):
        self.assertEqual(answer_reuse.normalize_question("  How\\n  ARE   you? "), "how are you?")

    def test_action_intents_are_never_reused(self):
        db = Mock()
        with patch.object(answer_reuse, "embed_query") as embed:
            result = answer_reuse.find_reusable_answer(db, user_id=__import__("uuid").uuid4(), question="buy rice", intent="ORDER_GROCERIES")
        self.assertIsNone(result)
        embed.assert_not_called()
        db.execute.assert_not_called()

    def test_only_high_quality_general_question_can_be_stored(self):
        db = Mock()
        with self.assertRaises(ValueError):
            answer_reuse.store_approved_answer(db, user_id=__import__("uuid").uuid4(), question="Buy rice", answer="Order initiated", intent="ORDER_GROCERIES", quality_score=1.0)
        with self.assertRaises(ValueError):
            answer_reuse.store_approved_answer(db, user_id=__import__("uuid").uuid4(), question="What is X?", answer="Answer", intent="GENERAL_QUESTION", quality_score=0.5)
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
