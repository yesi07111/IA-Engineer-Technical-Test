import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from emporio_agent.domain.models import PolicySection
from emporio_agent.errors import DataLoadError

HEADING = re.compile(r"^(\d+)(?:\.(\d+))?\.?\s+([A-ZÀ-Ý].{2,80})$")
PAGE_NOISE = re.compile(r"^(Empório da Música Manual de Políticas e Procedimentos|Página \d+)$")


def read_pdf_lines(pdf_path: Path) -> list[str]:
    """Extracts the text lines of a PDF, keeping the table columns readable.

    Args:
        pdf_path: Location of the PDF.

    Returns:
        Non empty lines without page headers or footers. Table columns are joined with " | ".

    Raises:
        DataLoadError: If the file is missing or is not a readable PDF.
    """
    if not pdf_path.is_file():
        raise DataLoadError(f"Policy file not found: {pdf_path}")
    try:
        pages = PdfReader(pdf_path).pages
        raw_text = "\n".join(page.extract_text(extraction_mode="layout") for page in pages)
    except (PdfReadError, OSError) as error:
        raise DataLoadError(f"Could not read {pdf_path.name}: {error}") from error

    lines = []
    for raw_line in raw_text.splitlines():
        # This is for turning the big gaps of the table layout into column separators
        line = re.sub(r"\s{2,}", " | ", raw_line.strip())
        if line and not PAGE_NOISE.match(line):
            lines.append(line)
    return lines


def is_next_heading(number: tuple[int, int], last: tuple[int, int]) -> bool:
    """Checks that a heading number follows the previous one.

    This is what stops numbered lists like "1. Saudação: ..." from being taken as sections.

    Args:
        number: Candidate as (section, subsection), subsection 0 for top level.
        last: Last accepted heading in the same format.

    Returns:
        True for the next section (3 after 2.x) or the next subsection (2.2 after 2.1).
    """
    section, subsection = number
    last_section, last_subsection = last
    if subsection == 0:
        return section == last_section + 1
    return section == last_section and subsection == last_subsection + 1


def make_section(heading: tuple[str, str], body: list[str]) -> PolicySection:
    """Builds a section from its heading and its lines.

    Args:
        heading: Pair of (number, title).
        body: Lines of text under the heading.

    Returns:
        The PolicySection.
    """
    return PolicySection(number=heading[0], title=heading[1], text="\n".join(body))


def split_policy_into_sections(pdf_path: Path) -> list[PolicySection]:
    """Splits the policy manual into its numbered sections.

    Args:
        pdf_path: Location of the policy PDF.

    Returns:
        One PolicySection per heading, like "4.1 Direito de Arrependimento". The cover
        page before section 1 is skipped because section 1.2 repeats its data. Headings
        with no text of their own (e.g. "5." right before "5.1") are not returned.

    Raises:
        DataLoadError: If the PDF can not be read or has no numbered sections.
    """
    sections: list[PolicySection] = []
    current: tuple[str, str] | None = None
    body: list[str] = []
    last_number = (0, 0)
    parent_title = ""

    for line in read_pdf_lines(pdf_path):
        match = HEADING.match(line)
        if match and ":" not in line:
            number = (int(match.group(1)), int(match.group(2) or 0))
            if is_next_heading(number, last_number):
                if current and body:
                    sections.append(make_section(current, body))
                title = match.group(3).strip()
                if number[1] == 0:
                    parent_title, label = title, str(number[0])
                else:
                    # This is for keeping the parent topic in the title, it helps the search
                    label, title = f"{number[0]}.{number[1]}", f"{parent_title} › {title}"
                current, body, last_number = (label, title), [], number
                continue
        if current:
            body.append(line)

    if current and body:
        sections.append(make_section(current, body))
    if not sections:
        raise DataLoadError(f"No numbered sections found in {pdf_path.name}")
    return sections
