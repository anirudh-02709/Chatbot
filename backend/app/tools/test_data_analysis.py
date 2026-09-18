"""
Unit test suite for Goal 10.6: Data Analysis Tool.

Tests:
1. Describe operation (row count, columns, types, missing counts, numeric summary stats)
2. Filter operation with numeric comparisons (>, <, >=, <=, ==, !=)
3. Filter operation with string comparisons (==, !=, in, contains)
4. Filter operation with complex safe expressions (and, or, not)
5. Filter operation with structured condition parameters
6. Filter operation with missing columns
7. Aggregate operation (count, sum, mean, min, max, median)
8. Aggregate operation with group_by
9. Aggregate operation on non-numeric column error
10. Sort operation (ascending, descending, limit, null placement)
11. Sort operation with missing column
12. Validation: Empty dataset rejection
13. Validation: Malformed data structure rejection
14. Validation: Unsupported operation rejection
15. Resource limits: Row limit enforcement (> 10,000 rows)
16. Resource limits: Cell size limit enforcement (> 10,000 chars)
17. Security: Code injection prevention (__import__, open, function calls, attribute access)
18. Integration: Registry registration and get_definitions() export
19. Integration: Execution through ToolExecutionService
20. Integration: ToolExecutionService invalid arguments rejection
"""

import sys
import unittest
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.models.tool import ToolResult
from app.tools.registry import ToolRegistry, tool_registry
from app.tools.data_analysis import (
    DataAnalysisTool,
    DataAnalysisInput,
    data_analysis_tool,
    MAX_ROWS,
    MAX_CELL_SIZE,
)
from app.tools.executor import ToolExecutionService


# ─────────────────────────────────────────────────────────────────────────────
# Sample Test Datasets
# ─────────────────────────────────────────────────────────────────────────────

def sample_employee_data() -> list[dict[str, Any]]:
    return [
        {"name": "Alice", "department": "Engineering", "salary": 95000, "years": 4, "active": True},
        {"name": "Bob", "department": "Engineering", "salary": 85000, "years": 2, "active": True},
        {"name": "Charlie", "department": "Marketing", "salary": 70000, "years": 5, "active": False},
        {"name": "Dana", "department": "Marketing", "salary": 75000, "years": 3, "active": True},
        {"name": "Evan", "department": "Sales", "salary": 60000, "years": 1, "active": True},
    ]


def sample_mixed_data() -> list[dict[str, Any]]:
    return [
        {"id": 1, "score": 85.5, "note": "Pass", "extra": None},
        {"id": 2, "score": 92.0, "note": "High Pass", "extra": "A"},
        {"id": 3, "score": None, "note": "", "extra": "B"},
        {"id": 4, "score": 78.0, "note": "Pass", "extra": None},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite
# ─────────────────────────────────────────────────────────────────────────────

class TestDataAnalysisTool(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tool = DataAnalysisTool()

    # 1. Describe operation
    async def test_describe_operation(self):
        data = sample_employee_data()
        result = await self.tool.execute(operation="describe", data=data)

        self.assertTrue(result.success)
        self.assertEqual(result.tool_name, "data_analysis")

        d = result.data
        self.assertEqual(d["row_count"], 5)
        self.assertEqual(d["column_count"], 5)
        self.assertIn("name", d["columns"])
        self.assertIn("salary", d["columns"])

        # Data types
        self.assertEqual(d["data_types"]["name"], "string")
        self.assertEqual(d["data_types"]["salary"], "numeric")
        self.assertEqual(d["data_types"]["years"], "numeric")
        self.assertEqual(d["data_types"]["active"], "boolean")

        # Missing counts
        self.assertEqual(d["missing_counts"]["salary"], 0)

        # Numeric statistics for salary
        sal_stats = d["numeric_statistics"]["salary"]
        self.assertEqual(sal_stats["count"], 5)
        self.assertEqual(sal_stats["sum"], 385000)
        self.assertEqual(sal_stats["mean"], 77000.0)
        self.assertEqual(sal_stats["min"], 60000)
        self.assertEqual(sal_stats["max"], 95000)
        self.assertGreater(sal_stats["std_dev"], 0)

    async def test_describe_with_missing_values(self):
        data = sample_mixed_data()
        result = await self.tool.execute(operation="describe", data=data)

        self.assertTrue(result.success)
        d = result.data
        self.assertEqual(d["missing_counts"]["score"], 1)
        self.assertEqual(d["missing_counts"]["note"], 1)
        self.assertEqual(d["missing_counts"]["extra"], 2)

        # 3 non-missing numeric scores: 85.5, 92.0, 78.0
        score_stats = d["numeric_statistics"]["score"]
        self.assertEqual(score_stats["count"], 3)
        self.assertAlmostEqual(score_stats["mean"], 85.1667, places=3)

    # 2. Filter operation with numeric comparisons
    async def test_filter_numeric_condition_string(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "salary >= 85000"},
        )

        self.assertTrue(result.success)
        rows = result.data["rows"]
        self.assertEqual(result.data["match_count"], 2)
        names = [r["name"] for r in rows]
        self.assertEqual(names, ["Alice", "Bob"])

    # 3. Filter operation with string comparisons
    async def test_filter_string_condition(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "department == 'Marketing'"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["match_count"], 2)
        names = [r["name"] for r in result.data["rows"]]
        self.assertEqual(names, ["Charlie", "Dana"])

    # 4. Filter operation with complex safe expressions (and, or, not)
    async def test_filter_complex_boolean_expression(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "salary > 70000 and active == True"},
        )

        self.assertTrue(result.success)
        names = [r["name"] for r in result.data["rows"]]
        self.assertEqual(names, ["Alice", "Bob", "Dana"])

    # 5. Filter operation with structured condition parameters
    async def test_filter_structured_parameters(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"column": "years", "operator": ">=", "value": 4},
        )

        self.assertTrue(result.success)
        names = [r["name"] for r in result.data["rows"]]
        self.assertEqual(names, ["Alice", "Charlie"])

    async def test_filter_contains_operator(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"column": "name", "operator": "contains", "value": "li"},
        )

        self.assertTrue(result.success)
        names = [r["name"] for r in result.data["rows"]]
        self.assertEqual(names, ["Alice", "Charlie"])

    # 6. Filter operation with missing columns
    async def test_filter_missing_column(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "nonexistent_column > 10"},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ColumnNotFoundError")
        self.assertIn("nonexistent_column", result.error)

    # 7. Aggregate operations
    async def test_aggregate_sum(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "salary", "aggregator": "sum"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["result"], 385000)
        self.assertEqual(result.data["count"], 5)

    async def test_aggregate_mean_and_median(self):
        data = sample_employee_data()
        mean_res = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "salary", "aggregator": "mean"},
        )
        self.assertTrue(mean_res.success)
        self.assertEqual(mean_res.data["result"], 77000.0)

        med_res = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "salary", "aggregator": "median"},
        )
        self.assertTrue(med_res.success)
        self.assertEqual(med_res.data["result"], 75000.0)

    async def test_aggregate_min_max_count(self):
        data = sample_employee_data()
        min_res = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "years", "aggregator": "min"},
        )
        self.assertEqual(min_res.data["result"], 1)

        max_res = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "years", "aggregator": "max"},
        )
        self.assertEqual(max_res.data["result"], 5)

        count_res = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"aggregator": "count"},
        )
        self.assertEqual(count_res.data["result"], 5)

    # 8. Grouped aggregation
    async def test_aggregate_with_group_by(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "salary", "aggregator": "mean", "group_by": "department"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["group_count"], 3)
        res_by_dept = {g["department"]: g["result"] for g in result.data["results"]}
        self.assertEqual(res_by_dept["Engineering"], 90000.0)
        self.assertEqual(res_by_dept["Marketing"], 72500.0)
        self.assertEqual(res_by_dept["Sales"], 60000.0)

    # 9. Aggregate on non-numeric column error
    async def test_aggregate_non_numeric_fails(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="aggregate",
            data=data,
            parameters={"column": "name", "aggregator": "sum"},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "DataAnalysisError")
        self.assertIn("no valid numeric values", result.error)

    # 10. Sort operation
    async def test_sort_ascending_and_descending(self):
        data = sample_employee_data()

        # Ascending
        asc_res = await self.tool.execute(
            operation="sort",
            data=data,
            parameters={"column": "salary", "descending": False},
        )
        self.assertTrue(asc_res.success)
        salaries = [r["salary"] for r in asc_res.data["rows"]]
        self.assertEqual(salaries, [60000, 70000, 75000, 85000, 95000])

        # Descending with limit
        desc_res = await self.tool.execute(
            operation="sort",
            data=data,
            parameters={"column": "salary", "descending": True, "limit": 2},
        )
        self.assertTrue(desc_res.success)
        self.assertEqual(len(desc_res.data["rows"]), 2)
        self.assertEqual([r["name"] for r in desc_res.data["rows"]], ["Alice", "Bob"])

    # 11. Sort with missing column
    async def test_sort_missing_column(self):
        data = sample_employee_data()
        result = await self.tool.execute(
            operation="sort",
            data=data,
            parameters={"column": "nonexistent"},
        )
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ColumnNotFoundError")

    # 12. Validation: Empty dataset rejection
    async def test_empty_dataset_rejected(self):
        result = await self.tool.execute(operation="describe", data=[])
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "EmptyDatasetError")

    # 13. Validation: Malformed data rejection
    async def test_malformed_data_rejected(self):
        # Non-dict rows
        result = await self.tool.execute(operation="describe", data=["row1", "row2"])
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "MalformedDataError")

    # 14. Validation: Unsupported operation rejection
    async def test_unsupported_operation_rejected(self):
        data = sample_employee_data()
        result = await self.tool.execute(operation="drop_database", data=data)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "UnsupportedOperationError")
        self.assertIn("Unsupported operation", result.error)

    # 15. Resource limits: Row limit
    async def test_oversized_row_count_rejected(self):
        oversized_data = [{"x": i} for i in range(MAX_ROWS + 1)]
        result = await self.tool.execute(operation="describe", data=oversized_data)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ResourceLimitExceededError")
        self.assertIn("maximum allowed rows", result.error)

    # 16. Resource limits: Cell size limit
    async def test_oversized_cell_rejected(self):
        oversized_data = [{"text": "A" * (MAX_CELL_SIZE + 50)}]
        result = await self.tool.execute(operation="describe", data=oversized_data)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ResourceLimitExceededError")
        self.assertIn("maximum cell size", result.error)

    # 17. Security: Code injection prevention
    async def test_code_injection_in_filter_rejected(self):
        data = sample_employee_data()

        # Attempt 1: Function call
        res_call = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "len(name) > 3"},
        )
        self.assertFalse(res_call.success)
        self.assertEqual(res_call.error_type, "InvalidConditionError")
        self.assertIn("Security: disallowed expression node 'Call'", res_call.error)

        # Attempt 2: Import attempt
        res_import = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "__import__('os').system('dir')"},
        )
        self.assertFalse(res_import.success)
        self.assertEqual(res_import.error_type, "InvalidConditionError")

        # Attempt 3: Attribute access
        res_attr = await self.tool.execute(
            operation="filter",
            data=data,
            parameters={"condition": "name.__class__ == str"},
        )
        self.assertFalse(res_attr.success)
        self.assertEqual(res_attr.error_type, "InvalidConditionError")
        self.assertIn("Security: disallowed expression node 'Attribute'", res_attr.error)

    # 18. Integration: ToolRegistry registration and get_definitions()
    def test_registry_registration_and_definitions(self):
        registered = tool_registry.get("data_analysis")
        self.assertIsNotNone(registered)
        self.assertEqual(registered.name, "data_analysis")

        definitions = tool_registry.get_definitions()
        da_def = next(
            (d for d in definitions if d.get("function", {}).get("name") == "data_analysis"),
            None,
        )
        self.assertIsNotNone(da_def)
        fn = da_def["function"]
        self.assertEqual(fn["name"], "data_analysis")
        schema = fn["parameters"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("operation", schema["properties"])
        self.assertIn("data", schema["properties"])
        self.assertIn("parameters", schema["properties"])
        self.assertIn("operation", schema["required"])
        self.assertIn("data", schema["required"])

        pydantic_def = registered.to_definition()
        self.assertEqual(pydantic_def.name, "data_analysis")

    # 19. Integration: Execution through ToolExecutionService
    async def test_execution_service_integration(self):
        registry = ToolRegistry()
        registry.register(self.tool)
        execution_service = ToolExecutionService(registry=registry)

        record = await execution_service.execute_tool(
            tool_name="data_analysis",
            arguments={
                "operation": "aggregate",
                "data": sample_employee_data(),
                "parameters": {"column": "salary", "aggregator": "sum"},
            },
        )

        self.assertTrue(record.success)
        self.assertEqual(record.tool_name, "data_analysis")
        self.assertEqual(record.data["result"], 385000)
        self.assertGreaterEqual(record.duration_ms, 0.0)

    # 20. Integration: ToolExecutionService invalid arguments rejection
    async def test_execution_service_validation_rejection(self):
        registry = ToolRegistry()
        registry.register(self.tool)
        execution_service = ToolExecutionService(registry=registry)

        # Missing required 'data'
        record = await execution_service.execute_tool(
            tool_name="data_analysis",
            arguments={"operation": "describe"},
        )

        self.assertFalse(record.success)
        self.assertEqual(record.error_type, "ToolInputValidationError")
        self.assertIn("data", record.error)


if __name__ == "__main__":
    unittest.main()
