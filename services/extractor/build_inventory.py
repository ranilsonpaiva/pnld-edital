from pathlib import Path
from pypdf import PdfReader
import re
import json
from collections import Counter

CORPUS = Path("/Users/ranilsonpaiva/Downloads/pnld-corpus")

DOCS = {
    "anos-iniciais/edital-5a": CORPUS
    / "anos-iniciais-2027/edital-5a-retificacao.pdf",
    "anos-iniciais/anexo-01-5a": CORPUS
    / "anos-iniciais-2027/anexo-01-5a-retificacao.pdf",
    "anos-iniciais/anexo-04": CORPUS / "anos-iniciais-2027/anexo-04-validacao.pdf",
    "anos-finais/edital-1a": CORPUS / "anos-finais-2028/edital-1a-retificacao.pdf",
    "anos-finais/anexo-01-1a": CORPUS
    / "anos-finais-2028/anexo-01-1a-retificacao.pdf",
    "anos-finais/anexo-04": CORPUS / "anos-finais-2028/anexo-04-validacao.pdf",
}


def full_text(path: Path) -> tuple[str, int]:
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return text, len(reader.pages)


def extract_headings_from_body(full: str) -> list[dict]:
    headings: list[dict] = []
    patterns = [
        r"(?m)^(\d+)\.\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{5,120})$",
        r"(?m)^(\d+)\s*[-–—]\s+([^\n]{5,120})$",
        r"(?m)^(ANEXO\s+\d+[^\n]{0,80})$",
    ]
    for pat in patterns:
        for match in re.finditer(pat, full):
            if match.lastindex == 2:
                headings.append(
                    {"code": match.group(1), "title": match.group(2).strip()}
                )
            else:
                headings.append({"code": None, "title": match.group(1).strip()})
    out: list[dict] = []
    seen: set = set()
    for heading in headings:
        key = (heading["code"], heading["title"][:60].lower())
        if key not in seen:
            seen.add(key)
            out.append(heading)
    return out


def extract_criteria_blocks(full: str, doc_role: str) -> list[dict]:
    items: list[dict] = []
    pattern = (
        r"(?m)^(\d+\.\d+(?:\.\d+){0,3})\s+(.{20,350}?)"
        r"(?=\n\d+\.\d+|\n\d+\s+[A-Z]|\nANEXO|\Z)"
    )
    for match in re.finditer(pattern, full, re.S):
        code = match.group(1)
        text = re.sub(r"\s+", " ", match.group(2)).strip()
        low = text.lower()
        kind = "normativo"
        if any(token in low for token in ["critério", "critérios", "avaliativ"]):
            kind = "criterio_avaliativo"
        elif any(
            token in low
            for token in [
                "deverá",
                "devem",
                "obrigat",
                "é vedado",
                "não serão aceit",
                "imped",
            ]
        ):
            kind = "obrigacao"
        elif any(token in low for token in ["prazo", "até às", "período"]):
            kind = "prazo"
        elif any(
            token in low for token in ["documento", "comprov", "certid", "declara"]
        ):
            kind = "documental"
        elif any(token in low for token in ["habilita", "inscrit", "cadastr"]):
            kind = "processual"
        items.append(
            {
                "code": code,
                "kind_guess": kind,
                "text": text[:280],
                "doc_role": doc_role,
            }
        )
    return items


def count_lettered(full: str) -> int:
    return len(re.findall(r"(?m)^\s*[a-z]\)\s+\S.{10,}", full))


def toc_like_lines(full: str) -> list[str]:
    lines: list[str] = []
    for raw in full.splitlines()[:160]:
        line = raw.strip()
        if re.match(r"^(\d+)\.\s+\S", line) or re.match(
            r"(?i)^(pre[aâ]mbulo|anexo)", line
        ):
            clean = re.sub(r"\s*\.{2,}\s*\d*\s*$", "", line)
            clean = re.sub(r"\s+\d+\s*$", "", clean)
            if 8 < len(clean) < 140:
                lines.append(clean)
    return lines[:30]


def main() -> None:
    inventory: dict = {"editals": {}, "schema_proposal": {}}

    for key, path in DOCS.items():
        full, pages = full_text(path)
        role = (
            "edital"
            if "edital" in key
            else ("anexo01" if "anexo-01" in key else "anexo04")
        )
        items = extract_criteria_blocks(full, role)
        kinds = Counter(item["kind_guess"] for item in items)
        inventory["editals"][key] = {
            "path": str(path),
            "pages": pages,
            "chars": len(full),
            "role": role,
            "major_headings": extract_headings_from_body(full)[:40],
            "toc_like": toc_like_lines(full),
            "item_count": len(items),
            "lettered_lines": count_lettered(full),
            "kind_counts": dict(kinds),
            "sample_by_kind": {
                kind: [item for item in items if item["kind_guess"] == kind][:3]
                for kind in kinds
            },
        }
        print(
            key,
            pages,
            "items",
            len(items),
            "kinds",
            dict(kinds),
            "letters",
            count_lettered(full),
        )

    inventory["schema_proposal"] = {
        "document_types": [
            "edital_convocacao",
            "anexo_01_referencial_pedagogico",
            "anexo_02_estrutura_editorial",
            "anexo_03_especificacoes_digitais",
            "anexo_04_manual_validacao",
            "anexo_05_glossario",
            "retificacao_dou",
            "portaria_resultado",
        ],
        "criterion_types": [
            {
                "id": "avaliativo_comum",
                "desc": "Critérios comuns às obras (Anexo 01)",
            },
            {
                "id": "avaliativo_objeto",
                "desc": "Critérios por objeto/categoria de obra",
            },
            {
                "id": "avaliativo_componente",
                "desc": "Critérios específicos por componente curricular",
            },
            {
                "id": "caracteristica_obra",
                "desc": "Características estruturais da obra",
            },
            {
                "id": "objeto_digital",
                "desc": "Requisitos de PDF interativo / objetos digitais",
            },
            {
                "id": "processual_inscricao",
                "desc": "Regras de inscrição/cadastro na plataforma",
            },
            {
                "id": "documental_habilitacao",
                "desc": "Documentos e habilitação do detentor",
            },
            {
                "id": "validacao_tecnica",
                "desc": "Checagens do Anexo 04 (atributos, acessibilidade)",
            },
            {"id": "prazo", "desc": "Prazos e cronograma"},
            {
                "id": "resultado_aprovacao",
                "desc": "Aprovação, aprovação condicionada, reprovação",
            },
        ],
        "item_schema_fields": [
            "id",
            "edital_id",
            "version",
            "doc_type",
            "section_path",
            "code",
            "parent_code",
            "title",
            "statement",
            "criterion_type",
            "mandatory",
            "applies_to",
            "component",
            "category",
            "object",
            "evidence_hint",
            "outcome_on_fail",
            "source_span",
            "confidence",
            "status",
        ],
        "applies_to_enum": [
            "obra",
            "colecao",
            "detentor",
            "inscricao",
            "pdf_interativo",
            "livro_professor",
            "livro_estudante",
        ],
        "checklist_derivation": (
            "Only approved items with criterion_type in avaliativo_*|"
            "validacao_tecnica|documental_habilitacao|processual_inscricao|prazo "
            "become checklist rows; características may be informational."
        ),
    }

    print("\n=== ANEXO 01 ANOS INICIAIS TOC-LIKE ===")
    for line in inventory["editals"]["anos-iniciais/anexo-01-5a"]["toc_like"]:
        print(" ", line)
    print("\n=== ANEXO 01 ANOS FINAIS TOC-LIKE ===")
    for line in inventory["editals"]["anos-finais/anexo-01-1a"]["toc_like"]:
        print(" ", line)
    print("\n=== EDITAL AI HEADINGS ===")
    for heading in inventory["editals"]["anos-iniciais/edital-5a"]["major_headings"][
        :25
    ]:
        print(" ", heading)
    print("\n=== EDITAL AF HEADINGS ===")
    for heading in inventory["editals"]["anos-finais/edital-1a"]["major_headings"][
        :25
    ]:
        print(" ", heading)

    out = CORPUS / "analysis" / "inventory.json"
    out.write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
    print("\nWrote", out)


if __name__ == "__main__":
    main()
