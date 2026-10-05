"""Adversarial tests for the Analyst Agent's SQL safety gate (Part 12).

This validator is the single thing standing between an LLM's generated SQL
and a real BigQuery execution — every test here represents a real attack or
mistake class a generated query could actually produce.
"""
import pytest

from app.agents.sql_validator import validate_sql, SQLValidationError, MAX_LIMIT


def test_allows_simple_select_on_allowed_table():
    sql = "SELECT team, cost_usd FROM eacp_usage_analytics.usage_daily LIMIT 10"
    result = validate_sql(sql)
    assert "SELECT" in result.upper()


def test_adds_limit_when_missing():
    sql = "SELECT * FROM eacp_usage_analytics.usage_daily"
    result = validate_sql(sql)
    assert "LIMIT" in result.upper()


def test_rejects_delete():
    with pytest.raises(SQLValidationError, match="only SELECT"):
        validate_sql("DELETE FROM eacp_usage_analytics.usage_daily")


def test_rejects_drop_table():
    with pytest.raises(SQLValidationError, match="only SELECT"):
        validate_sql("DROP TABLE eacp_usage_analytics.usage_daily")


def test_rejects_update():
    with pytest.raises(SQLValidationError, match="only SELECT"):
        validate_sql("UPDATE eacp_usage_analytics.usage_daily SET cost_usd = 0")


def test_rejects_insert():
    with pytest.raises(SQLValidationError, match="only SELECT"):
        validate_sql("INSERT INTO eacp_usage_analytics.usage_daily VALUES (1, 2, 3)")


def test_rejects_disallowed_table():
    with pytest.raises(SQLValidationError, match="allow-list"):
        validate_sql("SELECT * FROM some_other_dataset.secret_table LIMIT 10")


def test_rejects_statement_chaining():
    # A classic injection pattern: a valid-looking SELECT followed by a
    # second, destructive statement after a semicolon.
    with pytest.raises(SQLValidationError, match="exactly one SQL statement"):
        validate_sql(
            "SELECT * FROM eacp_usage_analytics.usage_daily; "
            "DROP TABLE eacp_usage_analytics.usage_daily"
        )


def test_rejects_limit_above_maximum():
    with pytest.raises(SQLValidationError, match="exceeds the maximum"):
        validate_sql(f"SELECT * FROM eacp_usage_analytics.usage_daily LIMIT {MAX_LIMIT + 1}")


def test_allows_limit_at_maximum():
    sql = f"SELECT * FROM eacp_usage_analytics.usage_daily LIMIT {MAX_LIMIT}"
    validate_sql(sql)  # should not raise


def test_rejects_delete_disguised_in_select_looking_prompt_injection():
    # A query that STARTS by looking like a SELECT request in a prompt but
    # the model actually generated a destructive statement — tests that we
    # check the real parsed statement type, not just "does it start with
    # a SELECT-sounding comment".
    sql = "-- SELECT only, I promise\nDELETE FROM eacp_usage_analytics.usage_daily"
    with pytest.raises(SQLValidationError, match="only SELECT"):
        validate_sql(sql)


def test_rejects_select_with_delete_keyword_hidden_as_second_statement_no_space():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT 1;DELETE FROM eacp_usage_analytics.usage_daily")


def test_rejects_disallowed_table_hidden_inside_subquery():
    # Real bug caught during development: the first version of
    # _extract_table_names walked sqlparse's NESTED structure and only saw
    # the subquery's alias ("sub"), missing the real table name one level
    # deeper inside the parentheses — this query was WRONGLY ALLOWED until
    # fixed to scan the flattened token stream instead.
    sql = "SELECT * FROM (SELECT * FROM secret_dataset.hidden_table) AS sub"
    with pytest.raises(SQLValidationError, match="allow-list"):
        validate_sql(sql)


def test_rejects_disallowed_table_in_join():
    sql = (
        "SELECT a.team FROM eacp_usage_analytics.usage_daily a "
        "JOIN secret.other_table b ON a.app = b.app"
    )
    with pytest.raises(SQLValidationError, match="allow-list"):
        validate_sql(sql)
