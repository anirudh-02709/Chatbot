"""
Data Analysis Tool for Goal 10.6.

Performs deterministic analysis over structured tabular datasets (e.g., parsed CSV data):
- describe: Column names, data types, missing counts, numeric summary statistics
- filter: Safe AST-based comparisons and structured row filtering
- aggregate: sum, mean, min, max, count, median (with optional group_by)
- sort: Ascending/descending column ordering

Strict Security Guarantees:
- NO arbitrary code execution or eval/exec.
- NO function calls, imports, attribute access, or variable assignment.
- Purely deterministic Python standard library math and statistics.
- Strict row, column, and cell size resource limits.
"""

import ast
import logging
import math
import statistics
from typing import Any, Optional, Union
from pydantic import BaseModel, Field

from app.models.tool import ToolResult
from app.tools.base import BaseTool, ToolError, ToolInputValidationError

logger = logging.getLogger("chatbot.tools.data_analysis")

# Resource Limits
MAX_ROWS = 10000
MAX_COLUMNS = 100
MAX_CELL_SIZE = 10000  # 10 KB per cell string
MAX_OUTPUT_ROWS = 1000


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────

class DataAnalysisError(ToolError):
    """Base exception for all data analysis errors."""
    pass


class EmptyDatasetError(DataAnalysisError):
    """Raised when data provided to the analysis tool is empty."""
    pass


class MalformedDataError(DataAnalysisError):
    """Raised when data structure is not a valid list of row dictionaries."""
    pass


class ColumnNotFoundError(DataAnalysisError):
    """Raised when a specified column is not present in the dataset."""
    pass


class InvalidConditionError(DataAnalysisError):
    """Raised when a filter expression or condition is invalid or unsafe."""
    pass


class ResourceLimitExceededError(DataAnalysisError):
    """Raised when dataset dimensions or cell sizes exceed security limits."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Input Schema
# ─────────────────────────────────────────────────────────────────────────────

class DataAnalysisInput(BaseModel):
    """Input parameters for the DataAnalysisTool."""

    operation: str = Field(
        ...,
        description="Analysis operation to perform: 'describe', 'filter', 'aggregate', or 'sort'.",
    )
    data: list[dict[str, Any]] = Field(
        ...,
        description="Tabular dataset represented as a list of row dictionaries (column -> value).",
    )
    parameters: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional operation-specific parameters (e.g. column, operator, condition, group_by).",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions: Data Validation & Coercion
# ─────────────────────────────────────────────────────────────────────────────

def validate_tabular_data(data: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Validates the dataset shape, row types, cell sizes, and extracts column names.

    Raises:
        EmptyDatasetError: If dataset has no rows.
        MalformedDataError: If data is not a list of dictionaries.
        ResourceLimitExceededError: If row count, column count, or cell size exceeds limits.
    """
    if not isinstance(data, list):
        raise MalformedDataError(f"Data must be a list of row objects, got {type(data).__name__}.")

    if not data:
        raise EmptyDatasetError("Dataset cannot be empty. At least one row dictionary is required.")

    if len(data) > MAX_ROWS:
        raise ResourceLimitExceededError(
            f"Dataset exceeds maximum allowed rows ({len(data)} > {MAX_ROWS})."
        )

    columns_set: set[str] = set()
    columns_ordered: list[str] = []

    for idx, row in enumerate(data):
        if not isinstance(row, dict):
            raise MalformedDataError(
                f"Row at index {idx} must be a dictionary of column -> value, got {type(row).__name__}."
            )

        for col, val in row.items():
            if not isinstance(col, str):
                raise MalformedDataError(f"Column name at row {idx} must be a string, got {type(col).__name__}.")
            if col not in columns_set:
                columns_set.add(col)
                columns_ordered.append(col)
                if len(columns_ordered) > MAX_COLUMNS:
                    raise ResourceLimitExceededError(
                        f"Dataset exceeds maximum allowed columns ({len(columns_ordered)} > {MAX_COLUMNS})."
                    )

            if isinstance(val, str) and len(val) > MAX_CELL_SIZE:
                raise ResourceLimitExceededError(
                    f"Cell in column '{col}' at row {idx} exceeds maximum cell size ({len(val)} > {MAX_CELL_SIZE} chars)."
                )

    return data, columns_ordered


def safe_numeric_value(val: Any) -> Optional[float]:
    """Attempts to coerce a cell value to float. Returns None if not numeric."""
    if val is None or val == "" or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, str):
        try:
            f = float(val.strip())
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except ValueError:
            return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Safe Filter Engine (AST Whitelist)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_comparison(op: ast.cmpop, left_val: Any, right_val: Any) -> bool:
    """Safely applies a comparison operator between two values with safe type coercion."""
    # Attempt numeric comparison if both are numeric
    num_left = safe_numeric_value(left_val)
    num_right = safe_numeric_value(right_val)
    use_numeric = (num_left is not None) and (num_right is not None)

    l_val = num_left if use_numeric else left_val
    r_val = num_right if use_numeric else right_val

    try:
        if isinstance(op, ast.Eq):
            return l_val == r_val
        elif isinstance(op, ast.NotEq):
            return l_val != r_val
        elif isinstance(op, ast.Lt):
            return l_val < r_val
        elif isinstance(op, ast.LtE):
            return l_val <= r_val
        elif isinstance(op, ast.Gt):
            return l_val > r_val
        elif isinstance(op, ast.GtE):
            return l_val >= r_val
        elif isinstance(op, ast.In):
            # right_val should be a container or string
            return l_val in r_val
        elif isinstance(op, ast.NotIn):
            return l_val not in r_val
    except TypeError:
        # Incompatible types comparison (e.g. str < int)
        return False

    return False


def _eval_ast_node(node: ast.AST, row: dict[str, Any], available_columns: set[str]) -> Any:
    """
    Recursively evaluates an AST node strictly against a whitelist of safe operations.
    Raises InvalidConditionError on any unauthorized node type.
    """
    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body, row, available_columns)

    elif isinstance(node, ast.Name):
        col_name = node.id
        if col_name not in available_columns:
            raise ColumnNotFoundError(
                f"Column '{col_name}' in filter condition does not exist in dataset."
            )
        return row.get(col_name)

    elif isinstance(node, ast.Constant):
        return node.value

    elif isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_ast_node(elt, row, available_columns) for elt in node.elts]

    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            operand = _eval_ast_node(node.operand, row, available_columns)
            if isinstance(operand, (int, float)):
                return -operand
            raise InvalidConditionError(f"Unary minus applied to non-numeric value: {operand}")
        elif isinstance(node.op, ast.Not):
            operand = _eval_ast_node(node.operand, row, available_columns)
            return not bool(operand)
        raise InvalidConditionError(f"Security: disallowed unary operator '{type(node.op).__name__}'")

    elif isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(bool(_eval_ast_node(v, row, available_columns)) for v in node.values)
        elif isinstance(node.op, ast.Or):
            return any(bool(_eval_ast_node(v, row, available_columns)) for v in node.values)
        raise InvalidConditionError(f"Security: disallowed boolean operator '{type(node.op).__name__}'")

    elif isinstance(node, ast.Compare):
        left_val = _eval_ast_node(node.left, row, available_columns)
        for op, comp_node in zip(node.ops, node.comparators):
            right_val = _eval_ast_node(comp_node, row, available_columns)
            if not _apply_comparison(op, left_val, right_val):
                return False
            left_val = right_val
        return True

    # Reject all other AST node types (Call, Attribute, Subscript, Import, etc.)
    raise InvalidConditionError(
        f"Security: disallowed expression node '{type(node).__name__}'. "
        "Only direct column comparisons and constants are permitted."
    )


def filter_rows_by_condition(
    data: list[dict[str, Any]],
    columns: list[str],
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Filters rows using either an expression string (e.g. "score >= 80")
    or structured parameters (e.g. column, operator, value).
    """
    col_set = set(columns)

    # 1. Expression condition string
    condition_str = parameters.get("condition")
    if condition_str and isinstance(condition_str, str) and condition_str.strip():
        expr_clean = condition_str.strip()
        try:
            parsed_tree = ast.parse(expr_clean, mode="eval")
        except SyntaxError as e:
            raise InvalidConditionError(f"Syntax error in filter condition '{expr_clean}': {e}") from e

        matching: list[dict[str, Any]] = []
        for row in data:
            match = bool(_eval_ast_node(parsed_tree, row, col_set))
            if match:
                matching.append(row)
        return matching

    # 2. Structured condition parameters
    col = parameters.get("column")
    if not col or not isinstance(col, str):
        raise InvalidConditionError(
            "Filter requires either a 'condition' expression string or a 'column' parameter."
        )

    if col not in col_set:
        raise ColumnNotFoundError(f"Column '{col}' does not exist in dataset.")

    operator = str(parameters.get("operator", "==")).strip()
    target_val = parameters.get("value")

    # Map string operator to ast.cmpop or direct function
    matching = []
    for row in data:
        row_val = row.get(col)

        if operator in ("=", "=="):
            matched = _apply_comparison(ast.Eq(), row_val, target_val)
        elif operator == "!=":
            matched = _apply_comparison(ast.NotEq(), row_val, target_val)
        elif operator == "<":
            matched = _apply_comparison(ast.Lt(), row_val, target_val)
        elif operator == "<=":
            matched = _apply_comparison(ast.LtE(), row_val, target_val)
        elif operator == ">":
            matched = _apply_comparison(ast.Gt(), row_val, target_val)
        elif operator == ">=":
            matched = _apply_comparison(ast.GtE(), row_val, target_val)
        elif operator == "in":
            matched = _apply_comparison(ast.In(), row_val, target_val)
        elif operator == "not in":
            matched = _apply_comparison(ast.NotIn(), row_val, target_val)
        elif operator == "contains":
            if row_val is None or target_val is None:
                matched = False
            else:
                matched = str(target_val).lower() in str(row_val).lower()
        else:
            raise InvalidConditionError(
                f"Unsupported filter operator '{operator}'. "
                "Supported operators: =, ==, !=, <, <=, >, >=, in, not in, contains."
            )

        if matched:
            matching.append(row)

    return matching


# ─────────────────────────────────────────────────────────────────────────────
# Operation Handlers
# ─────────────────────────────────────────────────────────────────────────────

def handle_describe(data: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    """Generates summary statistics, inferred data types, and missing value counts."""
    row_count = len(data)
    data_types: dict[str, str] = {}
    missing_counts: dict[str, int] = {}
    numeric_stats: dict[str, dict[str, Any]] = {}

    for col in columns:
        col_values = [row.get(col) for row in data]
        missing_count = sum(1 for v in col_values if v is None or v == "")
        missing_counts[col] = missing_count

        non_missing = [v for v in col_values if v is not None and v != ""]
        if not non_missing:
            data_types[col] = "empty"
            continue

        # Check for numeric type
        numeric_vals = [safe_numeric_value(v) for v in non_missing]
        if all(nv is not None for nv in numeric_vals):
            data_types[col] = "numeric"
            nums = [float(nv) for nv in numeric_vals if nv is not None]
            n_count = len(nums)
            n_sum = sum(nums)
            n_mean = statistics.mean(nums)
            n_min = min(nums)
            n_max = max(nums)
            n_std = round(statistics.stdev(nums), 4) if n_count >= 2 else None

            numeric_stats[col] = {
                "count": n_count,
                "sum": round(n_sum, 4),
                "mean": round(n_mean, 4),
                "min": round(n_min, 4),
                "max": round(n_max, 4),
                "std_dev": n_std,
            }
        elif all(isinstance(v, bool) or str(v).lower() in ("true", "false") for v in non_missing):
            data_types[col] = "boolean"
        else:
            data_types[col] = "string"

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "data_types": data_types,
        "missing_counts": missing_counts,
        "numeric_statistics": numeric_stats,
    }


def handle_aggregate(
    data: list[dict[str, Any]],
    columns: list[str],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Performs aggregation (count, sum, mean, min, max, median) with optional group_by."""
    aggregator = str(
        parameters.get("aggregator") or parameters.get("operation") or "count"
    ).lower().strip()
    col = parameters.get("column")
    group_by = parameters.get("group_by")

    valid_aggs = {"count", "sum", "mean", "avg", "average", "min", "max", "median"}
    if aggregator not in valid_aggs:
        raise DataAnalysisError(
            f"Unsupported aggregator '{aggregator}'. Supported: {sorted(valid_aggs)}"
        )

    # Count without column aggregates total rows
    if aggregator == "count" and not col and not group_by:
        return {
            "aggregator": "count",
            "column": None,
            "result": len(data),
            "row_count": len(data),
        }

    if col and col not in columns:
        raise ColumnNotFoundError(f"Aggregation column '{col}' does not exist in dataset.")

    if group_by and group_by not in columns:
        raise ColumnNotFoundError(f"Group-by column '{group_by}' does not exist in dataset.")

    def compute_metric(vals: list[Any]) -> Union[int, float]:
        if aggregator == "count":
            return len([v for v in vals if v is not None and v != ""])

        nums = [safe_numeric_value(v) for v in vals]
        valid_nums = [n for n in nums if n is not None]

        if not valid_nums:
            raise DataAnalysisError(
                f"Column '{col}' contains no valid numeric values for '{aggregator}' aggregation."
            )

        if aggregator == "sum":
            return round(sum(valid_nums), 4)
        elif aggregator in ("mean", "avg", "average"):
            return round(statistics.mean(valid_nums), 4)
        elif aggregator == "min":
            return round(min(valid_nums), 4)
        elif aggregator == "max":
            return round(max(valid_nums), 4)
        elif aggregator == "median":
            return round(statistics.median(valid_nums), 4)
        return 0

    if group_by:
        groups: dict[Any, list[Any]] = {}
        for row in data:
            grp_key = row.get(group_by)
            val = row.get(col) if col else 1
            groups.setdefault(grp_key, []).append(val)

        group_results = []
        for grp_key, grp_vals in groups.items():
            res = compute_metric(grp_vals)
            group_results.append({
                group_by: grp_key,
                "count": len(grp_vals),
                "result": res,
            })

        return {
            "aggregator": aggregator,
            "column": col,
            "group_by": group_by,
            "group_count": len(group_results),
            "results": group_results,
        }

    # Overall dataset metric
    vals = [row.get(col) for row in data]
    result_val = compute_metric(vals)
    return {
        "aggregator": aggregator,
        "column": col,
        "result": result_val,
        "count": len([v for v in vals if v is not None and v != ""]),
    }


def handle_sort(
    data: list[dict[str, Any]],
    columns: list[str],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Sorts tabular data by a specified column ascending or descending."""
    col = parameters.get("column")
    if not col or not isinstance(col, str):
        raise DataAnalysisError("Sort operation requires a 'column' parameter.")

    if col not in columns:
        raise ColumnNotFoundError(f"Sort column '{col}' does not exist in dataset.")

    descending = bool(
        parameters.get("descending", False) or str(parameters.get("order", "")).lower() == "desc"
    )
    limit = parameters.get("limit")

    def sort_key(row: dict[str, Any]) -> tuple[int, Any]:
        val = row.get(col)
        # Handle None/empty values by placing them at the end
        if val is None or val == "":
            return (1, "")
        num = safe_numeric_value(val)
        if num is not None:
            return (0, num)
        return (0, str(val).lower())

    sorted_rows = sorted(data, key=sort_key, reverse=descending)

    if limit is not None and isinstance(limit, int) and limit > 0:
        sorted_rows = sorted_rows[:limit]

    output_rows = sorted_rows[:MAX_OUTPUT_ROWS]
    is_truncated = len(sorted_rows) > MAX_OUTPUT_ROWS

    return {
        "column": col,
        "descending": descending,
        "row_count": len(output_rows),
        "total_matches": len(sorted_rows),
        "truncated": is_truncated,
        "rows": output_rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DataAnalysisTool Implementation
# ─────────────────────────────────────────────────────────────────────────────

class DataAnalysisTool(BaseTool):
    """
    Tool allowing the AI Assistant to perform deterministic analytical operations
    over structured tabular data (e.g. CSV datasets).

    Supports:
    - 'describe': Summary statistics, data types, missing counts
    - 'filter': Safe AST condition and structured comparison filtering
    - 'aggregate': sum, mean, min, max, count, median (with group_by)
    - 'sort': Ascending or descending column sorting
    """

    name = "data_analysis"
    description = (
        "Performs deterministic analysis over tabular data (list of row dictionaries). "
        "Supported operations: 'describe' (data summary & numeric statistics), "
        "'filter' (safe column comparisons), 'aggregate' (sum, mean, min, max, count, group_by), "
        "and 'sort' (ordering by column)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["describe", "filter", "aggregate", "sort"],
                "description": "The analysis operation to execute.",
            },
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Tabular dataset represented as a list of row dictionaries.",
            },
            "parameters": {
                "type": "object",
                "description": "Optional parameters specific to the operation (e.g. column, condition, group_by).",
            },
        },
        "required": ["operation", "data"],
    }
    args_model = DataAnalysisInput

    async def execute(
        self,
        operation: str,
        data: list[dict[str, Any]],
        parameters: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Executes the requested deterministic tabular data operation.

        Returns:
            Structured ToolResult containing analysis data, or a structured failure.
        """
        clean_op = str(operation).strip().lower() if operation else ""
        valid_ops = {"describe", "filter", "aggregate", "sort"}

        if clean_op not in valid_ops:
            return ToolResult.fail(
                tool_name=self.name,
                error=f"Unsupported operation '{operation}'. Supported operations: {', '.join(sorted(valid_ops))}.",
                error_type="UnsupportedOperationError",
            )

        # Validate tabular data shape and constraints
        try:
            validated_data, columns = validate_tabular_data(data)
        except DataAnalysisError as e:
            logger.warning(f"Data validation error in DataAnalysisTool: {e}")
            return ToolResult.fail(
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__,
            )
        except Exception as e:
            logger.error(f"Unexpected data validation failure in DataAnalysisTool: {e}")
            return ToolResult.fail(
                tool_name=self.name,
                error=f"Data validation failed: {e}",
                error_type="MalformedDataError",
            )

        params = parameters if parameters is not None else {}

        # Dispatch operation
        try:
            if clean_op == "describe":
                res_data = handle_describe(validated_data, columns)
                meta = {
                    "operation": clean_op,
                    "row_count": res_data["row_count"],
                    "column_count": res_data["column_count"],
                }

            elif clean_op == "filter":
                matching = filter_rows_by_condition(validated_data, columns, params)
                truncated = len(matching) > MAX_OUTPUT_ROWS
                output_rows = matching[:MAX_OUTPUT_ROWS]
                res_data = {
                    "match_count": len(matching),
                    "returned_rows": len(output_rows),
                    "truncated": truncated,
                    "rows": output_rows,
                }
                meta = {
                    "operation": clean_op,
                    "match_count": len(matching),
                    "truncated": truncated,
                }

            elif clean_op == "aggregate":
                res_data = handle_aggregate(validated_data, columns, params)
                meta = {
                    "operation": clean_op,
                    "aggregator": res_data.get("aggregator"),
                    "column": res_data.get("column"),
                }

            elif clean_op == "sort":
                res_data = handle_sort(validated_data, columns, params)
                meta = {
                    "operation": clean_op,
                    "column": res_data.get("column"),
                    "descending": res_data.get("descending"),
                    "row_count": res_data.get("row_count"),
                }

            logger.info(
                f"DataAnalysisTool executed '{clean_op}' over {len(validated_data)} rows successfully."
            )
            return ToolResult.ok(
                tool_name=self.name,
                data=res_data,
                metadata=meta,
            )

        except DataAnalysisError as e:
            logger.warning(f"DataAnalysisTool operation '{clean_op}' failed: {e}")
            return ToolResult.fail(
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__,
                metadata={"operation": clean_op},
            )
        except Exception as e:
            logger.error(f"Unexpected failure executing '{clean_op}': {e}")
            return ToolResult.fail(
                tool_name=self.name,
                error=f"Data analysis failed unexpectedly: {e}",
                error_type=type(e).__name__,
                metadata={"operation": clean_op},
            )


# Global singleton instance
data_analysis_tool = DataAnalysisTool()
