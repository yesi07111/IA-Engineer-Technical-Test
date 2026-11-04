"""Builds the submission PDF from the project README and the technical documentation.

The PDF has a cover, document control and contents, then Part I (the README), Part II
(the documents in docs/, in order) and two appendices: the example conversations and the
evaluation results. The HTML is printed with headless Chrome or Edge and a header and
footer with page numbers is added afterwards.

Usage (from the project root, after `pip install -e ".[docs]"`):
    python scripts/build_docs_pdf.py
    python scripts/build_docs_pdf.py --output "My Report.pdf"
"""

import argparse
import base64
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import markdown
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/yesi07111/IA-Engineer-Technical-Test"
AUTHOR = "Yesenia Valdés Rodríguez"
CONTACT = "yeseniavaldesrdg@gmail.com"
POSITION = "AI Engineer – Full-Stack para Aplicações com IA Generativa"
TITLE = "Empório da Música — Customer Service Agent"
DEFAULT_OUTPUT = ROOT / "dist" / f"{AUTHOR} - {POSITION}.pdf"

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
]

STYLE = (Path(__file__).with_name("docs_pdf.css")).read_text(encoding="utf-8")


def find_browser() -> str:
    """Finds a Chromium based browser to print the HTML.

    Returns:
        The path or command of the browser. EMPORIO_BROWSER wins when it is set.

    Raises:
        SystemExit: If no browser is found.
    """
    configured = os.environ.get("EMPORIO_BROWSER")
    for candidate in [configured, *BROWSER_CANDIDATES]:
        if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
            return candidate
    sys.exit("Chrome or Edge not found. Install one or set EMPORIO_BROWSER to its path.")


def make_slugger(prefix: str):
    """Creates a heading id function so each document gets its own anchor namespace.

    Args:
        prefix: Text put before every id, e.g. "readme-".

    Returns:
        A slugify function for the markdown toc extension.
    """

    def slugify(value: str, separator: str) -> str:
        """Turns a heading into an id.

        Args:
            value: Heading text.
            separator: Word separator, required by the extension and not used.

        Returns:
            The id, e.g. "readme-quick-start".
        """
        return prefix + re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    return slugify


def render_markdown(text: str, prefix: str) -> str:
    """Converts Markdown to HTML with tables and heading ids.

    Args:
        text: Markdown source.
        prefix: Prefix for the heading ids.

    Returns:
        The HTML fragment.
    """
    return markdown.markdown(
        text,
        extensions=["tables", "toc", "sane_lists", "fenced_code"],
        extension_configs={"toc": {"slugify": make_slugger(prefix)}},
    )


def separate_lists(text: str) -> str:
    """Adds the blank line Markdown needs before a list that follows a paragraph.

    Args:
        text: Markdown source.

    Returns:
        The same text, with lists that render as lists.
    """
    lines: list[str] = []
    in_code = False
    for line in text.replace("\u2022 ", "- ").split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        is_item = re.match(r"^(- |\d+\. )", line)
        previous = lines[-1] if lines else ""
        if (
            not in_code
            and is_item
            and previous.strip()
            and not re.match(r"^(- |\d+\. |\|)", previous)
        ):
            lines.append("")
        lines.append(line)
    return "\n".join(lines)


def embed_images(html: str, base_dir: Path) -> str:
    """Inlines local SVG images, so the PDF does not depend on file paths.

    Args:
        html: Rendered HTML.
        base_dir: Folder the image paths are relative to.

    Returns:
        HTML with images as data URIs, wrapped in a figure.
    """

    def inline(match: re.Match[str]) -> str:
        """Replaces one image tag by its embedded version.

        Args:
            match: Regex match with the alt text and the source path.

        Returns:
            The new image tag, or the original one when the file does not exist.
        """
        alt, source = match.group(1), match.group(2)
        path = (base_dir / source).resolve()
        if not path.is_file():
            return match.group(0)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'<img class="diagram" src="data:image/svg+xml;base64,{data}" alt="{alt}">'

    return re.sub(r'<img alt="([^"]*)" src="([^"]+)"\s*/?>', inline, html)


def point_links(text: str, doc_anchors: dict[str, str], own_prefix: str) -> str:
    """Rewrites Markdown links so they work inside the PDF.

    Links to other documents of docs/ jump to their section, links to the same page get
    the document prefix and any other repository file points to GitHub.

    Args:
        text: Markdown source.
        doc_anchors: File name of each document in docs/ mapped to its anchor.
        own_prefix: Prefix of the heading ids of this document.

    Returns:
        The Markdown with updated links.
    """

    def fix(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith(("http", "mailto:")) or match.group(0).startswith("!"):
            return match.group(0)
        if target.startswith("#"):
            return f"[{label}](#{own_prefix}{target[1:]})"
        name = Path(target).name
        if name in doc_anchors:
            return f"[{label}](#{doc_anchors[name]})"
        clean = target.removeprefix("../").removeprefix("./")
        kind = "blob" if Path(clean).suffix else "tree"
        return f"[{label}]({REPO_URL}/{kind}/main/{clean})"

    return re.sub(r"!?\[([^\]]*)\]\(([^)]+)\)", fix, text)


def build_readme_part(doc_anchors: dict[str, str]) -> str:
    """Renders the project README as Part I.

    Args:
        doc_anchors: Anchors of the documents in docs/.

    Returns:
        HTML of Part I.
    """
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    text = re.sub(r"^# .*\n", "", text, count=1)
    text = re.sub(r"^\[!\[CI\].*\n", "", text, flags=re.M)
    # This is for dropping the README's own contents list, the PDF has a full one
    text = re.sub(r"^## Contents\n.*?^---\n", "", text, count=1, flags=re.M | re.S)
    text = point_links(separate_lists(text), doc_anchors, "readme-")
    html = embed_images(render_markdown(text, "readme-"), ROOT)
    return (
        '<section class="part"><h1 id="part-1" class="part-title">Part I — Project README</h1>'
        f"{html}</section>"
    )


def build_docs_part(doc_files: list[Path], doc_anchors: dict[str, str]) -> str:
    """Renders every document of docs/ as Part II, one heading level below the part.

    Args:
        doc_files: Numbered documents, in order.
        doc_anchors: Anchors of the documents.

    Returns:
        HTML of Part II.
    """
    sections = []
    for path in doc_files:
        prefix = f"doc{path.name[:2]}-"
        text = point_links(separate_lists(path.read_text(encoding="utf-8")), doc_anchors, prefix)
        # This is for nesting the documents under the part title, "#" becomes "##"
        text = re.sub(r"^(#+) ", lambda m: "#" + m.group(1) + " ", text, flags=re.M)
        html = embed_images(render_markdown(text, prefix), path.parent)
        sections.append(f'<section class="doc" id="{doc_anchors[path.name]}">{html}</section>')
    return (
        '<section class="part"><h1 id="part-2" class="part-title">Part II — Technical '
        f"Documentation</h1>{''.join(sections)}</section>"
    )


def build_examples_appendix() -> str:
    """Renders the example conversations as Appendix A.

    Returns:
        HTML of the appendix.
    """
    blocks = []
    for number, path in enumerate(sorted((ROOT / "examples/conversations").glob("*.md")), 1):
        text = path.read_text(encoding="utf-8")
        title = re.search(r"^# (.+)$", text, re.M)
        goal = re.search(r"\*\*Goal:\*\* (.+?)\s*$", text, re.M)
        turns = text.split("\n---\n", 1)[-1]
        blocks.append(
            f'<section class="example"><h3>A.{number} {title.group(1) if title else path.stem}</h3>'
            f'<p class="goal"><strong>Objective:</strong> {goal.group(1) if goal else ""}</p>'
            f"{render_markdown(separate_lists(turns), f'ex{number}-')}</section>"
        )
    return (
        '<section class="appendix"><h1 id="appendix-a" class="part-title">Appendix A — Example '
        "Conversations</h1><p>Conversations generated with the real model by "
        "<code>python scripts/generate_examples.py</code>. Each answer lists the tools the agent "
        "called, which shows when it consulted data and when it consulted policies. Conversation "
        f"A.3 is the non-trivial scenario required by the brief.</p>{''.join(blocks)}</section>"
    )


def build_evaluation_appendix() -> str:
    """Renders the summary table of the latest evaluation as Appendix B.

    Returns:
        HTML of the appendix, or an empty string when there is no report yet.
    """
    report_file = ROOT / "evals/report.md"
    if not report_file.is_file():
        return ""
    report = report_file.read_text(encoding="utf-8").split("## Transcripts")[0]
    header = report.split("| Case |")[0]
    table = "| Case |" + report.split("| Case |", 1)[1]
    table = table.replace("✅ pass", "Pass").replace("❌ ", "Fail: ")
    model = re.search(r"\*\*Model:\*\* `([^`]+)`", header)
    passed = re.search(r"Cases passed:\*\* (\d+/\d+)", header)
    tools = re.search(r"Correct tool choice:\*\* (\d+/\d+)", header)
    summary = (
        "<p>Scenarios run with <code>python scripts/evaluate_agent.py</code> against "
        f"<code>{model.group(1) if model else 'the configured model'}</code>. "
        f"<strong>Scenarios passed: {passed.group(1) if passed else '-'}</strong>; correct tool "
        f"choice in {tools.group(1) if tools else '-'} of the scenarios that check it. The full "
        f'transcripts are in <a href="{REPO_URL}/blob/main/evals/report.md">'
        "evals/report.md</a>.</p>"
    )
    return (
        '<section class="appendix"><h1 id="appendix-b" class="part-title">Appendix B — '
        f"Evaluation Results</h1>{summary}{render_markdown(table, 'ev-')}</section>"
    )


def build_contents(body: str) -> str:
    """Builds the table of contents from the part, document and section headings.

    Args:
        body: HTML of the parts and appendices.

    Returns:
        HTML list with links.
    """
    rows = []
    for level, anchor, title in re.findall(r'<h([123]) [^>]*?id="([^"]+)"[^>]*>(.*?)</h\1>', body):
        if anchor.startswith("readme-contents"):
            continue
        css = {"1": "toc-part", "2": "toc-l1", "3": "toc-l2"}[level]
        if level == "3" and not re.match(r"\d+\.\d+", title):
            continue
        rows.append(
            f'<li class="{css}"><a href="#{anchor}">{re.sub("<[^>]+>", "", title)}</a></li>'
        )
    return f'<ul class="toc">{"".join(rows)}</ul>'


def build_html() -> str:
    """Assembles the whole document as one HTML page.

    Returns:
        The HTML ready to print.
    """
    doc_files = sorted((ROOT / "docs").glob("[0-9][0-9]-*.md"))
    doc_anchors = {path.name: f"doc-{path.name[:2]}" for path in doc_files}
    today = date.today().strftime("%B %d, %Y").replace(" 0", " ")
    body = (
        build_readme_part(doc_anchors)
        + build_docs_part(doc_files, doc_anchors)
        + build_examples_appendix()
        + build_evaluation_appendix()
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{TITLE} — Technical Documentation</title><style>{STYLE}</style></head><body>
<section class="cover"><div class="accent"></div><div class="cover-inner">
  <div class="brand">Artefact · AI Engineer Technical Case</div>
  <h1 class="cover-title">Empório da Música<br>Customer Service Agent</h1>
  <div class="subtitle">Project README and Technical Documentation</div>
  <div class="doc-type">Technical Report</div></div>
  <div class="cover-meta"><table>
    <tr><td>Author</td><td>{AUTHOR}</td></tr>
    <tr><td>Position</td><td>{POSITION}</td></tr>
    <tr><td>Contact</td><td>{CONTACT}</td></tr>
    <tr><td>Repository</td><td><a href="{REPO_URL}">{REPO_URL}</a></td></tr>
    <tr><td>Version / Date</td><td>1.0 · {today}</td></tr>
  </table></div></section>
<section class="front">
  <h2>Document Control</h2>
  <table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>
    <tr><td>Document</td><td>Technical Report — {TITLE}</td></tr>
    <tr><td>Version</td><td>1.0 (final submission)</td></tr>
    <tr><td>Date</td><td>{today}</td></tr>
    <tr><td>Author</td><td>{AUTHOR}</td></tr>
    <tr><td>Audience</td><td>Artefact technical evaluation team</td></tr>
    <tr><td>Source</td><td>Generated by <code>scripts/build_docs_pdf.py</code> from
      <code>README.md</code> and <code>docs/</code> of the repository</td></tr>
    <tr><td>Repository</td><td><a href="{REPO_URL}">{REPO_URL}</a></td></tr>
    <tr><td>Language model</td><td>Google Gemini 3.5 Flash</td></tr>
  </tbody></table>
  <h2>Purpose of this Document</h2>
  <p>This report documents the solution delivered for the written case of the Artefact
  selection process: a prototype customer service agent for Empório da Música. Part I
  reproduces the project README, which explains how to run the project and summarises the
  technical decisions, assumptions, limitations and use of AI assistants. Part II contains
  the technical documentation: architecture, decision record, business rules, data analysis,
  security, error handling, quality assurance, operations and roadmap. The appendices show
  the agent in action and the results of its evaluation with the real language model.</p>
  <h2>Reading Guide</h2>
  <table><thead><tr><th>If you want to…</th><th>Read</th></tr></thead><tbody>
    <tr><td>Run the project and get a summary</td><td>Part I — Project README</td></tr>
    <tr><td>Get the overall picture and results</td><td>Part II, section 1 (Overview)</td></tr>
    <tr><td>Understand the design and why it was chosen</td><td>Part II, sections 2 and 3</td></tr>
    <tr><td>Check how store rules and data issues are handled</td>
      <td>Part II, sections 4 and 5</td></tr>
    <tr><td>Review safety, errors and quality evidence</td>
      <td>Part II, sections 6 and 7; Appendix B</td></tr>
    <tr><td>See the agent in action</td><td>Appendix A</td></tr>
  </tbody></table>
</section>
<section class="front"><h2>Contents</h2>{build_contents(body)}</section>
{body}</body></html>"""


def print_to_pdf(html: str, browser: str, target: Path) -> None:
    """Prints the HTML to PDF with a headless browser.

    Args:
        html: Document HTML.
        browser: Browser executable.
        target: Where to write the PDF without header and footer.

    Raises:
        SystemExit: If the browser does not produce the file.
    """
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "report.html"
        page.write_text(html, encoding="utf-8")
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={Path(folder) / 'profile'}",
            f"--print-to-pdf={target}",
            page.as_uri(),
        ]
        subprocess.run(command, capture_output=True, timeout=180, check=False)
    if not target.is_file():
        sys.exit(f"The browser did not create the PDF. Command: {' '.join(command)}")


def add_header_and_footer(source: Path, target: Path) -> int:
    """Stamps a header and a footer with page numbers on every page but the cover.

    Args:
        source: PDF printed by the browser.
        target: Final PDF.

    Returns:
        Number of pages.
    """
    reader = PdfReader(source)
    total = len(reader.pages)
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index > 0:
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            buffer = io.BytesIO()
            overlay = canvas.Canvas(buffer, pagesize=(width, height))
            margin = 51
            overlay.setStrokeColor(HexColor("#c8102e"))
            overlay.setLineWidth(0.8)
            overlay.line(margin, height - 44, width - margin, height - 44)
            overlay.setFont("Helvetica", 8.5)
            overlay.setFillColor(HexColor("#4a5868"))
            overlay.drawString(margin, height - 38, TITLE)
            overlay.drawRightString(width - margin, height - 38, "Technical Report · v1.0")
            overlay.setStrokeColor(HexColor("#d5dce4"))
            overlay.line(margin, 40, width - margin, 40)
            overlay.drawString(margin, 28, f"{AUTHOR} · Artefact AI Engineer Technical Case")
            overlay.drawRightString(width - margin, 28, f"Page {index + 1} of {total}")
            overlay.save()
            buffer.seek(0)
            page.merge_page(PdfReader(buffer).pages[0])
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": f"{TITLE} — Technical Report",
            "/Author": AUTHOR,
            "/Subject": "Artefact AI Engineer technical case",
            "/Keywords": "LLM, agent, LangChain, Gemini, tool calling, RAG",
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as file:
        writer.write(file)
    return total


def main() -> None:
    """Builds the HTML, prints it and adds header and footer."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="PDF to create")
    parser.add_argument("--html", type=Path, help="Also save the HTML here, for review")
    args = parser.parse_args()

    html = build_html()
    if args.html:
        args.html.write_text(html, encoding="utf-8")
    with tempfile.TemporaryDirectory() as folder:
        raw = Path(folder) / "raw.pdf"
        print_to_pdf(html, find_browser(), raw)
        pages = add_header_and_footer(raw, args.output.resolve())
    print(f"Saved {args.output} ({pages} pages)")


if __name__ == "__main__":
    main()
