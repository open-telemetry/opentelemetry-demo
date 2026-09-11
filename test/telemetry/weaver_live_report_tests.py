# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import unittest

from check_weaver_live_report import validate_report


CONTRACT = {
    "expected": {
        "attributes": ["demo.product.id", "demo.order.id"],
        "metrics": ["demo.cart.add_item.latency"],
    }
}


def report(attributes=None, metrics=None, spans=1, violations=0):
    return {
        "statistics": {
            "total_entities_by_type": {"span": spans},
            "advice_level_counts": {"violation": violations},
            "seen_registry_attributes": attributes or {},
            "seen_registry_metrics": metrics or {},
        }
    }


class ValidateReportTest(unittest.TestCase):
    def test_complete_contract_passes(self):
        errors = validate_report(
            CONTRACT,
            report(
                attributes={"demo.product.id": 2, "demo.order.id": 1},
                metrics={"demo.cart.add_item.latency": 1},
            ),
        )

        self.assertEqual([], errors)

    def test_empty_report_fails(self):
        errors = validate_report(CONTRACT, report(spans=0))

        self.assertIn("Weaver did not observe any spans", errors)

    def test_missing_attribute_fails(self):
        errors = validate_report(
            CONTRACT,
            report(
                attributes={"demo.product.id": 1},
                metrics={"demo.cart.add_item.latency": 1},
            ),
        )

        self.assertIn("Missing expected attributes: demo.order.id", errors)

    def test_missing_metric_fails(self):
        errors = validate_report(
            CONTRACT,
            report(
                attributes={"demo.product.id": 1, "demo.order.id": 1},
            ),
        )

        self.assertIn(
            "Missing expected metrics: demo.cart.add_item.latency",
            errors,
        )

    def test_weaver_violation_fails(self):
        errors = validate_report(
            CONTRACT,
            report(
                attributes={"demo.product.id": 1, "demo.order.id": 1},
                metrics={"demo.cart.add_item.latency": 1},
                violations=2,
            ),
        )

        self.assertIn("Weaver reported 2 violation(s)", errors)


if __name__ == "__main__":
    unittest.main()
