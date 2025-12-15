from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import re

# templates 경로
TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,
)

ARTICLE_RE = re.compile(r"^Article\s+\d+", re.IGNORECASE)
SECTION_RE = re.compile(r"^\(?\d+\)?")

def _parse_markdown(markdown: str):
    """
    markdown → Article / Section 구조로 변환
    """
    lines = [l.strip() for l in markdown.split("\n") if l.strip()]
    blocks = []
    current_article = None

    for line in lines:
        if ARTICLE_RE.match(line):
            if current_article:
                blocks.append(current_article)
            current_article = {
                "type": "article",
                "title": line,
                "sections": [],
            }

        elif current_article and SECTION_RE.match(line):
            num, _, rest = line.partition(" ")
            current_article["sections"].append(
                {"number": num, "text": rest.strip()}
            )

        else:
            if current_article:
                current_article["sections"].append(
                    {"number": "", "text": line}
                )
            else:
                blocks.append(
                    {"type": "paragraph", "text": line}
                )

    if current_article:
        blocks.append(current_article)

    return blocks


def translated_markdown_to_pdf(
    *,
    translated_result: dict,
    output_path: Path,
    title: str,
):
    """
    LLMTranslator.translate_markdown 결과 → PDF
    """

    pages = []

    for batch in translated_result["results"]:
        translated = batch.get("translated", [])
        if not isinstance(translated, list):
            continue

        for p in translated:
            blocks = _parse_markdown(p.get("markdown", ""))
            pages.append(
                {
                    "page": p.get("page"),
                    "blocks": blocks,
                }
            )

    template = env.get_template("translated_markdown.html.j2")
    html = template.render(
        title=title,
        pages=pages,
    )

    HTML(string=html).write_pdf(output_path)
