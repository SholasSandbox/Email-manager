import unittest
from pathlib import Path

from email_core import PolicyAction, load_policy, parse_policy


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class PolicyLoaderTests(unittest.TestCase):
    def test_loads_sample_policy(self):
        policy = load_policy(FIXTURES_DIR / "sample_policy.json")

        self.assertEqual(policy.name, "sample-inbox-policy")
        self.assertEqual(policy.version, "1.0")
        self.assertEqual(len(policy.rules), 2)
        self.assertEqual(policy.rules[0].actions[0].type, "archive")
        self.assertEqual(policy.rules[1].actions[0].params["label"], "Review/Updates")

    def test_rejects_unsupported_action(self):
        with self.assertRaises(ValueError):
            PolicyAction("launch_provider_oauth")

    def test_requires_rule_actions(self):
        with self.assertRaises(ValueError):
            parse_policy(
                {
                    "name": "bad-policy",
                    "version": "1.0",
                    "rules": [
                        {
                            "name": "empty-rule",
                            "criteria": {},
                            "actions": [],
                        }
                    ],
                }
            )

    def test_requires_rules_list(self):
        with self.assertRaises(TypeError):
            parse_policy({"name": "bad-policy", "version": "1.0", "rules": {}})


if __name__ == "__main__":
    unittest.main()
