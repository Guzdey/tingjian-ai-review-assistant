from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(PIPELINE))

import hf_range_sample  # noqa: E402


class FakeResponse:
    def __init__(self, *, status: int, headers: dict[str, str], body: bytes):
        self.status = status
        self.headers = headers
        self.body = body
        self.read_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, amount: int) -> bytes:
        self.read_called = True
        return self.body[:amount]


class RangeSamplerTests(unittest.TestCase):
    def test_valid_partial_response_is_bounded(self):
        response = FakeResponse(
            status=206,
            headers={"Content-Range": "bytes 10-13/100", "Content-Length": "4"},
            body=b"test",
        )
        with patch.object(hf_range_sample.urllib.request, "urlopen", return_value=response):
            payload = hf_range_sample.bounded_range("https://example.test/data", 10, 4, 100, 1)
        self.assertEqual(payload, b"test")
        self.assertTrue(response.read_called)

    def test_non_partial_response_is_rejected_before_body_read(self):
        response = FakeResponse(
            status=200,
            headers={"Content-Length": "100"},
            body=b"x" * 100,
        )
        with patch.object(hf_range_sample.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(hf_range_sample.RangeSafetyError):
                hf_range_sample.bounded_range("https://example.test/data", 10, 4, 100, 1)
        self.assertFalse(response.read_called)

    def test_private_projection_drops_reviewer_and_images(self):
        output = hf_range_sample.sanitized(
            "demo-tws-a",
            {
                "parent_asin": "B000TEST",
                "text": "Useful review",
                "user_id": "private-user",
                "images": ["private-image"],
            },
        )
        self.assertNotIn("user_id", output)
        self.assertNotIn("images", output)
        self.assertEqual(output["product_id"] if "product_id" in output else output["_product_id"], "demo-tws-a")


if __name__ == "__main__":
    unittest.main()
