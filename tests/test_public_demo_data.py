from __future__ import annotations

import unittest

from pipeline.validate_public_data import validate_public_fixture


class PublicDemoDataTest(unittest.TestCase):
    def test_fixture_is_explicitly_synthetic_and_complete(self) -> None:
        summary = validate_public_fixture()
        self.assertEqual(summary["products"], 2)
        self.assertEqual(summary["evidence"], 36)
        self.assertEqual(summary["coverage_cells"], 12)


if __name__ == "__main__":
    unittest.main()
