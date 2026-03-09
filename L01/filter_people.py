from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "people.csv"
OUTPUT_FILE = BASE_DIR / "people_out.csv"
REFERENCE_DATE = date(2026, 3, 9)
MIN_AGE = 20
MAX_AGE = 40
TARGET_GENDER = "M"
TARGET_BIRTHPLACE = "Grudziądz"


def calculate_age(birth_date: date, reference_date: date) -> int:
    years = reference_date.year - birth_date.year
    had_birthday = (reference_date.month, reference_date.day) >= (birth_date.month, birth_date.day)
    return years if had_birthday else years - 1


def matches_criteria(person: dict[str, str]) -> bool:
    birth_date = datetime.strptime(person["birthDate"], "%Y-%m-%d").date()
    age = calculate_age(birth_date, REFERENCE_DATE)

    return (
        person["gender"] == TARGET_GENDER
        and MIN_AGE <= age < MAX_AGE
        and person["birthPlace"] == TARGET_BIRTHPLACE
    )


def main() -> None:
    with INPUT_FILE.open("r", encoding="utf-8", newline="") as input_handle:
        reader = csv.DictReader(input_handle)
        filtered_rows = [row for row in reader if matches_criteria(row)]
        fieldnames = reader.fieldnames

    if fieldnames is None:
        raise ValueError("Brak naglowkow w pliku wejściowym CSV.")

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(output_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_rows)


if __name__ == "__main__":
    main()