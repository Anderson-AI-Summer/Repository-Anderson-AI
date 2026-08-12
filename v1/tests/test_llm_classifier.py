import json
import os
import unittest
from unittest.mock import MagicMock, patch

from spend_agent.llm_classifier import classify_with_llm, is_available
from spend_agent.taxonomy import Category, UNCATEGORIZED


class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


def fake_client(response_payload):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(
        content=[FakeTextBlock(json.dumps(response_payload))]
    )
    return client


class TestClassifyWithLlm(unittest.TestCase):
    def setUp(self):
        self.taxonomy = [
            Category(name="Office Supplies", keywords=["staples"]),
            Category(name="Software", keywords=["saas"]),
        ]

    def test_returns_category_from_valid_response(self):
        client = fake_client({"category": "Software", "reasoning": "It's a SaaS renewal."})
        result = classify_with_llm("Acme Corp", "annual subscription", self.taxonomy, client=client)
        self.assertIsNotNone(result)
        self.assertEqual(result.category, "Software")
        self.assertEqual(result.reasoning, "It's a SaaS renewal.")

    def test_model_may_honestly_decline_to_categorize(self):
        client = fake_client({"category": UNCATEGORIZED, "reasoning": "No clear fit."})
        result = classify_with_llm("Mystery LLC", "misc charge", self.taxonomy, client=client)
        self.assertEqual(result.category, UNCATEGORIZED)

    def test_rejects_category_not_in_taxonomy(self):
        client = fake_client({"category": "Not A Real Category", "reasoning": "??"})
        result = classify_with_llm("Acme Corp", "widgets", self.taxonomy, client=client)
        self.assertIsNone(result)

    def test_returns_none_on_malformed_json(self):
        client = MagicMock()
        client.messages.create.return_value = MagicMock(content=[FakeTextBlock("not json")])
        result = classify_with_llm("Acme Corp", "widgets", self.taxonomy, client=client)
        self.assertIsNone(result)

    def test_returns_none_when_api_call_raises(self):
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("network error")
        result = classify_with_llm("Acme Corp", "widgets", self.taxonomy, client=client)
        self.assertIsNone(result)

    def test_returns_none_when_no_text_block_present(self):
        client = MagicMock()
        client.messages.create.return_value = MagicMock(content=[])
        result = classify_with_llm("Acme Corp", "widgets", self.taxonomy, client=client)
        self.assertIsNone(result)


class TestIsAvailable(unittest.TestCase):
    def test_false_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_available())

    def test_true_with_package_and_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            self.assertTrue(is_available())

    def test_false_without_anthropic_package(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.dict("sys.modules", {"anthropic": None}):
                self.assertFalse(is_available())


if __name__ == "__main__":
    unittest.main()
