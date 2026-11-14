
import unittest

from backend.risk.feature_engineering import build_feature_table
from backend.risk.predictor import RiskPredictor

import networkx as nx


class TestRiskPredictor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.analysis = [
            {
                "file": "auth.py",
                "imports": ["database"],
                "functions": [
                    {
                        "name": "login",
                        "line": 1,
                        "end_line": 12,
                        "calls": ["check_password"],
                        "source": """def login(username, password):
    user = get_user(username)
    if user:
        if check_password(password):
            return create_session(user)
    return None
""",
                    },
                    {
                        "name": "check_password",
                        "line": 14,
                        "end_line": 16,
                        "calls": [],
                        "source": """def check_password(password):
    return password == "admin"
""",
                    },
                ],
                "classes": [],
                "loc": 16,
            }
        ]

        cls.graph = nx.DiGraph()

        cls.graph.add_node("auth.py")
        cls.graph.add_node("auth.py:login")
        cls.graph.add_node("auth.py:check_password")

        cls.graph.add_edge(
            "auth.py",
            "auth.py:login",
            relation="CONTAINS",
        )

        cls.graph.add_edge(
            "auth.py",
            "auth.py:check_password",
            relation="CONTAINS",
        )

        cls.graph.add_edge(
            "auth.py:login",
            "auth.py:check_password",
            relation="CALLS",
        )

        cls.features = build_feature_table(
            cls.analysis,
            cls.graph,
        )

        cls.predictor = RiskPredictor()

    def test_predicts_all_functions(self):
        results = self.predictor.predict(self.features)
        self.assertEqual(len(results), 2)

    def test_prediction_fields(self):
        results = self.predictor.predict(self.features)

        for result in results:
            self.assertIn("risk_probability", result)
            self.assertIn("risk_index", result)
            self.assertIn("risk_score", result)
            self.assertIn("risk_level", result)
            self.assertIn("id", result)
            self.assertIn("file", result)

    def test_probability_range(self):
        results = self.predictor.predict(self.features)

        for result in results:
            self.assertGreaterEqual(
                result["risk_probability"], 0.0
            )
            self.assertLessEqual(
                result["risk_probability"], 1.0
            )

    def test_risk_index_matches_probability(self):
        results = self.predictor.predict(self.features)

        for result in results:
            self.assertEqual(
                result["risk_index"],
                round(result["risk_probability"] * 100, 2),
            )

    def test_risk_levels(self):
        results = self.predictor.predict(self.features)

        for result in results:
            self.assertIn(
                result["risk_level"],
                ["Low", "Medium", "High"],
            )

    def test_empty_input(self):
        self.assertEqual(self.predictor.predict([]), [])


if __name__ == "__main__":
    unittest.main()
