"""Analyst Agent — Part 12.

Pipeline: question -> schema grounding -> SQL generation (LLM) -> SQL
validator (code, not the LLM) -> BigQuery dry run (bytes cap) -> real
execution -> plain-English answer.

Every safety-relevant decision (is this SELECT-only? is the table allowed?
is the estimated scan too big?) is made by CODE, never by asking the LLM
"is this safe" — an LLM's own judgment about its own query is not a
security boundary.
"""
from dataclasses import dataclass

from app.agents.bigquery_client import dry_run, execute, BigQueryError
from app.agents.schema_catalog import get_schema_context
from app.agents.sql_validator import validate_sql, SQLValidationError
from app.prompts import load_prompt

# Refuse any query estimated to scan more than this many bytes — a dry run
# catches this BEFORE it costs anything (BigQuery's free tier is 1TB/month;
# one careless unbounded scan across a growing table could eat a big chunk
# of that in a single query).
MAX_BYTES_SCANNED = 100_000_000  # 100 MB


@dataclass
class AnalystAgentResult:
    question: str
    sql: str | None
    answer: str
    status: str  # "ok" | "sql_generation_failed" | "validation_refused" | "dry_run_refused" | "execution_failed"
    rows: list | None = None
    columns: list | None = None
    bytes_scanned: int | None = None


async def _generate_sql(provider_module, question: str) -> str:
    prompt_template = load_prompt("analyst_sql", 1)
    system = prompt_template["system"].replace("{schema}", get_schema_context())
    full_prompt = f"{system}\n\nQuestion: {question}\n\nSQL:"
    result = await provider_module.chat(full_prompt)
    sql = result.answer.strip()
    # Models sometimes wrap SQL in markdown fences despite instructions not to.
    if sql.startswith("```"):
        sql = sql.strip("`")
        if sql.lower().startswith("sql"):
            sql = sql[3:]
        sql = sql.strip()
    return sql


async def _summarize_answer(provider_module, question: str, columns: list, rows: list) -> str:
    if not rows:
        return "The query ran successfully but returned no rows."
    table_preview = f"Columns: {columns}\nRows: {rows[:20]}"
    prompt = (
        f"Question: {question}\n\nQuery result:\n{table_preview}\n\n"
        "Answer the question in plain English, using only this data. Be concise."
    )
    result = await provider_module.chat(prompt)
    return result.answer.strip()


async def ask(provider_module, question: str) -> AnalystAgentResult:
    try:
        sql = await _generate_sql(provider_module, question)
    except Exception as exc:
        return AnalystAgentResult(
            question=question, sql=None, answer=f"Could not generate SQL: {exc}",
            status="sql_generation_failed",
        )

    try:
        validated_sql = validate_sql(sql)
    except SQLValidationError as exc:
        return AnalystAgentResult(
            question=question, sql=sql,
            answer=f"Refused to run this query — it failed safety validation: {exc}",
            status="validation_refused",
        )

    try:
        bytes_scanned = await dry_run(validated_sql)
    except BigQueryError as exc:
        return AnalystAgentResult(
            question=question, sql=validated_sql, answer=f"Could not estimate query cost: {exc}",
            status="dry_run_refused",
        )

    if bytes_scanned > MAX_BYTES_SCANNED:
        return AnalystAgentResult(
            question=question, sql=validated_sql,
            answer=(
                f"Refused to run this query — it would scan {bytes_scanned:,} bytes, "
                f"over the {MAX_BYTES_SCANNED:,} byte limit."
            ),
            status="dry_run_refused",
            bytes_scanned=bytes_scanned,
        )

    try:
        result = await execute(validated_sql)
    except BigQueryError as exc:
        return AnalystAgentResult(
            question=question, sql=validated_sql, answer=f"Query execution failed: {exc}",
            status="execution_failed", bytes_scanned=bytes_scanned,
        )

    answer = await _summarize_answer(provider_module, question, result["columns"], result["rows"])

    return AnalystAgentResult(
        question=question, sql=validated_sql, answer=answer, status="ok",
        rows=result["rows"], columns=result["columns"], bytes_scanned=bytes_scanned,
    )
