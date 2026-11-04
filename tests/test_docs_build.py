import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("markdown")
pytest.importorskip("reportlab")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_docs_pdf  # noqa: E402


@pytest.fixture(scope="module")
def html():
    return build_docs_pdf.build_html()


def test_every_document_of_docs_is_included(html):
    for path in sorted((ROOT / "docs").glob("[0-9][0-9]-*.md")):
        title = path.read_text(encoding="utf-8").splitlines()[0].removeprefix("# ")
        assert title in html, f"{path.name} is missing from the PDF"


def test_readme_is_included_as_part_one(html):
    assert "Part I — Project README" in html
    assert "Use of AI coding assistants" in html
    assert "Quick start" in html


def test_diagrams_are_embedded(html):
    assert html.count('src="data:image/svg+xml;base64,') >= 3


def test_no_link_points_to_a_local_markdown_file(html):
    local_links = re.findall(r'href="(?!https?:|#|mailto:)([^"]+)"', html)

    assert local_links == []


def test_internal_links_point_to_existing_anchors(html):
    anchors = set(re.findall(r'id="([^"]+)"', html))
    targets = set(re.findall(r'href="#([^"]+)"', html))

    assert targets - anchors == set()


def test_appendices_are_present(html):
    assert "Appendix A — Example Conversations" in html
    assert "Appendix B — Evaluation Results" in html
