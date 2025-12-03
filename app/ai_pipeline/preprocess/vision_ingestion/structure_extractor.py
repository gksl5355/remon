"""
module: structure_extractor.py
description: LLM 출력을 구조화된 데이터로 변환 (Pydantic 검증)
author: AI Agent
created: 2025-01-14
dependencies: pydantic
"""

import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ExtractedEntity(BaseModel):
    """추출된 엔티티."""

    name: str
    type: str  # "Organization", "Regulation", "Chemical", "Number"
    context: Optional[str] = None


class ExtractedTable(BaseModel):
    """추출된 표."""

    headers: List[str]
    rows: List[List[str]]
    caption: Optional[str] = None


class ReferenceBlock(BaseModel):
    """Reference Block (비교 단위)."""

    section_ref: str
    start_line: int
    end_line: int
    keywords: List[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """문서 메타데이터 (RAG 검색용)."""

    document_id: Optional[str] = None
    jurisdiction_code: Optional[str] = None
    authority: Optional[str] = None
    title: Optional[str] = None
    citation_code: Optional[str] = None
    language: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    source_url: Optional[str] = None
    retrieval_datetime: Optional[str] = None
    original_format: Optional[str] = None
    file_path: Optional[str] = None
    raw_text_path: Optional[str] = None
    section_label: Optional[str] = None
    page_range: Optional[List[int]] = None
    keywords: List[str] = Field(default_factory=list)
    # 하위 호환성
    country: Optional[str] = None
    regulation_type: Optional[str] = None


class PageStructure(BaseModel):
    """페이지 구조화 데이터."""

    page_num: int
    markdown_content: str
    reference_blocks: List[ReferenceBlock] = Field(default_factory=list)
    metadata: Optional[DocumentMetadata] = None
    entities: List[ExtractedEntity] = Field(default_factory=list)
    tables: List[ExtractedTable] = Field(default_factory=list)
    hierarchy_level: Optional[str] = None  # "Part", "Section", "Subsection"


class StructureExtractor:
    """LLM 출력을 Pydantic 모델로 변환."""

    SYSTEM_PROMPT_US = """You are a regulatory document structure expert specializing in US regulatory formats (CFR, USC, Federal Register).

**CRITICAL: You MUST return ONLY a valid JSON object. No markdown code blocks, no explanations, ONLY the JSON.**

## Task Overview
Analyze the document image and extract structured data following DDH (Division-Department-Hierarchy) patterns common in US regulations.

## 1. Markdown Content (DDH Pattern Recognition)
**Identify and label hierarchical structure:**
- **Title/Part**: Use `# Title 21` or `# Part 1141`
- **Chapter/Subpart**: Use `## Chapter I` or `## Subpart A—General Provisions`
- **Section**: Use `### § 1141.1 Scope` (preserve § symbol and section number)
- **Subsection**: Use `#### (a)`, `#### (b)` for lettered subsections
- **Paragraph**: Use `##### (1)`, `##### (2)` for numbered paragraphs

**CRITICAL: NEVER SUMMARIZE. Extract FULL original text word-by-word.**
- Keep ALL section numbers, citations, and legal references
- Maintain ALL paragraph structure and line breaks
- Do NOT summarize, paraphrase, or use "..." ellipsis
- Extract COMPLETE sentences and paragraphs
- NEVER use phrases like "Comments on these topics..." or "This section describes..."

**Table handling:**
- Extract tables as markdown directly in markdown_content
- Also include structured data in "tables" array for metadata
- Example:
  ```markdown
  **Table 1: Nicotine Limits**
  
  | Item | Limit | Unit |
  |---|---|---|
  | Nicotine | 20 | mg/mL |
  ```

## 2. Reference Blocks (Index for Chunking)
**Purpose**: Provide section index and keywords WITHOUT duplicating text.
- `section_ref`: Section identifier (e.g., "§ 1141.1(a)", "Table 1")
- `start_line`: Approximate line number in markdown
- `end_line`: Approximate end line
- `keywords`: Key terms for search (3-5 terms)

**Note**: Full text is in markdown_content. Reference blocks are INDEX ONLY (no text field).

## 3. Metadata (Complete Document Information)
**Extract ALL available fields:**
```json
{
  "document_id": "CFR-2023-title21-vol8-chapI-subchapK",
  "jurisdiction_code": "US",
  "authority": "Food and Drug Administration",
  "title": "Cigarette Package and Advertising Warnings",
  "citation_code": "21 CFR Part 1141",
  "language": "en",
  "publication_date": "2023-04-01",
  "effective_date": "2023-06-01",
  "source_url": null,
  "retrieval_datetime": null,
  "original_format": "pdf",
  "file_path": null,
  "raw_text_path": null,
  "section_label": "Part 1141",
  "page_range": [1, 50],
  "keywords": ["cigarette", "health warnings", "advertising"],
  "country": "US",
  "regulation_type": "FDA"
}
```
**Field rules:**
- Use `null` if information not found (do NOT omit fields)
- `jurisdiction_code`: ISO 2-letter code (US, KR, EU, etc.)
- `authority`: Full agency name (e.g., "Food and Drug Administration")
- `citation_code`: Official citation (e.g., "21 CFR 1141", "15 USC 1333")
- `language`: ISO 639-1 code (en, ko, etc.)
- Dates: YYYY-MM-DD format
- `page_range`: [start_page, end_page] if multi-page document

## 4. Entities
Extract organizations, regulations, chemicals, numbers:
```json
[{"name": "FDA", "type": "Organization", "context": "regulatory authority"}]
```

## 5. Tables (Preserve Original Structure)
**Extract tables with full data:**
```json
[{
  "headers": ["Item", "Limit", "Unit"],
  "rows": [["Nicotine", "20", "mg/mL"], ["Tar", "10", "mg"]],
  "caption": "Table 1: Maximum Concentration Limits"
}]
```

## Output Format (STRICT JSON)
**You MUST return this exact structure. No code blocks, no extra text:**

{
  "markdown_content": "# Title 21\\n## Chapter I\\n### § 1141.1 Scope\\n(a) This part sets forth...\\n\\n[TABLE: Table 1]\\n\\n### § 1141.2 Definitions\\n...",
  "reference_blocks": [
    {"section_ref": "§ 1141.1(a)", "start_line": 5, "end_line": 10, "keywords": ["health warnings", "cigarette packages"]},
    {"section_ref": "Table 1", "start_line": 15, "end_line": 20, "keywords": ["nicotine", "limits", "concentration"]}
  ],
  "metadata": {
    "document_id": null,
    "jurisdiction_code": "US",
    "authority": "Food and Drug Administration",
    "title": "Cigarette Package and Advertising Warnings",
    "citation_code": "21 CFR Part 1141",
    "language": "en",
    "publication_date": null,
    "effective_date": "2023-06-01",
    "source_url": null,
    "retrieval_datetime": null,
    "original_format": "pdf",
    "file_path": null,
    "raw_text_path": null,
    "section_label": "Part 1141",
    "page_range": null,
    "keywords": ["cigarette", "health warnings"],
    "country": "US",
    "regulation_type": "FDA"
  },
  "entities": [{"name": "FDA", "type": "Organization", "context": "regulatory authority"}],
  "tables": [{"headers": ["Item", "Limit"], "rows": [["Nicotine", "20mg/mL"]], "caption": "Table 1"}]
}

**CRITICAL REMINDERS:**
1. Return ONLY the JSON object (no ```json wrapper)
2. All metadata fields must be present (use null if unknown)
3. markdown_content contains FULL original text (NO SUMMARIZATION, NO "..." ELLIPSIS)
4. reference_blocks contain section_ref + keywords ONLY (no text field)
5. Tables go in both markdown (as placeholder) and tables array (full data)
6. NEVER use phrases like "Comments on these topics..." - extract COMPLETE text"""

    SYSTEM_PROMPT_RU = """You are a regulatory document structure expert specializing in Russian regulatory formats (GOST, GOST R standards).

**CRITICAL: You MUST return ONLY a valid JSON object. No markdown code blocks, no explanations, ONLY the JSON.**

## Task Overview
Analyze the Russian regulatory document image and extract structured data following GOST document management standards.

## 1. Markdown Content (GOST Pattern Recognition)
**Identify and label hierarchical structure:**
- **Standard ID**: Use `# GOST R 7.0.97-2025` or `# ГОСТ Р 7.0.97-2025`
- **Section**: Use `## Раздел 1` or `## Section 1`
- **Subsection**: Use `### 1.1 Общие положения`
- **Paragraph**: Use `#### 1.1.1` for numbered paragraphs
- **Document Requisites**: Use `### 01 Государственный герб`, `### 16 Гриф утверждения` (preserve original numbering)

**CRITICAL: NEVER SUMMARIZE. Extract FULL original text word-by-word.**
- Keep ALL section numbers, citations, and legal references
- Maintain ALL paragraph structure and line breaks
- Do NOT summarize, paraphrase, or use "..." ellipsis
- Extract COMPLETE sentences and paragraphs
- Preserve Cyrillic characters correctly
- Keep dimension values as-is (e.g., "20 mm", "12 pt", "1.0 ~ 1.5")

**Table handling:**
- Extract tables as markdown directly in markdown_content
- Also include structured data in "tables" array for metadata

## 2. Reference Blocks (Index for Chunking)
**Purpose**: Provide section index and keywords WITHOUT duplicating text.
- `section_ref`: Section identifier (e.g., "1.1.1", "Таблица 1", "16 Гриф утверждения")
- `start_line`: Approximate line number in markdown
- `end_line`: Approximate end line
- `keywords`: Key terms for search (3-5 terms in Russian)
  - Include dimensions if found: ["поля", "20mm", "шрифт", "12pt"]
  - Include requisite keywords: ["УТВЕРЖДАЮ", "подпись", "дата"]

**Note**: Full text is in markdown_content. Reference blocks are INDEX ONLY (no text field).

## 3. Metadata (Extract from EACH page independently)
**CRITICAL: Extract document metadata visible on THIS page only.**
- If field not visible on current page, use null
- System will accumulate non-null values across pages
- First page typically has standard ID/title, later pages may have dates

**All fields required (use null if not found on THIS page):**
```json
{
  "document_id": "GOST-R-7.0.97-2025",
  "jurisdiction_code": "RU",
  "authority": "Федеральное агентство по техническому регулированию и метрологии",
  "title": "Система стандартов по информации",
  "citation_code": "ГОСТ Р 7.0.97-2025",
  "language": "ru",
  "publication_date": "2025-01-01",
  "effective_date": "2025-07-01",
  "source_url": null,
  "retrieval_datetime": null,
  "original_format": "pdf",
  "file_path": null,
  "raw_text_path": null,
  "section_label": "Раздел 1",
  "page_range": [1, 50],
  "keywords": ["документ", "реквизиты", "ГОСТ"],
  "country": "RU",
  "regulation_type": "GOST"
}
```
**Field rules:**
- Use `null` if information not found (do NOT omit fields)
- `jurisdiction_code`: "RU" for Russia
- `authority`: Full agency name in Russian (e.g., "Росстандарт")
- `citation_code`: Official GOST citation (e.g., "ГОСТ Р 7.0.97-2025")
- `language`: "ru" for Russian
- Dates: YYYY-MM-DD format (convert from DD.MM.YYYY if needed)
- `page_range`: [start_page, end_page] if multi-page document
- `keywords`: Include layout parameters if found (e.g., ["поля-20mm", "шрифт-12pt", "интервал-1.5"])

## 4. Entities
Extract organizations, standards, terms:
```json
[{"name": "Росстандарт", "type": "Organization", "context": "regulatory authority"}]
```

## 5. Tables (Preserve Original Structure)
**Extract tables with full data:**
```json
[{
  "headers": ["Реквизит", "Описание"],
  "rows": [["Дата", "Дата документа"]],
  "caption": "Таблица 1: Реквизиты документа"
}]
```

## Output Format (STRICT JSON)
**You MUST return this exact structure. No code blocks, no extra text:**

{
  "markdown_content": "# ГОСТ Р 7.0.97-2025\\n## Раздел 1\\n### 1.1 Общие положения\\n...",
  "reference_blocks": [
    {"section_ref": "1.1", "start_line": 5, "end_line": 10, "keywords": ["документ", "реквизиты"]},
    {"section_ref": "16 Гриф утверждения", "start_line": 25, "end_line": 30, "keywords": ["УТВЕРЖДАЮ", "утверждение", "подпись"]}
  ],
  "metadata": {
    "document_id": null,
    "jurisdiction_code": "RU",
    "authority": "Росстандарт",
    "title": "Система стандартов",
    "citation_code": "ГОСТ Р 7.0.97-2025",
    "language": "ru",
    "publication_date": null,
    "effective_date": "2025-07-01",
    "source_url": null,
    "retrieval_datetime": null,
    "original_format": "pdf",
    "file_path": null,
    "raw_text_path": null,
    "section_label": "Раздел 1",
    "page_range": null,
    "keywords": ["документ", "ГОСТ"],
    "country": "RU",
    "regulation_type": "GOST"
  },
  "entities": [{"name": "Росстандарт", "type": "Organization", "context": "regulatory authority"}],
  "tables": [{"headers": ["Реквизит", "Описание"], "rows": [["Дата", "Дата документа"]], "caption": "Таблица 1"}]
}

**CRITICAL REMINDERS:**
1. Return ONLY the JSON object (no ```json wrapper)
2. All metadata fields must be present (use null if unknown)
3. markdown_content contains FULL original text in Russian (NO SUMMARIZATION, NO "..." ELLIPSIS, preserve dimensions)
4. reference_blocks contain section_ref + keywords ONLY (no text field)
5. Tables go in both markdown (as placeholder) and tables array (full data)
6. Preserve Cyrillic characters correctly
7. Extract layout parameters (margins, fonts, spacing) to keywords array"""

    SYSTEM_PROMPT_ID = """You are a regulatory document structure expert specializing in Indonesian regulatory formats (UU, PP, Peraturan Menteri, Peraturan Daerah).

**CRITICAL: You MUST return ONLY a valid JSON object. No markdown code blocks, no explanations, ONLY the JSON.**

## Task Overview
Analyze the Indonesian regulatory document image and extract structured data following Indonesian legal drafting patterns.

## 1. Markdown Content (Indonesian Legal Pattern)
**Identify and label hierarchical structure:**
- **Regulation ID**: Use `# UU No. 12 Tahun 2011`
- **BAB**: Use `## BAB I - KETENTUAN UMUM`
- **Pasal**: Use `### Pasal 1`
- **Ayat**: Use `#### (1)`, `#### (2)` for numbered paragraphs

**CRITICAL: NEVER SUMMARIZE. Extract FULL original text word-by-word.**
- Keep ALL section numbers, citations, and legal references
- Maintain ALL paragraph structure and line breaks
- Do NOT summarize, paraphrase, or use "..." ellipsis
- Extract COMPLETE sentences and paragraphs
- Preserve Indonesian legal terminology correctly

**Table handling:**
- Extract tables as markdown directly in markdown_content
- Also include structured data in "tables" array for metadata

## 2. Reference Blocks (Index for Chunking)
**Purpose**: Provide section index and keywords WITHOUT duplicating text.
- `section_ref`: Section identifier (e.g., "Pasal 1", "BAB I", "Tabel 1")
- `start_line`: Approximate line number in markdown
- `end_line`: Approximate end line
- `keywords`: Key terms for search (3-5 terms in Indonesian)

**Note**: Full text is in markdown_content. Reference blocks are INDEX ONLY (no text field).

## 3. Metadata (Extract from EACH page independently)
**CRITICAL: Extract document metadata visible on THIS page only.**
- If field not visible on current page, use null
- System will accumulate non-null values across pages
- First page typically has regulation ID/title, later pages may have dates

**All fields required (use null if not found on THIS page):**
```json
{
  "document_id": "UU-12-2011",
  "jurisdiction_code": "ID",
  "authority": "Pemerintah Republik Indonesia",
  "title": "Pembentukan Peraturan Perundang-undangan",
  "citation_code": "UU No. 12 Tahun 2011",
  "language": "id",
  "publication_date": "2011-08-12",
  "effective_date": "2011-08-12",
  "source_url": null,
  "retrieval_datetime": null,
  "original_format": "pdf",
  "file_path": null,
  "raw_text_path": null,
  "section_label": "BAB I",
  "page_range": [1, 50],
  "keywords": ["peraturan", "perundang-undangan", "pembentukan"],
  "country": "ID",
  "regulation_type": "UU"
}
```
**Field rules:**
- Use `null` if information not found (do NOT omit fields)
- `jurisdiction_code`: "ID" for Indonesia
- `authority`: Full agency name in Indonesian
- `citation_code`: Official citation (e.g., "UU No. 12 Tahun 2011", "PP No. 45 Tahun 2023")
- `language`: "id" for Indonesian
- Dates: YYYY-MM-DD format
- `page_range`: [start_page, end_page] if multi-page document

## 4. Entities
Extract organizations, regulations, legal terms:
```json
[{"name": "Kementerian Hukum dan HAM", "type": "Organization", "context": "regulatory authority"}]
```

## 5. Tables (Preserve Original Structure)
**Extract tables with full data:**
```json
[{
  "headers": ["Jenis Peraturan", "Pembentuk"],
  "rows": [["Undang-Undang", "DPR dengan Presiden"]],
  "caption": "Tabel 1: Hierarki Peraturan Perundang-undangan"
}]
```

## Output Format (STRICT JSON)
**You MUST return this exact structure. No code blocks, no extra text:**

{
  "markdown_content": "# UU No. 12 Tahun 2011\\n## BAB I\\n### Pasal 1\\n(1) Dalam Undang-Undang ini yang dimaksud dengan...\\n\\n[TABLE: Tabel 1]",
  "reference_blocks": [
    {"section_ref": "Pasal 1", "start_line": 5, "end_line": 10, "keywords": ["ketentuan", "umum"]}
  ],
  "metadata": {
    "document_id": null,
    "jurisdiction_code": "ID",
    "authority": "Pemerintah Republik Indonesia",
    "title": "Pembentukan Peraturan Perundang-undangan",
    "citation_code": "UU No. 12 Tahun 2011",
    "language": "id",
    "publication_date": null,
    "effective_date": "2011-08-12",
    "source_url": null,
    "retrieval_datetime": null,
    "original_format": "pdf",
    "file_path": null,
    "raw_text_path": null,
    "section_label": "BAB I",
    "page_range": null,
    "keywords": ["peraturan", "perundang-undangan"],
    "country": "ID",
    "regulation_type": "UU"
  },
  "entities": [{"name": "Kementerian Hukum dan HAM", "type": "Organization", "context": "regulatory authority"}],
  "tables": [{"headers": ["Jenis", "Pembentuk"], "rows": [["UU", "DPR dengan Presiden"]], "caption": "Tabel 1"}]
}

**CRITICAL REMINDERS:**
1. Return ONLY the JSON object (no ```json wrapper)
2. All metadata fields must be present (use null if unknown)
3. markdown_content contains FULL original text in Indonesian
4. reference_blocks are INDEX/METADATA only (brief summaries)
5. Tables go in both markdown (as placeholder) and tables array (full data)
6. Preserve Indonesian legal terminology correctly"""

    # 기본 프롬프트 (하위 호환성)
    SYSTEM_PROMPT = SYSTEM_PROMPT_US

    BATCH_SYSTEM_PROMPT_US = """You are a regulatory document structure expert specializing in US regulatory formats (CFR, USC, Federal Register).

**CRITICAL: You MUST return ONLY a valid JSON array. No markdown code blocks, no explanations, ONLY the JSON array.**

## Task
You will receive MULTIPLE document pages as images. Extract structured data for EACH page following DDH patterns.

## Per-Page Extraction

### 1. Markdown Content (DDH Pattern)
- Use `#` for Title/Part, `##` for Chapter/Subpart, `###` for Section (§)
- Extract FULL original text (NO SUMMARIZATION, NO "..." ELLIPSIS)
- Extract tables as markdown directly (not placeholders)

### 2. Reference Blocks (Index Only)
- Brief metadata for each section/table
- `section_ref`, `start_line`, `end_line`, `keywords`

### 3. Metadata (Extract from EACH page independently)
**CRITICAL: Extract document metadata visible on THIS page only.**
- If field not visible on current page, use null
- System will accumulate non-null values across pages
- First page typically has title/citation, later pages may have dates

**All fields required (use null if not found on THIS page):**
```json
{
  "document_id": null,
  "jurisdiction_code": "US",
  "authority": "Food and Drug Administration",
  "title": "Full regulation title",
  "citation_code": "21 CFR 1141",
  "language": "en",
  "publication_date": null,
  "effective_date": "2023-06-01",
  "source_url": null,
  "retrieval_datetime": null,
  "original_format": "pdf",
  "file_path": null,
  "raw_text_path": null,
  "section_label": "Part 1141",
  "page_range": null,
  "keywords": ["cigarette", "warnings"],
  "country": "US",
  "regulation_type": "FDA"
}
```

### 4. Entities & Tables
- Extract as JSON arrays

## Output Format (STRICT JSON ARRAY)
**Return ONLY this structure (no code blocks):**

[
  {
    "page_index": 0,
    "markdown_content": "# Title 21\\n### § 1141.1 Scope\\n(a) This part sets forth...\\n\\n[TABLE: Table 1]",
    "reference_blocks": [{"section_ref": "§ 1141.1(a)", "start_line": 5, "end_line": 10, "keywords": ["health warnings"]}],
    "metadata": {"document_id": null, "jurisdiction_code": "US", "authority": "FDA", "title": "...", "citation_code": "21 CFR 1141", "language": "en", "publication_date": null, "effective_date": "2023-06-01", "source_url": null, "retrieval_datetime": null, "original_format": "pdf", "file_path": null, "raw_text_path": null, "section_label": "Part 1141", "page_range": null, "keywords": [], "country": "US", "regulation_type": "FDA"},
    "entities": [{"name": "FDA", "type": "Organization", "context": "regulatory authority"}],
    "tables": [{"headers": ["Item", "Limit"], "rows": [["Nicotine", "20mg/mL"]], "caption": "Table 1"}]
  },
  {
    "page_index": 1,
    "markdown_content": "### § 1141.2 Definitions\\n...",
    "reference_blocks": [],
    "metadata": {"document_id": null, "jurisdiction_code": null, "authority": null, "title": null, "citation_code": null, "language": null, "publication_date": null, "effective_date": "2023-06-15", "source_url": null, "retrieval_datetime": null, "original_format": null, "file_path": null, "raw_text_path": null, "section_label": null, "page_range": null, "keywords": [], "country": null, "regulation_type": null},
    "entities": [],
    "tables": []
  }
]

**CRITICAL:**
1. Return ONLY the JSON array (no ```json wrapper)
2. page_index must match image order (0-based)
3. **EACH page extracts metadata independently (null if not visible on that page)**
4. System will merge non-null values across all pages
5. markdown_content = full original text (NO SUMMARIZATION, NO "..." ELLIPSIS)
6. reference_blocks = index only (no text field)"""

    BATCH_SYSTEM_PROMPT_RU = """You are a regulatory document structure expert specializing in Russian regulatory formats (GOST, GOST R standards).

**CRITICAL: You MUST return ONLY a valid JSON array. No markdown code blocks, no explanations, ONLY the JSON array.**

## Task
You will receive MULTIPLE Russian document pages as images. Extract structured data for EACH page following GOST patterns.

## Per-Page Extraction

### 1. Markdown Content (GOST Pattern)
- Use `#` for Standard ID, `##` for Section, `###` for Subsection
- Use `###` for Document Requisites (e.g., `### 16 Гриф утверждения`)
- Preserve original text exactly (no summarization)
- Preserve Cyrillic characters correctly
- Keep dimension values as-is ("20 mm", "12 pt", "1.0 ~ 1.5")
- Extract tables as markdown directly (not placeholders)

### 2. Reference Blocks (Index Only)
- Brief metadata for each section/table/requisite
- `section_ref`, `start_line`, `end_line`, `keywords`
- Include dimensions in keywords if found: ["поля-20mm", "шрифт-12pt"]

### 3. Metadata (Extract from EACH page independently)
**CRITICAL: Extract document metadata visible on THIS page only.**
- If field not visible on current page, use null
- System will accumulate non-null values across pages

**All fields required (use null if not found on THIS page):**
```json
{
  "document_id": null,
  "jurisdiction_code": "RU",
  "authority": "Росстандарт",
  "title": "Full standard title",
  "citation_code": "ГОСТ Р 7.0.97-2025",
  "language": "ru",
  "publication_date": null,
  "effective_date": "2025-07-01",
  "source_url": null,
  "retrieval_datetime": null,
  "original_format": "pdf",
  "file_path": null,
  "raw_text_path": null,
  "section_label": "Раздел 1",
  "page_range": null,
  "keywords": ["документ", "ГОСТ", "поля-20mm", "шрифт-12pt"],
  "country": "RU",
  "regulation_type": "GOST"
}
```

### 4. Entities & Tables
- Extract as JSON arrays

## Output Format (STRICT JSON ARRAY)
**Return ONLY this structure (no code blocks):**

[
  {
    "page_index": 0,
    "markdown_content": "# ГОСТ Р 7.0.97-2025\\n## Раздел 1\\n...",
    "reference_blocks": [{"section_ref": "1.1", "start_line": 5, "end_line": 10, "keywords": ["документ", "поля-20mm"]}],
    "metadata": {"document_id": null, "jurisdiction_code": "RU", "authority": "Росстандарт", "title": "...", "citation_code": "ГОСТ Р 7.0.97-2025", "language": "ru", "publication_date": null, "effective_date": "2025-07-01", "source_url": null, "retrieval_datetime": null, "original_format": "pdf", "file_path": null, "raw_text_path": null, "section_label": "Раздел 1", "page_range": null, "keywords": [], "country": "RU", "regulation_type": "GOST"},
    "entities": [{"name": "Росстандарт", "type": "Organization", "context": "regulatory authority"}],
    "tables": [{"headers": ["Реквизит", "Описание"], "rows": [["Дата", "Дата документа"]], "caption": "Таблица 1"}]
  },
  {
    "page_index": 1,
    "markdown_content": "### 1.2 Определения\\n...",
    "reference_blocks": [],
    "metadata": {"document_id": null, "jurisdiction_code": null, "authority": null, "title": null, "citation_code": null, "language": null, "publication_date": null, "effective_date": "2025-07-15", "source_url": null, "retrieval_datetime": null, "original_format": null, "file_path": null, "raw_text_path": null, "section_label": null, "page_range": null, "keywords": [], "country": null, "regulation_type": null},
    "entities": [],
    "tables": []
  }
]

**CRITICAL:**
1. Return ONLY the JSON array (no ```json wrapper)
2. page_index must match image order (0-based)
3. **EACH page extracts metadata independently (null if not visible on that page)**
4. System will merge non-null values across all pages
5. markdown_content = full original text in Russian (NO SUMMARIZATION, preserve dimensions)
6. reference_blocks = index only (no text field)
7. Preserve Cyrillic characters correctly
8. Extract layout parameters to keywords array"""

    # 기본 배치 프롬프트 (하위 호환성)
    BATCH_SYSTEM_PROMPT_ID = """You are a regulatory document structure expert specializing in Indonesian regulatory formats (UU, PP, Peraturan Menteri, Peraturan Daerah).

**CRITICAL: You MUST return ONLY a valid JSON array. No markdown code blocks, no explanations, ONLY the JSON array.**

## Task
You will receive MULTIPLE Indonesian document pages as images. Extract structured data for EACH page following Indonesian legal drafting patterns.

## Per-Page Extraction

### 1. Markdown Content (Indonesian Legal Pattern)
- Use `#` for Regulation ID, `##` for BAB, `###` for Pasal, `####` for Ayat
- Extract FULL original text (NO SUMMARIZATION, NO "..." ELLIPSIS)
- Preserve Indonesian legal terminology correctly
- Extract tables as markdown directly (not placeholders)

### 2. Reference Blocks (Index Only)
- Brief metadata for each section/table
- `section_ref`, `start_line`, `end_line`, `keywords`

### 3. Metadata (Extract from EACH page independently)
**CRITICAL: Extract document metadata visible on THIS page only.**
- If field not visible on current page, use null
- System will accumulate non-null values across pages

**All fields required (use null if not found on THIS page):**
```json
{
  "document_id": null,
  "jurisdiction_code": "ID",
  "authority": "Pemerintah Republik Indonesia",
  "title": "Full regulation title",
  "citation_code": "UU No. 12 Tahun 2011",
  "language": "id",
  "publication_date": null,
  "effective_date": "2011-08-12",
  "source_url": null,
  "retrieval_datetime": null,
  "original_format": "pdf",
  "file_path": null,
  "raw_text_path": null,
  "section_label": "BAB I",
  "page_range": null,
  "keywords": ["peraturan", "perundang-undangan"],
  "country": "ID",
  "regulation_type": "UU"
}
```

### 4. Entities & Tables
- Extract as JSON arrays

## Output Format (STRICT JSON ARRAY)
**Return ONLY this structure (no code blocks):**

[
  {
    "page_index": 0,
    "markdown_content": "# UU No. 12 Tahun 2011\\n## BAB I\\n### Pasal 1\\n(1) Dalam Undang-Undang ini...",
    "reference_blocks": [{"section_ref": "Pasal 1", "start_line": 5, "end_line": 10, "keywords": ["ketentuan"]}],
    "metadata": {"document_id": null, "jurisdiction_code": "ID", "authority": "Pemerintah RI", "title": "...", "citation_code": "UU No. 12 Tahun 2011", "language": "id", "publication_date": null, "effective_date": "2011-08-12", "source_url": null, "retrieval_datetime": null, "original_format": "pdf", "file_path": null, "raw_text_path": null, "section_label": "BAB I", "page_range": null, "keywords": [], "country": "ID", "regulation_type": "UU"},
    "entities": [{"name": "Kementerian Hukum dan HAM", "type": "Organization", "context": "regulatory authority"}],
    "tables": [{"headers": ["Jenis", "Pembentuk"], "rows": [["UU", "DPR"]], "caption": "Tabel 1"}]
  },
  {
    "page_index": 1,
    "markdown_content": "### Pasal 2\\n...",
    "reference_blocks": [],
    "metadata": {"document_id": null, "jurisdiction_code": null, "authority": null, "title": null, "citation_code": null, "language": null, "publication_date": null, "effective_date": "2011-08-15", "source_url": null, "retrieval_datetime": null, "original_format": null, "file_path": null, "raw_text_path": null, "section_label": null, "page_range": null, "keywords": [], "country": null, "regulation_type": null},
    "entities": [],
    "tables": []
  }
]

**CRITICAL:**
1. Return ONLY the JSON array (no ```json wrapper)
2. page_index must match image order (0-based)
3. **EACH page extracts metadata independently (null if not visible on that page)**
4. System will merge non-null values across all pages
5. markdown_content = full original text in Indonesian (NO SUMMARIZATION)
6. reference_blocks = index only (no text field)
7. Preserve Indonesian legal terminology correctly"""

    # 기본 배치 프롬프트 (하위 호환성)
    BATCH_SYSTEM_PROMPT = BATCH_SYSTEM_PROMPT_US

    def __init__(self, language_code: str = "en"):
        """
        Args:
            language_code: 문서 언어 코드 (en, ru, ko 등)
        """
        self.language_code = language_code.lower()

    def get_system_prompt(self) -> str:
        """
        언어별 시스템 프롬프트 반환.

        Returns:
            해당 언어의 시스템 프롬프트
        """
        if self.language_code == "ru":
            return self.SYSTEM_PROMPT_RU
        elif self.language_code == "id":
            return self.SYSTEM_PROMPT_ID
        else:
            # 기본값: 영어/미국 (en, ko 등 모두 US 프롬프트 사용)
            return self.SYSTEM_PROMPT_US

    def get_batch_system_prompt(self) -> str:
        """
        언어별 배치 시스템 프롬프트 반환.

        Returns:
            해당 언어의 배치 프롬프트
        """
        if self.language_code == "ru":
            return self.BATCH_SYSTEM_PROMPT_RU
        elif self.language_code == "id":
            return self.BATCH_SYSTEM_PROMPT_ID
        else:
            return self.BATCH_SYSTEM_PROMPT_US

    def extract(self, llm_output: str, page_num: int) -> PageStructure:
        """
        LLM 출력을 구조화.

        Args:
            llm_output: Vision LLM의 원본 출력
            page_num: 페이지 번호

        Returns:
            PageStructure: 검증된 구조화 데이터
        """
        try:
            # JSON 파싱 시도
            parsed = self._parse_json(llm_output)

            # Pydantic 검증
            structure = PageStructure(
                page_num=page_num,
                markdown_content=parsed.get("markdown_content", llm_output),
                reference_blocks=[
                    ReferenceBlock(**rb) for rb in parsed.get("reference_blocks", [])
                ],
                metadata=(
                    DocumentMetadata(**parsed["metadata"])
                    if parsed.get("metadata")
                    else None
                ),
                entities=[ExtractedEntity(**e) for e in parsed.get("entities", [])],
                tables=[ExtractedTable(**t) for t in parsed.get("tables", [])],
            )

            logger.debug(
                f"페이지 {page_num} 구조화 완료: {len(structure.entities)}개 엔티티, {len(structure.tables)}개 표"
            )

            return structure

        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"페이지 {page_num} 구조화 실패, 원본 텍스트 사용: {e}")

            # Fallback: 원본 텍스트만 사용
            return PageStructure(
                page_num=page_num, markdown_content=llm_output, entities=[], tables=[]
            )

    def extract_batch(
        self, page_infos: List[Dict[str, Any]], model: str
    ) -> List[Dict[str, Any]]:
        """
        배치 단위 구조화 (여러 페이지를 한 번에 Vision LLM에 전송).

        Args:
            page_infos: 페이지 정보 리스트
            model: 사용할 모델명

        Returns:
            List[Dict]: 페이지별 구조화 결과
        """
        from openai import OpenAI
        from ..config import PreprocessConfig

        config = PreprocessConfig.get_vision_config()

        # OpenAI 클라이언트 생성
        client = OpenAI(api_key=config["api_key"], timeout=config["request_timeout"])
        client = PreprocessConfig.wrap_openai_client(client)

        # 배치 메시지 구성 (언어별 프롬프트)
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": self.get_batch_system_prompt(),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {"role": "user", "content": self._build_batch_user_content(page_infos)},
        ]

        logger.info(f"배치 Vision 호출: {model}, {len(page_infos)}페이지")

        # Vision API 호출
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
            )

            batch_content = response.choices[0].message.content
            total_tokens = response.usage.total_tokens

            # 배치 결과 파싱
            return self._parse_batch_response(
                batch_content, page_infos, model, total_tokens
            )

        except Exception as e:
            logger.error(f"배치 Vision 호출 실패 ({model}): {e}")
            # Fallback: 개별 페이지로 처리
            return self._fallback_individual_processing(page_infos, model)

    def _build_batch_user_content(
        self, page_infos: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """배치용 사용자 메시지 콘텐츠 구성."""
        content = []

        for i, page_info in enumerate(page_infos):
            content.append(
                {
                    "type": "text",
                    "text": f"Page {i} (original page {page_info['page_index'] + 1}):",
                }
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{page_info['image_base64']}"
                    },
                }
            )

        content.append(
            {
                "type": "text",
                "text": f"Extract structure from all {len(page_infos)} pages above. Return JSON array.",
            }
        )

        return content

    def _parse_batch_response(
        self,
        batch_content: str,
        page_infos: List[Dict[str, Any]],
        model: str,
        total_tokens: int,
    ) -> List[Dict[str, Any]]:
        """배치 응답 파싱."""
        try:
            # JSON 배열 파싱
            batch_results = self._parse_json_array(batch_content)

            if len(batch_results) != len(page_infos):
                logger.warning(
                    f"배치 결과 개수 불일치: 예상 {len(page_infos)}, 실제 {len(batch_results)}"
                )

            results = []
            tokens_per_page = total_tokens // len(page_infos) if page_infos else 0

            for i, page_info in enumerate(page_infos):
                page_index = page_info["page_index"]
                page_num = page_index + 1

                # 해당 페이지 결과 찾기
                page_result = None
                for result in batch_results:
                    if result.get("page_index") == i:
                        page_result = result
                        break

                if not page_result:
                    logger.warning(f"페이지 {page_num} 결과 없음, fallback 사용")
                    page_result = {
                        "markdown_content": f"# Page {page_num}\n\nContent extraction failed.",
                        "reference_blocks": [],
                        "metadata": None,
                        "entities": [],
                        "tables": [],
                    }

                # PageStructure 생성
                structure = PageStructure(
                    page_num=page_num,
                    markdown_content=page_result.get("markdown_content", ""),
                    reference_blocks=[
                        ReferenceBlock(**rb)
                        for rb in page_result.get("reference_blocks", [])
                    ],
                    metadata=(
                        DocumentMetadata(**page_result["metadata"])
                        if page_result.get("metadata")
                        else None
                    ),
                    entities=[
                        ExtractedEntity(**e) for e in page_result.get("entities", [])
                    ],
                    tables=[ExtractedTable(**t) for t in page_result.get("tables", [])],
                )

                results.append(
                    {
                        "page_index": page_index,
                        "page_num": page_num,
                        "model_used": model,
                        "content": page_result.get("markdown_content", ""),
                        "complexity_score": page_info["complexity"],
                        "tokens_used": tokens_per_page,
                        "structure": structure.dict(),
                    }
                )

            logger.info(f"배치 파싱 완료: {len(results)}페이지, {total_tokens}토큰")
            return results

        except Exception as e:
            logger.error(f"배치 응답 파싱 실패: {e}")
            return self._fallback_individual_processing(page_infos, model)

    def _parse_json_array(self, text: str) -> List[Dict[str, Any]]:
        """JSON 배열 파싱 (강화된 파싱)."""
        import re

        # 1. 마크다운 코드 블록 제거
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            json_str = text

        # 2. JSON 배열 추출
        if "[" in json_str and "]" in json_str:
            start = json_str.find("[")
            end = json_str.rfind("]") + 1
            json_str = json_str[start:end]
        else:
            raise json.JSONDecodeError("No JSON array found", text, 0)

        # 3. 파싱 시도
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # 4. 일반적인 JSON 오류 수정 시도
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)
            return json.loads(json_str)

    def _fallback_individual_processing(
        self, page_infos: List[Dict[str, Any]], model: str
    ) -> List[Dict[str, Any]]:
        """배치 실패 시 개별 페이지 처리 fallback."""
        logger.warning(f"배치 처리 실패, 개별 처리로 fallback: {len(page_infos)}페이지")

        results = []
        for page_info in page_infos:
            page_index = page_info["page_index"]
            page_num = page_index + 1

            # 기본 구조 생성
            structure = PageStructure(
                page_num=page_num,
                markdown_content=f"# Page {page_num}\n\nBatch processing failed, fallback used.",
                entities=[],
                tables=[],
            )

            results.append(
                {
                    "page_index": page_index,
                    "page_num": page_num,
                    "model_used": model,
                    "content": structure.markdown_content,
                    "complexity_score": page_info["complexity"],
                    "tokens_used": 100,  # 추정값
                    "structure": structure.dict(),
                }
            )

        return results

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """LLM 출력에서 JSON 추출 (강화된 파싱)."""
        import re

        # 1. 마크다운 코드 블록 제거
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_str = text[start:end].strip()
        elif "```" in text:
            # ```만 있는 경우
            start = text.find("```") + 3
            end = text.find("```", start)
            json_str = text[start:end].strip()
        else:
            json_str = text

        # 2. JSON 객체 추출
        if "{" in json_str and "}" in json_str:
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            json_str = json_str[start:end]
        else:
            raise json.JSONDecodeError("No JSON object found", text, 0)

        # 3. 파싱 시도
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # 4. 일반적인 JSON 오류 수정 시도
            # 후행 쉼표 제거
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)
            return json.loads(json_str)
