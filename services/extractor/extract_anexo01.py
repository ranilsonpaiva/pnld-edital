#!/usr/bin/env python3
"""Extract sections, numbered items, and lettered alíneas from PNLD Anexo 01 PDFs."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PdfReader

SECTION_RE = re.compile(
    r"^(?P<code>\d{1,2})(?:\.|\s*[-–—])\s+(?P<title>[A-ZÁÉÍÓÚÂÊÔÃÕÇ].{3,140})$"
)
INLINE_ALINEA_RE = re.compile(
    r"^(?P<head>.*?[:;])\s+(?P<letter>[a-z])\)\s+(?P<body>\S.*)$"
)
# 3.1 / 3.1. / 4.2.2 / 2.8.1 — allow optional trailing dot
ITEM_RE = re.compile(
    r"^(?P<code>\d{1,2}(?:\.\d+){1,4})\.?\s+(?P<body>\S.*)$"
)
ALINEA_RE = re.compile(
    r"^(?P<letter>[a-z])\)\s+(?P<body>\S.*)$"
)
BULLET_RE = re.compile(r"^[•●▪︎-]\s+(?P<body>\S.*)$")
PAGE_NUM_RE = re.compile(r"^\d{1,3}$")
FOOTER_NOISE_RE = re.compile(
    r"(?i)^(edital de convocação|pnld anos|anexo 01|página\s+\d+|ministério da educação)"
)

SECTION_TYPE_MAP = [
    (re.compile(r"(?i)crit[eé]rios?\s+comuns"), "avaliativo_comum"),
    (re.compile(r"(?i)crit[eé]rios?\s+das\s+obras"), "avaliativo_objeto"),
    (re.compile(r"(?i)crit[eé]rios?\s+avaliativos?\s+espec"), "avaliativo_componente"),
    (re.compile(r"(?i)crit[eé]rios?\s+avaliativos?\s+das\s+obras\s+de\s+apoio"), "avaliativo_objeto"),
    (re.compile(r"(?i)caracter[ií]sticas"), "caracteristica_obra"),
    (re.compile(r"(?i)objetos?\s+digitais|pdf\s+interativo"), "objeto_digital"),
    (re.compile(r"(?i)aprova[cç][aã]o|reprova[cç][aã]o|resultado|recurso|avalia[cç][aã]o\s+pedag"), "resultado_aprovacao"),
    (re.compile(r"(?i)^do\s+objeto|^introdu"), "contexto"),
]


@dataclass
class ExtractedItem:
    code: str
    parent_code: str | None
    kind: str  # section | item | alinea | bullet
    statement: str
    section_code: str | None
    section_title: str | None
    criterion_type: str
    page_start: int
    page_end: int
    mandatory_guess: bool = True
    applies_to: list[str] = field(default_factory=list)


def infer_criterion_type(section_title: str | None) -> str:
    if not section_title:
        return "normativo"
    for pattern, type_id in SECTION_TYPE_MAP:
        if pattern.search(section_title):
            return type_id
    return "normativo"


def infer_applies_to(text: str, section_title: str | None) -> list[str]:
    low = text.lower()
    title = (section_title or "").lower()
    tags: list[str] = []
    if "professor" in low or "lip" in low:
        tags.append("livro_professor")
    if "estudante" in low or "lie" in low or "aluno" in low:
        tags.append("livro_estudante")
    if "pdf interativo" in low or "objeto digital" in low or "objeto digital" in title:
        tags.append("pdf_interativo")
    if "coleção" in low or "colecoes" in low:
        tags.append("colecao")
    if "detentor" in low:
        tags.append("detentor")
    if not tags:
        if "apoio" in title:
            tags.append("livro_professor")
        else:
            tags.append("obra")
    return tags


def load_pages(path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages):
        pages.append((idx + 1, page.extract_text() or ""))
    return pages


def normalize_lines(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Flatten pages into (page_no, line) skipping obvious noise."""
    out: list[tuple[int, str]] = []
    for page_no, text in pages:
        raw_lines = text.splitlines()
        # Drop leading page number if present as first non-empty line
        started = False
        for raw in raw_lines:
            line = re.sub(r"[ \t]+", " ", raw).strip()
            if not line:
                continue
            if not started and PAGE_NUM_RE.match(line):
                started = True
                continue
            started = True
            if FOOTER_NOISE_RE.match(line) and len(line) < 80:
                continue
            out.append((page_no, line))
    return out


def is_section(line: str) -> re.Match[str] | None:
    match = SECTION_RE.match(line)
    if not match:
        return None
    # Avoid matching "3.1 Something" — SECTION_RE requires single digit group only
    # But "4. Critérios..." is valid. Reject if title looks like continuation lowercase start? OK.
    code = match.group("code")
    # Ignore fake sections from years like "2027." etc — code already 1-2 digits
    if int(code) > 30:
        return None
    return match


def merge_wrapped_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str, str]]:
    """
    Return list of (page, kind_hint_line, merged_paragraph_starting_at_line).
    We keep atomic structural lines; wrap continuations into previous unit later.
    """
    return [(p, "line", t) for p, t in lines]


def split_inline_alineas(items: list[ExtractedItem]) -> list[ExtractedItem]:
    """Split statements that embed a) b) c) sequences into child alíneas."""
    out: list[ExtractedItem] = []
    letter_body = re.compile(r"^([a-z])\)\s+(.*)$", re.S)

    for item in items:
        if item.kind != "item":
            out.append(item)
            continue

        chunks: list[str] = []
        buf = ""
        for token in re.split(r"(?=(?<![A-Za-z0-9])[a-z]\))", item.statement):
            if not token:
                continue
            stripped = token.lstrip()
            if letter_body.match(stripped) and buf:
                chunks.append(buf.strip())
                buf = stripped
            else:
                buf += token
        if buf:
            chunks.append(buf.strip())

        if len(chunks) <= 1 or not any(letter_body.match(c) for c in chunks[1:]):
            out.append(item)
            continue

        head = chunks[0]
        if letter_body.match(head):
            out.append(item)
            for chunk in chunks:
                m = letter_body.match(chunk)
                if not m:
                    continue
                out.append(
                    ExtractedItem(
                        code=f"{item.code}.{m.group(1)}",
                        parent_code=item.code,
                        kind="alinea",
                        statement=m.group(2).strip(),
                        section_code=item.section_code,
                        section_title=item.section_title,
                        criterion_type=item.criterion_type,
                        page_start=item.page_start,
                        page_end=item.page_end,
                        mandatory_guess=item.mandatory_guess,
                        applies_to=list(item.applies_to),
                    )
                )
            continue

        item.statement = head.rstrip(" :;")
        out.append(item)
        existing_letters = {
            i.code.rsplit(".", 1)[-1]
            for i in items
            if i.parent_code == item.code and i.kind == "alinea"
        }
        for chunk in chunks[1:]:
            m = letter_body.match(chunk)
            if not m:
                continue
            letter = m.group(1)
            if letter in existing_letters:
                continue
            out.append(
                ExtractedItem(
                    code=f"{item.code}.{letter}",
                    parent_code=item.code,
                    kind="alinea",
                    statement=m.group(2).strip(),
                    section_code=item.section_code,
                    section_title=item.section_title,
                    criterion_type=item.criterion_type,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    mandatory_guess=item.mandatory_guess,
                    applies_to=list(item.applies_to),
                )
            )
    return out


def skip_toc_section_line(line: str) -> bool:
    """Skip sumário entries with dotted leaders / trailing page numbers."""
    if re.search(r"\.{3,}", line):
        return True
    if re.search(r"\s\d{1,3}\s*$", line) and "Crit" in line:
        # e.g. title ............. 13
        if re.search(r"\.\s*\d+\s*$", line) or re.search(r"\s{2,}\d+\s*$", line):
            return True
    return False


def extract(path: Path, edital_id: str, version: str) -> dict:
    pages = load_pages(path)
    lines = normalize_lines(pages)

    items: list[ExtractedItem] = []
    current_section_code: str | None = None
    current_section_title: str | None = None
    current_item_code: str | None = None
    buffer: list[str] = []
    buffer_page_start: int | None = None
    buffer_page_end: int | None = None
    buffer_kind: str | None = None
    buffer_code: str | None = None
    buffer_parent: str | None = None

    def flush() -> None:
        nonlocal buffer, buffer_page_start, buffer_page_end
        nonlocal buffer_kind, buffer_code, buffer_parent
        if not buffer or not buffer_kind or not buffer_code:
            buffer = []
            return
        statement = " ".join(buffer).strip()
        statement = re.sub(r"\s+", " ", statement)
        # Trim trailing partial page artifacts
        if len(statement) < 8:
            buffer = []
            return
        ctype = infer_criterion_type(current_section_title)
        if buffer_kind == "section":
            ctype = "contexto" if ctype == "normativo" else ctype
        mandatory = True
        low = statement.lower()
        if any(x in low for x in ["poderá", "optativ", "sugest"]):
            mandatory = False
        items.append(
            ExtractedItem(
                code=buffer_code,
                parent_code=buffer_parent,
                kind=buffer_kind,
                statement=statement,
                section_code=current_section_code,
                section_title=current_section_title,
                criterion_type=ctype if buffer_kind != "section" else infer_criterion_type(statement),
                page_start=buffer_page_start or 1,
                page_end=buffer_page_end or buffer_page_start or 1,
                mandatory_guess=mandatory,
                applies_to=infer_applies_to(statement, current_section_title),
            )
        )
        buffer = []
        buffer_kind = None
        buffer_code = None
        buffer_parent = None
        buffer_page_start = None
        buffer_page_end = None

    def start_unit(page: int, kind: str, code: str, parent: str | None, body: str) -> None:
        nonlocal buffer, buffer_page_start, buffer_page_end
        nonlocal buffer_kind, buffer_code, buffer_parent
        flush()
        buffer_kind = kind
        buffer_code = code
        buffer_parent = parent
        buffer_page_start = page
        buffer_page_end = page
        buffer = [body]

    for page, line in lines:
        if skip_toc_section_line(line):
            continue

        sec = is_section(line)
        if sec:
            flush()
            current_section_code = sec.group("code")
            current_section_title = sec.group("title").strip()
            current_section_title = re.sub(r"\s+\d+\s*$", "", current_section_title).strip()
            current_item_code = None
            start_unit(
                page,
                "section",
                current_section_code,
                None,
                f"{current_section_code}. {current_section_title}",
            )
            continue

        item_match = ITEM_RE.match(line)
        if item_match:
            code = item_match.group("code")
            body = item_match.group("body").strip()
            if re.search(r"\.{4,}", body):
                continue
            parent = ".".join(code.split(".")[:-1]) if "." in code else current_section_code
            current_item_code = code
            inline = INLINE_ALINEA_RE.match(body)
            if inline:
                start_unit(page, "item", code, parent, inline.group("head").strip())
                letter = inline.group("letter")
                start_unit(
                    page,
                    "alinea",
                    f"{code}.{letter}",
                    code,
                    inline.group("body").strip(),
                )
            else:
                start_unit(page, "item", code, parent, body)
            continue

        alinea_match = ALINEA_RE.match(line)
        if alinea_match and current_item_code:
            letter = alinea_match.group("letter")
            body = alinea_match.group("body").strip()
            code = f"{current_item_code}.{letter}"
            start_unit(page, "alinea", code, current_item_code, body)
            continue

        bullet_match = BULLET_RE.match(line)
        if bullet_match and current_item_code:
            body = bullet_match.group("body").strip()
            n = sum(
                1
                for it in items
                if it.parent_code == current_item_code and it.kind == "bullet"
            ) + (1 if buffer_kind == "bullet" and buffer_parent == current_item_code else 0)
            code = f"{current_item_code}.bullet{n + 1}"
            start_unit(page, "bullet", code, current_item_code, body)
            continue

        if buffer_kind and buffer:
            if re.match(r"^(Quadro|Tabela|Figura)\s+\d+", line):
                flush()
                continue
            buffer.append(line)
            buffer_page_end = page
            continue

    flush()
    items = split_inline_alineas(items)

    # Deduplicate by code keeping richest statement
    dedup: dict[str, ExtractedItem] = {}
    for item in items:
        prev = dedup.get(item.code)
        if not prev or len(item.statement) > len(prev.statement):
            dedup[item.code] = item
    items = list(dedup.values())
    # stable-ish order by page then code
    items.sort(key=lambda i: (i.page_start, i.code))

    kind_counts = Counter(i.kind for i in items)
    type_counts = Counter(i.criterion_type for i in items)
    section_counts = Counter(
        f"{i.section_code}. {i.section_title}" for i in items if i.section_code
    )

    checklist_candidates = [
        i
        for i in items
        if i.kind in {"item", "alinea", "bullet"}
        and i.criterion_type
        in {
            "avaliativo_comum",
            "avaliativo_objeto",
            "avaliativo_componente",
            "caracteristica_obra",
            "objeto_digital",
            "resultado_aprovacao",
        }
    ]

    return {
        "edital_id": edital_id,
        "version": version,
        "doc_type": "anexo_01_referencial_pedagogico",
        "source_path": str(path),
        "page_count": len(pages),
        "stats": {
            "total_units": len(items),
            "by_kind": dict(kind_counts),
            "by_criterion_type": dict(type_counts),
            "checklist_candidate_count": len(checklist_candidates),
            "sections_with_items": len(section_counts),
        },
        "sections": [
            {"code": code, "title": title, "unit_count": count}
            for (label, count) in section_counts.most_common()
            for code, title in [label.split(". ", 1) if ". " in label else (label, "")]
        ],
        "items": [
            {
                **asdict(i),
                "edital_id": edital_id,
                "version": version,
                "doc_type": "anexo_01_referencial_pedagogico",
                "status": "pending_review",
                "confidence": 0.55 if i.kind == "alinea" else 0.5,
            }
            for i in items
        ],
        "checklist_preview": [
            {
                "code": i.code,
                "parent_code": i.parent_code,
                "criterion_type": i.criterion_type,
                "statement": i.statement[:180],
                "page": i.page_start,
            }
            for i in checklist_candidates[:40]
        ],
    }


def write_outputs(result: dict, out_dir: Path, stem: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    # Lightweight review CSV-like TSV for HITL sampling
    tsv_path = out_dir / f"{stem}.tsv"
    lines = [
        "code\tparent_code\tkind\tcriterion_type\tpage_start\tmandatory_guess\tstatement"
    ]
    for item in result["items"]:
        if item["kind"] == "section":
            continue
        stmt = item["statement"].replace("\t", " ").replace("\n", " ")
        lines.append(
            f"{item['code']}\t{item['parent_code'] or ''}\t{item['kind']}\t"
            f"{item['criterion_type']}\t{item['page_start']}\t{item['mandatory_guess']}\t{stmt}"
        )
    tsv_path.write_text("\n".join(lines) + "\n")
    return json_path, tsv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/Users/ranilsonpaiva/Downloads/pnld-corpus/analysis/extractions"),
    )
    args = parser.parse_args()

    jobs = [
        {
            "path": Path(
                "/Users/ranilsonpaiva/Downloads/pnld-corpus/anos-iniciais-2027/anexo-01-5a-retificacao.pdf"
            ),
            "edital_id": "pnld-anos-iniciais-2027-2030",
            "version": "anexo-01-5a-retificacao",
            "stem": "anos-iniciais-anexo01",
        },
        {
            "path": Path(
                "/Users/ranilsonpaiva/Downloads/pnld-corpus/anos-finais-2028/anexo-01-1a-retificacao.pdf"
            ),
            "edital_id": "pnld-anos-finais-2028-2031",
            "version": "anexo-01-1a-retificacao",
            "stem": "anos-finais-anexo01",
        },
    ]

    summary = []
    for job in jobs:
        result = extract(job["path"], job["edital_id"], job["version"])
        json_path, tsv_path = write_outputs(result, args.out, job["stem"])
        summary.append(
            {
                "stem": job["stem"],
                "stats": result["stats"],
                "json": str(json_path),
                "tsv": str(tsv_path),
                "sample_codes": [i["code"] for i in result["items"][:15]],
            }
        )
        print(f"\n=== {job['stem']} ===")
        print(json.dumps(result["stats"], ensure_ascii=False, indent=2))
        print("sections:", len(result["sections"]))
        print("wrote:", json_path)
        print("sample checklist:")
        for row in result["checklist_preview"][:8]:
            print(f"  {row['code']}: {row['statement'][:100]}")

    summary_path = args.out / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nsummary:", summary_path)


if __name__ == "__main__":
    main()
