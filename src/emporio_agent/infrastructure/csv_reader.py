import csv
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from emporio_agent.errors import DataLoadError

T = TypeVar("T")


def read_csv_rows(path: Path, required_columns: Iterable[str]) -> list[dict[str, str]]:
    """Reads a CSV file and checks it has the expected columns.

    Args:
        path: Location of the CSV file (UTF-8, comma separated, header on the first line).
        required_columns: Columns the file must have. Extra columns are allowed.

    Returns:
        One dict per row, with the cell values stripped of surrounding spaces.

    Raises:
        DataLoadError: If the file does not exist, can not be decoded or misses a column.
    """
    if not path.is_file():
        raise DataLoadError(f"Data file not found: {path}")
    try:
        with path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            missing = set(required_columns) - set(reader.fieldnames or [])
            if missing:
                raise DataLoadError(f"{path.name} is missing columns: {sorted(missing)}")
            return [
                {key: (value or "").strip() for key, value in row.items() if key is not None}
                for row in reader
            ]
    except UnicodeDecodeError as error:
        raise DataLoadError(f"{path.name} is not valid UTF-8: {error}") from error


def build_records(
    rows: list[dict[str, str]], file_name: str, to_record: Callable[[dict[str, str]], T]
) -> list[T]:
    """Turns raw CSV rows into domain records.

    Args:
        rows: Rows returned by read_csv_rows.
        file_name: Name of the source file, only used in error messages.
        to_record: Function that converts one row into a record.

    Returns:
        The records in the same order as the rows.

    Raises:
        DataLoadError: If a row has an invalid value. The message says the file and line.
    """
    records = []
    for line_number, row in enumerate(rows, start=2):
        try:
            records.append(to_record(row))
        except (ValidationError, ValueError, KeyError) as error:
            # This is for pointing to the exact line, line 1 is the header
            raise DataLoadError(f"{file_name}, line {line_number}: {error}") from error
    return records


def empty_to_none(value: str) -> str | None:
    """Converts an empty cell into None.

    Args:
        value: Raw cell value.

    Returns:
        None for empty cells, the same value otherwise.
    """
    return value or None
