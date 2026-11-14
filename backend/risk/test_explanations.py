
import unittest

from backend.risk.feature_engineering import build_feature_table
from backend.risk.predictor import RiskPredictor

import networkx as nx


class TestRiskExplanations(unittest.TestCase):

    def test_predictions_include_explanations(self):
        analysis = [
            {
                "file": "auth.py",
                "imports": ["database"],
                "functions": [
                    {
                        "name": "login",
                        "line": 1,
                        "end_line": 5,
                        "calls": ["check_password"],
                        "source": """def login(username, password):
    if check_password(password):
        return create_session(username)
    return None
""",
                    },
                    {
                        "name": "check_password",
                        "line": 7,
                        "end_line": 8,
                        "calls": [],
                        "source": """def check_password(password):
    return password == "admin"
""",
                    },
                ],
                "classes": [],
                "loc": 8,
            }
        ]

        graph = nx.DiGraph()

        graph.add_node("auth.py")
        graph.add_node("auth.py:login")
        graph.add_node("auth.py:check_password")

        graph.add_edge(
            "auth.py",
            "auth.py:login",
            relation="CONTAINS",
        )

        graph.add_edge(
            "auth.py",
            "auth.py:check_password",
            relation="CONTAINS",
        )

        graph.add_edge(
            "auth.py:login",
            "auth.py:check_password",
            relation="CALLS",
        )

        features = build_feature_table(analysis, graph)

        predictor = RiskPredictor()
        results = predictor.predict(features)

        self.assertEqual(len(results), 2)

        for result in results:
            self.assertTrue(
                any(
                    key in result
                    for key in ("reasons", "summary", "factors")
                ),
                f"No explanation fields found: {list(result.keys())}",
            )


if __name__ == "__main__":
    unittest.main()
