from __future__ import annotations

import re
import zipfile
from collections import defaultdict
from datetime import date, time, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from .models import Employee, ImportedOperatorDoc, TimeConstraint, WeekendChoice
from .parsers import ParseError, slugify_name

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FULL_DAY_START = time(0, 0)
FULL_DAY_END = time(23, 59)

WEEKDAY_ALIASES = {
    "понедельник": 0,
    "понедельника": 0,
    "понедельнику": 0,
    "понедельникам": 0,
    "вторник": 1,
    "вторника": 1,
    "вторнику": 1,
    "вторникам": 1,
    "среда": 2,
    "среду": 2,
    "среды": 2,
    "средам": 2,
    "четверг": 3,
    "четверга": 3,
    "четвергу": 3,
    "четвергам": 3,
    "пятница": 4,
    "пятницу": 4,
    "пятницы": 4,
    "пятницам": 4,
    "суббота": 5,
    "субботу": 5,
    "субботы": 5,
    "субботам": 5,
    "воскресенье": 6,
    "воскресенья": 6,
    "воскресеньям": 6,
}

MONTH_ALIASES = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}

STRICT_MARKERS = ("не ставить", "не могу", "выходной", "отпуск", "уехать", "отдыхаю", "запись")
SOFT_MARKERS = ("по возможности", "при возможности", "был бы рад", "была бы рада", "прошу по возможности")
STUDY_MARKERS = ("пары", "учеб", "сесс", "консультац", "вкр", "занят")
POSITIVE_WORK_MARKERS = ("свобод", "могу выйти", "смогу выйти", "готов отработ", "готова отработ", "готов выйти", "готова выйти", "отработать")


def import_operator_documents(
    base_dir: str,
    year: int,
    month: int,
) -> tuple[list[Employee], list[TimeConstraint], list[WeekendChoice], list[ImportedOperatorDoc], list[str]]:
    root = Path(base_dir).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    if not root.exists() or not root.is_dir():
        raise ParseError(f"Папка операторов не найдена: {root}")

    employees: list[Employee] = []
    constraints: list[TimeConstraint] = []
    weekend_choices: list[WeekendChoice] = []
    previews: list[ImportedOperatorDoc] = []
    warnings: list[str] = []

    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        employee_name = folder.name.strip()
        employees.append(Employee(employee_id=slugify_name(employee_name), name=employee_name))
        docx_files = sorted(path for path in folder.iterdir() if is_supported_docx(path))
        if not docx_files:
            if any(path.is_file() and is_word_temp_file(path) for path in folder.iterdir()):
                warnings.append(
                    f"У сотрудника {employee_name} найдены только временные файлы Word `~$...docx`. "
                    "Они пропущены, потому что это служебные файлы открытого документа."
                )
            else:
                warnings.append(f"У сотрудника {employee_name} в папке нет .docx-файлов.")
            continue

        for docx_path in docx_files:
            try:
                text = extract_docx_text(docx_path)
            except ParseError as error:
                warnings.append(str(error))
                continue
            local_notes: list[str] = []
            all_constraints: list[TimeConstraint] = []
            doc_weekend_choices: list[WeekendChoice] = []
            error: str | None = None

            # Используем локальный парсер
            local_constraints, parse_notes = parse_constraints_from_document_text(employee_name, text, year, month)
            doc_weekend_choices, weekend_notes = parse_weekend_choices_from_document_text(employee_name, text, year, month)
            all_constraints = deduplicate_constraints(list(local_constraints))
            local_notes = list(parse_notes) + list(weekend_notes)

            constraints.extend(all_constraints)
            weekend_choices.extend(doc_weekend_choices)
            previews.append(
                ImportedOperatorDoc(
                    employee_name=employee_name,
                    source_path=str(docx_path),
                    extracted_text=text.strip(),
                    constraints=all_constraints,
                    notes=local_notes,
                    error=error,
                )
            )

    return (
        merge_employees(employees),
        deduplicate_constraints(constraints),
        deduplicate_weekend_choices(weekend_choices),
        previews,
        warnings,
    )


def is_word_temp_file(path: Path) -> bool:
    return path.name.startswith("~$")


def is_supported_docx(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".docx" and not is_word_temp_file(path)


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_content = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ParseError(f"Не удалось прочитать DOCX-файл {path}: {error}") from error

    root = ET.fromstring(xml_content)
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{W_NS}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{W_NS}t" and node.text:
                parts.append(node.text)
            elif node.tag in {f"{W_NS}tab"}:
                parts.append(" ")
            elif node.tag in {f"{W_NS}br", f"{W_NS}cr"}:
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return normalize_text("\n".join(paragraphs))


def normalize_text(text: str) -> str:
    normalized = text.replace("\xa0", " ").replace("\u2028", "\n").replace("\u2029", "\n")
    normalized = normalized.replace("—", "-").replace("–", "-").replace("−", "-")
    normalized = normalized.replace("\t", " ")
    normalized = re.sub(r"[ ]{2,}", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def parse_constraints_from_document_text(employee_name: str, text: str, year: int, month: int) -> tuple[list[TimeConstraint], list[str]]:
    lowered = text.lower()
    constraints: list[TimeConstraint] = []
    notes: list[str] = []

    constraints.extend(parse_explicit_date_lines(employee_name, text, year, month))
    constraints.extend(parse_date_range_requests(employee_name, lowered, year, month))
    constraints.extend(parse_weekday_requests(employee_name, lowered, year, month))
    constraints.extend(parse_even_odd_week_blocks(employee_name, text, year, month))
    constraints.extend(parse_specific_day_requests(employee_name, lowered, year, month))
    constraints.extend(parse_recurring_daily_windows(employee_name, lowered, year, month, notes))

    unique_constraints = deduplicate_constraints(constraints)
    if not unique_constraints:
        notes.append("Локальный парсер не нашел явных ограничений — проверьте исходный документ.")
    return unique_constraints, deduplicate_notes(notes)


def parse_weekend_choices_from_document_text(employee_name: str, text: str, year: int, month: int) -> tuple[list[WeekendChoice], list[str]]:
    choices: list[WeekendChoice] = []
    notes: list[str] = []
    lowered = text.lower()

    choices.extend(parse_explicit_work_date_lines(employee_name, text, year, month))
    choices.extend(parse_work_date_list_requests(employee_name, lowered, year, month))

    unique_choices = deduplicate_weekend_choices(choices)
    if unique_choices:
        notes.append(f"Найдены даты готовности на выходные или праздники: {len(unique_choices)}.")
    return unique_choices, notes


def parse_explicit_date_lines(employee_name: str, text: str, year: int, month: int) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(
            r"^(?P<start>\d{1,2}[./]\d{1,2})(?:\s*-\s*(?P<end>\d{1,2}[./]\d{1,2}))?\s*-\s*(?P<body>.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        start_date = build_numeric_date(match.group("start"), year)
        end_value = match.group("end")
        end_date = build_numeric_date(end_value, year) if end_value else start_date
        body = match.group("body").strip()
        if start_date.month != month and end_date.month != month:
            continue
        for target_date in iterate_dates(start_date, end_date):
            if target_date.month != month:
                continue
            constraints.extend(parse_line_body(employee_name, target_date, body))
    return constraints


def parse_explicit_work_date_lines(employee_name: str, text: str, year: int, month: int) -> list[WeekendChoice]:
    choices: list[WeekendChoice] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(
            r"^(?P<start>\d{1,2}[./]\d{1,2})(?:\s*-\s*(?P<end>\d{1,2}[./]\d{1,2}))?\s*-\s*(?P<body>.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        body = match.group("body").strip()
        if not is_positive_work_phrase(body.lower()):
            continue

        start_date = build_numeric_date(match.group("start"), year)
        end_value = match.group("end")
        end_date = build_numeric_date(end_value, year) if end_value else start_date
        if start_date.month != month and end_date.month != month:
            continue

        for target_date in iterate_dates(start_date, end_date):
            if target_date.month != month:
                continue
            choices.append(
                WeekendChoice(
                    employee_name=employee_name,
                    date=target_date,
                    shift_code=None,
                    note=body,
                )
            )
    return choices


def parse_line_body(employee_name: str, target_date: date, body: str) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    fragments = [fragment.strip() for fragment in re.split(r"[;,]", body) if fragment.strip()]
    if not fragments:
        fragments = [body]

    for fragment in fragments:
        fragment_lower = fragment.lower()

        if "смогу выйти" in fragment_lower and "после" in fragment_lower:
            time_value = find_single_time_after_keyword(fragment_lower, "после")
            if time_value:
                constraints.append(
                    TimeConstraint(
                        employee_name=employee_name,
                        date=target_date,
                        kind="unavailable",
                        start_time=FULL_DAY_START,
                        end_time=time_value,
                        strict=True,
                        note=fragment,
                    )
                )
            continue

        if contains_any(fragment_lower, ("отдыхаю", "отпуск", "выходной", "запись", "не ставить")):
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind="unavailable",
                    start_time=None,
                    end_time=None,
                    strict=True,
                    note=fragment,
                )
            )
            continue

        time_ranges = find_time_ranges(fragment_lower)
        for start_value, end_value in time_ranges:
            kind = "study" if contains_any(fragment_lower, STUDY_MARKERS) else "unavailable"
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind=kind,
                    start_time=start_value,
                    end_time=end_value,
                    strict=True,
                    note=fragment,
                )
            )
    return constraints


def parse_date_range_requests(employee_name: str, text: str, year: int, month: int) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []

    for match in re.finditer(
        r"(?P<prefix>отпуск|уехать|не выходить|выходной|не ставить[^.]{0,80})[^.\n]{0,80}?(?:с|со)\s*(?P<start>\d{1,2}[./]\d{1,2})\s*по\s*(?P<end>\d{1,2}[./]\d{1,2})",
        text,
        flags=re.IGNORECASE,
    ):
        start_date = build_numeric_date(match.group("start"), year)
        end_date = build_numeric_date(match.group("end"), year)
        for target_date in iterate_dates(start_date, end_date):
            if target_date.month != month:
                continue
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind="unavailable",
                    start_time=None,
                    end_time=None,
                    strict=True,
                    note=match.group(0).strip(),
                )
            )

    for match in re.finditer(
        r"(?P<prefix>отпуск|уехать|не выходить|выходной|не ставить[^.]{0,80})[^.\n]{0,80}?(?:с|со)\s*(?P<day1>\d{1,2})\s*(?:по|-)\s*(?P<day2>\d{1,2})\s*(?P<month_name>[а-яё]+)",
        text,
        flags=re.IGNORECASE,
    ):
        month_number = resolve_month_from_word(match.group("month_name"))
        if month_number != month:
            continue
        start_date = date(year, month_number, int(match.group("day1")))
        end_date = date(year, month_number, int(match.group("day2")))
        for target_date in iterate_dates(start_date, end_date):
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind="unavailable",
                    start_time=None,
                    end_time=None,
                    strict=True,
                    note=match.group(0).strip(),
                )
            )

    return constraints


def parse_weekday_requests(employee_name: str, text: str, year: int, month: int) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    for sentence in split_sentences(text):
        sentence_lower = sentence.lower()
        weekday_numbers = extract_weekday_numbers(sentence_lower)
        if not weekday_numbers:
            continue

        if "могу работать с" in sentence_lower:
            after_time = find_single_time_after_keyword(sentence_lower, "с")
            if after_time is None:
                continue
            for target_date in dates_for_weekdays(year, month, weekday_numbers):
                constraints.append(
                    TimeConstraint(
                        employee_name=employee_name,
                        date=target_date,
                        kind="unavailable",
                        start_time=FULL_DAY_START,
                        end_time=after_time,
                        strict=True,
                        note=sentence.strip(),
                    )
                )
            continue

        if contains_any(sentence_lower, ("вечернее время", "вечером")):
            continue

        time_ranges = find_time_ranges(sentence_lower)
        if time_ranges and not contains_any(
            sentence_lower,
            ("не ставить", "кажд", "по ", "могу", "занят", "учеб", "пары", "отпуск", "выходной", "вкр", "консультац"),
        ):
            continue
        strict = is_strict_request(sentence_lower)
        kind = "study" if contains_any(sentence_lower, STUDY_MARKERS) else ("unavailable" if strict else "prefer_off")
        for target_date in dates_for_weekdays(year, month, weekday_numbers):
            if time_ranges:
                for start_value, end_value in time_ranges:
                    constraints.append(
                        TimeConstraint(
                            employee_name=employee_name,
                            date=target_date,
                            kind=kind,
                            start_time=start_value,
                            end_time=end_value,
                            strict=strict or kind == "study",
                            note=sentence.strip(),
                        )
                    )
            elif contains_any(sentence_lower, ("не ставить", "выходной", "отпуск", "занят")):
                constraints.append(
                    TimeConstraint(
                        employee_name=employee_name,
                        date=target_date,
                        kind=kind,
                        start_time=None,
                        end_time=None,
                        strict=strict,
                        note=sentence.strip(),
                    )
                )
    return constraints


def parse_even_odd_week_blocks(employee_name: str, text: str, year: int, month: int) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    parity_map: dict[str, list[tuple[int, time, time]]] = defaultdict(list)
    current_parity: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if not line:
            current_parity = None
            continue
        if "четн" in line and "недел" in line and "неч" not in line:
            current_parity = "even"
            continue
        if "неч" in line and "недел" in line:
            current_parity = "odd"
            continue
        if current_parity is None:
            continue
        match = re.match(
            r"^(?P<weekday>[а-яё]+)\s+(?P<start>\d{1,2}[:.]\d{2})\s*-\s*(?P<end>\d{1,2}[:.]\d{2})$",
            line,
        )
        if not match:
            continue
        weekday_number = resolve_weekday(match.group("weekday"))
        if weekday_number is None:
            continue
        parity_map[current_parity].append(
            (
                weekday_number,
                parse_time_value(match.group("start")),
                parse_time_value(match.group("end")),
            )
        )

    for target_date in iterate_month(year, month):
        parity = "even" if target_date.isocalendar().week % 2 == 0 else "odd"
        for weekday_number, start_value, end_value in parity_map.get(parity, []):
            if target_date.weekday() != weekday_number:
                continue
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind="study",
                    start_time=start_value,
                    end_time=end_value,
                    strict=True,
                    note=f"Расписание {'четной' if parity == 'even' else 'нечетной'} недели",
                )
            )
    return constraints


def parse_specific_day_requests(employee_name: str, text: str, year: int, month: int) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []
    patterns = [
        r"не ставить(?: меня)?\s+(?P<day>\d{1,2})\s*(?P<month_name>[а-яё]+)",
        r"выходной\s+(?P<day>\d{1,2})\s*(?P<month_name>[а-яё]+)",
        r"запись[^.\n]{0,80}?(?:на|у)?\s*(?P<day>\d{1,2})\s*(?P<month_name>[а-яё]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            month_number = resolve_month_from_word(match.group("month_name"))
            if month_number != month:
                continue
            target_date = date(year, month_number, int(match.group("day")))
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind="unavailable",
                    start_time=None,
                    end_time=None,
                    strict=True,
                    note=match.group(0).strip(),
                )
            )
    return constraints


def parse_recurring_daily_windows(employee_name: str, text: str, year: int, month: int, notes: list[str]) -> list[TimeConstraint]:
    constraints: list[TimeConstraint] = []

    if "не ставить работу с 8:00" in text or "не ставить меня с 8:00" in text:
        for target_date in iterate_month(year, month):
            constraints.append(
                TimeConstraint(
                    employee_name=employee_name,
                    date=target_date,
                    kind="prefer_off",
                    start_time=FULL_DAY_START,
                    end_time=time(8, 0),
                    strict=False,
                    note="Просьба не ставить работу с 8:00",
                )
            )

    if "вечернее время" in text or "вечером" in text:
        notes.append("Найдено пожелание про вечернее время. Оно сохранено как заметка и будет учтено при ручной проверке графика.")

    preferred_window = re.search(r"работать\s+с\s*(?P<start>\d{1,2}[:.]\d{2})\s*(?:до|-)\s*(?P<end>\d{1,2}[:.]\d{2})", text)
    if preferred_window:
        notes.append(
            f"Найдено пожелание работать в окне {preferred_window.group('start')} - {preferred_window.group('end')}. "
            "Если нужно зафиксировать это точно, добавьте ручную смену на это время."
        )

    return constraints


def parse_work_date_list_requests(employee_name: str, text: str, year: int, month: int) -> list[WeekendChoice]:
    choices: list[WeekendChoice] = []
    patterns = [
        r"(?:отработать|могу выйти|смогу выйти|готов[а-я]* выйти|готов[а-я]* отработать)\s+(?P<days>\d{1,2}(?:\s*(?:,|и)\s*\d{1,2})+)(?:\s*(?P<month_name>[а-яё]+))?",
    ]

    for sentence in split_sentences(text):
        sentence_lower = sentence.lower()
        for pattern in patterns:
            for match in re.finditer(pattern, sentence_lower, flags=re.IGNORECASE):
                month_number = resolve_month_from_word(match.group("month_name") or "") or month
                if month_number != month:
                    continue
                for day_value in extract_day_numbers(match.group("days")):
                    try:
                        target_date = date(year, month_number, day_value)
                    except ValueError:
                        continue
                    choices.append(
                        WeekendChoice(
                            employee_name=employee_name,
                            date=target_date,
                            shift_code=None,
                            note=sentence.strip(),
                        )
                    )
    return choices


def merge_employees(employees: list[Employee]) -> list[Employee]:
    merged: dict[str, Employee] = {}
    for employee in employees:
        merged.setdefault(employee.name, employee)
    return sorted(merged.values(), key=lambda item: item.name.lower())


def deduplicate_constraints(constraints: list[TimeConstraint]) -> list[TimeConstraint]:
    unique: dict[tuple[str, date, str, time | None, time | None, bool, str], TimeConstraint] = {}
    for constraint in constraints:
        key = (
            constraint.employee_name,
            constraint.date,
            constraint.kind,
            constraint.start_time,
            constraint.end_time,
            constraint.strict,
            constraint.note.strip(),
        )
        unique[key] = constraint
    return sorted(unique.values(), key=lambda item: (item.employee_name.lower(), item.date, item.start_time or FULL_DAY_START, item.kind))


def deduplicate_notes(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for note in notes:
        normalized = note.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def deduplicate_weekend_choices(choices: list[WeekendChoice]) -> list[WeekendChoice]:
    unique: dict[tuple[str, date, str | None], WeekendChoice] = {}
    for choice in choices:
        key = (choice.employee_name, choice.date, choice.shift_code)
        unique[key] = choice
    return sorted(unique.values(), key=lambda item: (item.employee_name.lower(), item.date, item.shift_code or ""))


def split_sentences(text: str) -> list[str]:
    raw_chunks = re.split(r"[\n.!?]+", text)
    return [chunk.strip() for chunk in raw_chunks if chunk.strip()]


def extract_weekday_numbers(text: str) -> list[int]:
    numbers: list[int] = []
    for match in re.finditer(r"[а-яё]+", text):
        weekday_number = resolve_weekday(match.group(0))
        if weekday_number is not None:
            numbers.append(weekday_number)
    return sorted(set(numbers))


def resolve_weekday(word: str) -> int | None:
    normalized = word.strip().lower()
    return WEEKDAY_ALIASES.get(normalized)


def resolve_month_from_word(word: str) -> int | None:
    normalized = word.strip().lower()
    for stem, month_number in MONTH_ALIASES.items():
        if normalized.startswith(stem):
            return month_number
    return None


def dates_for_weekdays(year: int, month: int, weekdays: list[int]) -> list[date]:
    weekday_set = set(weekdays)
    return [target_date for target_date in iterate_month(year, month) if target_date.weekday() in weekday_set]


def iterate_month(year: int, month: int) -> list[date]:
    cursor = date(year, month, 1)
    dates: list[date] = []
    while cursor.month == month:
        dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def iterate_dates(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def build_numeric_date(value: str, year: int) -> date:
    day_value, month_value = re.split(r"[./]", value)
    return date(year, int(month_value), int(day_value))


def parse_time_value(value: str) -> time:
    normalized = value.replace(".", ":")
    hours, minutes = normalized.split(":")
    return time(int(hours), int(minutes))


def find_time_ranges(text: str) -> list[tuple[time, time]]:
    ranges: list[tuple[time, time]] = []
    for start_value, end_value in re.findall(r"(\d{1,2}[:.]\d{2})\s*(?:-|до)\s*(\d{1,2}[:.]\d{2})", text):
        ranges.append((parse_time_value(start_value), parse_time_value(end_value)))
    return ranges


def find_single_time_after_keyword(text: str, keyword: str) -> time | None:
    match = re.search(rf"{re.escape(keyword)}\s*(\d{{1,2}}[:.]\d{{2}})", text)
    if not match:
        return None
    return parse_time_value(match.group(1))


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def is_strict_request(text: str) -> bool:
    if contains_any(text, SOFT_MARKERS):
        return False
    return contains_any(text, STRICT_MARKERS)


def is_positive_work_phrase(text: str) -> bool:
    normalized = text.strip().lower()
    if not contains_any(normalized, POSITIVE_WORK_MARKERS):
        return False
    if contains_any(normalized, ("отпуск", "отдыхаю", "не выходить", "выходной", "не ставить")):
        return False
    if "не могу" in normalized and "смогу выйти" not in normalized and "могу выйти" not in normalized:
        return False
    return True


def extract_day_numbers(value: str) -> list[int]:
    numbers = []
    for match in re.findall(r"\b\d{1,2}\b", value):
        numbers.append(int(match))
    return numbers
