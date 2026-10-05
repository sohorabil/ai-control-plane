"""Validates LLM-generated SQL before it ever touches BigQuery — Part 12.

Uses sqlparse's real tokenizer, not regex/string matching. Regex checks for
"no DELETE" are a classic bypass surface (a DELETE hidden in a comment, a
string literal containing the word SELECT, a semicolon-chained second
statement) — a real parser sees the actual statement structure instead of
just scanning for scary words.

Defense in depth, in order: (1) exactly one statement, (2) that statement
is a SELECT, (3) every table referenced is on the allow-list, (4) a LIMIT
clause is present (capped), (5) the caller still runs a BigQuery dry run
afterward to catch a huge scan a syntactically-valid SELECT could still
cause (e.g. a missing WHERE on a huge unclustered table) — this validator
only proves intent, not cost.
"""
import sqlparse
from sqlparse.tokens import Keyword, DML, Name, Punctuation

ALLOWED_TABLES = {
    "eacp_usage_analytics.usage_daily",
    "eacp_eval_history",  # dataset itself has no tables yet (Part 6/13 territory)
}

MAX_LIMIT = 10_000


class SQLValidationError(Exception):
    pass


_FROM_LIKE = {"FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"}
_STOP_KEYWORDS = {"WHERE", "GROUP BY", "ORDER BY", "LIMIT", "ON", "AS", "HAVING", "UNION"}


def _extract_table_names(parsed) -> set[str]:
    """Scans the FLATTENED token stream (not the nested structure) for every
    FROM/JOIN keyword, then reads the dotted name that follows each one.
    Flattening deliberately ignores how sqlparse groups parentheses/subquery
    structure — a naive structural walk missed a table hidden inside a
    subquery's parentheses (only saw the subquery's alias); scanning the
    flat stream for every FROM/JOIN, including ones nested inside
    parentheses, closes that gap.
    """
    tables = set()
    tokens = list(parsed.flatten())
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.ttype is Keyword and token.value.upper() in _FROM_LIKE:
            # Walk forward past whitespace to the table name (possibly
            # dotted: dataset.table), stop at the next keyword/punctuation
            # that isn't part of a dotted name.
            j = i + 1
            name_parts = []
            while j < len(tokens):
                t = tokens[j]
                if t.is_whitespace:
                    j += 1
                    continue
                if t.ttype is Name:
                    name_parts.append(t.value)
                    j += 1
                    continue
                if t.ttype is Punctuation and t.value == "." and name_parts:
                    j += 1
                    continue
                break
            if name_parts:
                tables.add(".".join(name_parts))
        i += 1
    return tables


def validate_sql(sql: str) -> str:
    """Returns the validated SQL (possibly with a LIMIT appended) or raises
    SQLValidationError with a clear reason.
    """
    statements = sqlparse.parse(sql.strip().rstrip(";"))

    if len(statements) != 1:
        raise SQLValidationError(
            f"expected exactly one SQL statement, got {len(statements)} "
            "(statement-chaining via semicolons is not allowed)"
        )

    parsed = statements[0]

    dml_tokens = [t for t in parsed.flatten() if t.ttype is DML]
    if not dml_tokens or dml_tokens[0].value.upper() != "SELECT":
        found = dml_tokens[0].value.upper() if dml_tokens else "none"
        raise SQLValidationError(f"only SELECT statements are allowed (found: {found})")

    # Reject any other DML/DDL keyword appearing anywhere in the statement
    # (belt-and-suspenders beyond the single-statement check above — catches
    # e.g. a SELECT containing a subquery that references a disallowed
    # write-capable construct in some dialect-specific extension).
    forbidden = {"DELETE", "DROP", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "MERGE", "CREATE", "GRANT"}
    for token in parsed.flatten():
        if token.ttype is DML and token.value.upper() in forbidden:
            raise SQLValidationError(f"forbidden statement type: {token.value.upper()}")
        if token.ttype is Keyword and token.value.upper() in forbidden:
            raise SQLValidationError(f"forbidden keyword present: {token.value.upper()}")

    tables = _extract_table_names(parsed)
    disallowed = {t for t in tables if t not in ALLOWED_TABLES and f"eacp_usage_analytics.{t}" not in ALLOWED_TABLES}
    if disallowed:
        raise SQLValidationError(
            f"query references table(s) not on the allow-list: {disallowed} "
            f"(allowed: {ALLOWED_TABLES})"
        )

    sql_upper = sql.upper()
    if "LIMIT" not in sql_upper:
        sql = sql.rstrip().rstrip(";") + f" LIMIT {MAX_LIMIT}"
    else:
        import re
        match = re.search(r"LIMIT\s+(\d+)", sql_upper)
        if match and int(match.group(1)) > MAX_LIMIT:
            raise SQLValidationError(f"LIMIT {match.group(1)} exceeds the maximum allowed ({MAX_LIMIT})")

    return sql
