from __future__ import annotations

import re

from app.schemas.academic import TopicRead, UnitRead
from app.schemas.syllabus import SyllabusParseResult

_ROMAN = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6,
    "vii": 7, "viii": 8, "ix": 9, "x": 10,
}
_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}

# "UNIT - I", "Unit-II", "UNIT I : DATABASE SYSTEMS", "Module 1"
_UNIT_RE = re.compile(
    r"^\s*(?:unit|module)\s*[-.:)']?\s*"
    r"([A-Za-z0-9]+)"
    r"\s*[-.:)' ]?\s*(.*)$",
    re.IGNORECASE,
)

_TOPIC_LABEL_RE = re.compile(r"^\s*(?:topic|lesson|subtopic)\s*[-:.>]?\s*(.+)$", re.IGNORECASE)
_BULLET_RE = re.compile(
    r"^\s*(?:[•●‣˗◦o*\–—-]|\(\s*\d+\s*\)|\d+[.、)]|"
    r"\([a-zA-Z0-9]\)|[a-zA-Z]\s*[.)])\s*(.+)$"
)
_SECTION_RE = re.compile(
    r"^\s*(course\s+)?(outcomes?|objectives?)\s*[:]?\s*$", re.IGNORECASE
)

# A content header such as "Processes:" or "Threads and Concurrency :" followed
# by the (possibly comma-separated) topic list on the same line.
_TOPIC_HEADER_RE = re.compile(r"^(.{2,90}?)\s*:\s*(.+)$")

# Separator between atomic topics inside one line. Commas/semicolons only —
# never split on whitespace, hyphens or "and" (they occur inside topic names).
_TOPIC_SEPARATOR_RE = re.compile(r"\s*[,;]\s*")


def _clean_fragment(fragment: str) -> str:
    """Trim punctuation/whitespace artifacts from one candidate topic name."""
    fragment = fragment.strip()
    # Leading/trailing sentence periods, stray separators and wrapping hyphens
    # (a leading ':' appears when a header colon lands on its own wrapped line).
    fragment = fragment.strip(" \t\u00a0").lstrip(":;.,").rstrip(".;,: \t\u00a0").strip()
    # Normalize OCR/PDF whitespace runs ("Ope rating" spaces are ambiguous —
    # only multi-space runs are collapsed; we never re-join or invent words).
    fragment = re.sub(r"\s{2,}", " ", fragment)
    return fragment


def _split_atomic(text: str) -> list[str]:
    """Split one line into atomic topic names (comma/semicolon separated)."""
    topics: list[str] = []
    for fragment in _TOPIC_SEPARATOR_RE.split(text or ""):
        name = _clean_fragment(fragment)
        if name:
            topics.append(name)
    return topics



def _to_unit_number(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    if token in _ROMAN:
        return _ROMAN[token]
    if token in _WORDS:
        return _WORDS[token]
    return None


def _looks_like_header(text: str) -> bool:
    """True when the text before a ':' is a section header, not a topic.

    Headers are short, rarely contain separators, and typically read like a
    noun phrase ("Processes", "Threads and Concurrency"). A long string with
    commas is a topic list, not a header.
    """
    text = text.strip()
    if not (2 <= len(text) <= 60):
        return False
    if "," in text or ";" in text:
        return False
    return True


def _add_topic(unit: UnitRead, name: str) -> None:
    name = name.strip()
    if not name:
        return
    if any(t.topic_name.lower() == name.lower() for t in unit.topics):
        return
    unit.topics.append(TopicRead(topic_name=name, confidence="inferred"))


class SyllabusService:
    unit_pattern = _UNIT_RE
    topic_pattern = _TOPIC_LABEL_RE

    @staticmethod
    def _physical_lines(text: str) -> list[str]:
        """Merge PDF/OCR line-wrapping so one logical topic line stays whole.

        A line that ends with ``,`` or ``;`` is a wrapped continuation of the
        next line (e.g. ``"Process scheduling,"`` / ``"Operations on processes."``).
        Only that unambiguous signal is joined — otherwise lines are left as-is.
        """
        merged: list[str] = []
        buffer = ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if buffer:
                line = f"{buffer} {line}"
                buffer = ""
            if line.endswith((",", ";")):
                buffer = line
                continue
            merged.append(line)
        if buffer:
            merged.append(buffer)
        return merged

    @staticmethod
    def _add_atomic_topics(unit: UnitRead, text: str) -> None:
        """Add each atomic comma-separated fragment as its own topic."""
        for name in _split_atomic(text):
            _add_topic(unit, name)


    def parse_text(self, extracted_text: str, source_file_name: str) -> SyllabusParseResult:
        units: list[UnitRead] = []
        notes: list[str] = []
        warnings: list[str] = []
        current_unit: UnitRead | None = None
        saw_heading = False
        pending_title = False

        for raw_line in self._physical_lines(extracted_text or ""):
            line = raw_line.strip()
            if not line:
                continue

            unit_match = self.unit_pattern.match(line)
            if unit_match:
                number = _to_unit_number(unit_match.group(1))
                if number is None:
                    warnings.append(f"Could not interpret unit marker on line: {line}")
                else:
                    saw_heading = True
                    title = (unit_match.group(2) or "").strip(" :-\u2014.")
                    if _SECTION_RE.fullmatch(title) or re.fullmatch(
                        r"(course\s+title|syllabus|pre[- ]?requisites?)", title, re.IGNORECASE
                    ):
                        title = ""
                    current_unit = UnitRead(unit_number=number, title=title or None, confidence="inferred")
                    units.append(current_unit)
                    pending_title = not title
                    continue

            if current_unit is None:
                notes.append(f"Unassigned line: {line}")
                continue

            if _SECTION_RE.fullmatch(line):
                continue

            # A short standalone line immediately after a heading with no inline
            # title is the unit title (e.g. "UNIT - I" then "Introduction to DB").
            # A colon header ("Processes: A, B, C") or comma list is content,
            # never a title — capturing it as the title would swallow the
            # whole first topic group of the unit.
            header_here = _TOPIC_HEADER_RE.match(line)
            topic_label_match = self.topic_pattern.match(line)
            bullet = _BULLET_RE.match(line)
            is_content_line = bool(
                topic_label_match
                or bullet
                or (header_here and _looks_like_header(header_here.group(1)))
                or "," in line
                or line.endswith(":")
            )
            if pending_title and not is_content_line and len(line) <= 120:
                current_unit.title = line
                pending_title = False
                continue
            pending_title = False

            if topic_label_match:
                # "Topic: A, B, C" — the label part may itself carry a list.
                self._add_atomic_topics(current_unit, topic_label_match.group(1))
            elif bullet:
                self._add_atomic_topics(current_unit, bullet.group(1))
            else:
                header = _TOPIC_HEADER_RE.match(line)
                if header and _looks_like_header(header.group(1)):
                    # "Processes: Process Concept, Process scheduling, ..."
                    # The part before ':' is a GROUP HEADING for the
                    # confirmation UI — it is NOT a question topic (it would
                    # produce vague questions). Only the atomic items after
                    # the colon become topics.
                    self._add_atomic_topics(current_unit, header.group(2))
                else:
                    # A plain line: atomic-split if it is a comma list,
                    # otherwise it is one topic (e.g. a unit title line).
                    self._add_atomic_topics(current_unit, line)

        if not saw_heading:
            warnings.append("No explicit unit headings were detected; faculty confirmation is required.")

        if not units:
            notes.append("No explicit unit headings were detected; faculty confirmation is required.")
            warnings.append(
                "We couldn't confidently read the syllabus structure. Please upload a "
                "clearer PDF/DOCX/image or add the units manually."
            )

        return SyllabusParseResult(
            source_file_name=source_file_name,
            units=units,
            confidence="inferred" if saw_heading else "unknown",
            notes=notes,
            warnings=warnings,
        )

    def extract_units(self, parsed_result: SyllabusParseResult) -> list[int]:
        return [unit.unit_number for unit in parsed_result.units]


async def _resolve_subject(session, identifier: str):
    """Resolve a Subject row from a UUID, code, or name (creating if new).

    The faculty UI works with subject names; the ``subjects`` table keys on
    UUIDs. Mirrors the resolution already used by the generation audit-graph:
    reuse by id/code/name, otherwise create the subject once.
    """
    from uuid import UUID, uuid4

    from sqlalchemy import func
    from sqlalchemy.future import select

    from app.models.academic import Subject

    ident = (identifier or "").strip() or "default"
    try:
        as_uuid = str(UUID(ident))
    except (ValueError, AttributeError, TypeError):
        as_uuid = None

    subject = await session.get(Subject, as_uuid) if as_uuid else None
    if subject is None:
        subject = (
            await session.execute(
                select(Subject).where(func.lower(Subject.code) == ident.lower())
            )
        ).scalars().first()
    if subject is None:
        subject = (
            await session.execute(
                select(Subject).where(func.lower(Subject.name) == ident.lower())
            )
        ).scalars().first()
    if subject is None:
        subject = Subject(id=str(uuid4()), code=ident, name=ident, is_active=True)
        session.add(subject)
        await session.flush()
    return subject


async def persist_confirmed_syllabus(
    session, subject_id: str, source_file_name: str, units
) -> str:
    """Persist a faculty-confirmed syllabus structure.

    Accepts the faculty-facing unit payloads (topics as plain strings) as well
    as :class:`UnitRead` values. Creates or reuses the ``Syllabus`` for the
    resolved subject, adds a new ``SyllabusVersion`` and its ``SyllabusUnit`` /
    ``SyllabusTopic`` rows. Returns the new version id.
    """
    from uuid import uuid4

    from sqlalchemy.future import select

    from app.models.academic import Syllabus, SyllabusTopic, SyllabusUnit, SyllabusVersion
    from app.schemas.academic import TopicRead, UnitRead

    normalized: list[UnitRead] = []
    for unit in units:
        topics = [
            topic if isinstance(topic, TopicRead) else TopicRead(topic_name=str(topic), confidence="confirmed")
            for topic in getattr(unit, "topics", []) or []
        ]
        normalized.append(
            unit if isinstance(unit, UnitRead) else UnitRead(
                unit_number=unit.unit_number,
                title=unit.title,
                confidence="confirmed",
                topics=topics,
            )
        )

    subject = await _resolve_subject(session, subject_id)

    stmt = select(Syllabus).where(Syllabus.subject_id == subject.id)
    syllabus = (await session.execute(stmt)).scalars().first()

    if syllabus is None:
        syllabus = Syllabus(
            subject_id=subject.id,
            title=source_file_name or "Confirmed Syllabus",
        )
        session.add(syllabus)
        await session.flush()
        version_number = 1
    else:
        last = (await session.execute(
            select(SyllabusVersion)
            .where(SyllabusVersion.syllabus_id == syllabus.id)
            .order_by(SyllabusVersion.version_number.desc())
        )).scalars().first()
        version_number = (last.version_number + 1) if last else 1

    version = SyllabusVersion(
        syllabus_id=syllabus.id,
        version_number=version_number,
        source_file_name=source_file_name,
        structured_data={"units": [unit.model_dump() for unit in normalized]},
    )
    session.add(version)
    await session.flush()

    for unit_model in normalized:
        unit_row = SyllabusUnit(
            syllabus_version_id=version.id,
            unit_number=unit_model.unit_number,
            title=unit_model.title,
            confidence="confirmed",
        )
        session.add(unit_row)
        await session.flush()
        for topic in unit_model.topics:
            session.add(
                SyllabusTopic(
                    unit_id=unit_row.id,
                    topic_name=topic.topic_name,
                    page_reference=topic.page_reference,
                    confidence="confirmed",
                )
            )

    await session.commit()
    return str(version.id)
