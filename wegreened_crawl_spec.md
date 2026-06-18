# WeGreened Crawl Spec

Tài liệu này mô tả chiến lược crawl định kỳ từ wegreened.com để xây dựng dataset case immigration (NIW / EB-1A / EB-1B) phục vụ analytics và RAG.

---

## 1. Tổng quan nguồn dữ liệu

| Source | URL Pattern | Tần suất update | Giá trị |
|---|---|---|---|
| Daily approval digest | `/Latest-Information/{slug}` | Hàng ngày | ⭐⭐⭐ Rich nhất |
| Success story blog | `/blog/niw/`, `/blog/eb1/` | Vài lần/tuần | ⭐⭐ Narrative |
| Approval notice PDF | S3 bucket (thumbnail + PDF) | Hàng ngày | ⭐ Ít extract được |

---

## 2. Source 1 — Daily Approval Digest (Ưu tiên cao nhất)

### 2.1 Entry point

```
https://www.wegreened.com/Latest-Information
```

Trang index liệt kê các bài theo ngày. Paginate bằng query param:

```
/Latest-Information?page=1
/Latest-Information?page=2
...
/Latest-Information?page=14   ← hiện tại ~14 pages
```

Mỗi item trên index có dạng:

```
- [58 I-140 Approvals on June 3, 2026] → /Latest-Information/58-i-140-approvals-on-june-3-2026
- [11 I-140 Approvals After RFE on June 3, 2026] → ...
```

### 2.2 Cấu trúc một bài digest

Mỗi bài là **prose text** (không phải HTML table hay JSON), structured theo pattern:

```
### #N: {CATEGORY} in {FIELD}

Born in {COUNTRY} and residing in {RESIDENCE}, this applicant works as a {CURRENT_ROLE}
and proposes to {PROPOSED_ROLE}. The petition was approved under {CATEGORY} in {FIELD}.

The applicant holds a {DEGREE} and had {PUBLICATIONS} publications and {CITATIONS} citations
at the time of filing.

Supported by {REC_LETTERS} recommendation letters and {TESTIMONIAL_LETTERS} testimonial letters,
the case was adjudicated at the {SERVICE_CENTER} with {PREMIUM_PROCESSING}.
[and was approved in {DAYS} days.]

**Notable:** {NOTABLE_FLAGS}
```

### 2.3 Fields cần extract

```python
{
    # metadata
    "source_url": str,
    "crawl_date": "YYYY-MM-DD",
    "approval_date": "YYYY-MM-DD",   # parse từ title bài

    # case info
    "case_number": int,              # số thứ tự trong bài (#1, #2...)
    "category": str,                 # "NIW" | "EB-1A" | "EB-1B"
    "field": str,                    # "Machine Learning", "Civil Engineering"...

    # applicant profile
    "country_birth": str,
    "residence_during_filing": str,  # "US" | tên quốc gia nếu outside US
    "residing_outside_us": bool,
    "degree": str,                   # "PhD" | "Master" | "Bachelor" | "MD" | "MBBS"
    "current_role": str,
    "proposed_role": str,
    "sector": str,                   # "academia" | "industry" | infer từ role

    # evidence profile
    "publications": int,
    "citations": int,
    "rec_letters": int,
    "testimonial_letters": int,
    "total_letters": int,            # rec + testimonial
    "no_letters": bool,              # approved without any letters

    # adjudication
    "service_center": str,           # "Nebraska" | "Texas" | "SCOPS"
    "premium_processing": str,       # "upfront" | "upgrade" | "none"
    "processing_days": int | None,   # None nếu premium (không công bố)
    "had_rfe": bool,                 # infer từ title bài ("After RFE")

    # notable flags (list)
    "notable": list[str],
    # possible values:
    # "no_rfe", "approved_without_letters", "non_stem",
    # "outside_us", "no_phd", "approved_after_rfe"
}
```

### 2.4 Chiến lược parse

Dùng **Claude API (structured output)** để extract fields từ prose text, vì format không hoàn toàn nhất quán.

```python
SYSTEM_PROMPT = """
Bạn là parser trích xuất thông tin từ immigration case description.
Trả về JSON thuần, không markdown, không giải thích.
Nếu field không có trong text, trả về null.
"""

USER_PROMPT = """
Extract các fields sau từ đoạn case description này:
{case_text}

Trả về JSON với schema:
{schema}
"""
```

Batch nhiều case trong một lần gọi API để tiết kiệm cost:
- Gom 10 case/request → parse song song
- Model: `claude-haiku-4-5` (nhanh + rẻ cho extraction task)

### 2.5 Detect bài mới (incremental crawl)

```python
# Lưu set URL đã crawl vào DB
crawled_urls = set(db.query("SELECT source_url FROM cases"))

# Chỉ fetch bài chưa có
for url in index_urls:
    if url not in crawled_urls:
        crawl_and_parse(url)
```

Không cần crawl lại toàn bộ — chỉ check page 1 của index mỗi lần chạy.

---

## 3. Source 2 — Success Story Blog

### 3.1 Entry points

```
https://www.wegreened.com/blog/niw/
https://www.wegreened.com/blog/eb1/
```

Sub-categories theo field (dùng để filter):

```
/blog/computer-science/
/blog/biology/
/blog/electrical-engineering/
/blog/medical/
/blog/mathematics/
/blog/chemistry/
/blog/mechanical-engineering/
/blog/civil-engineering/
/blog/energy-engineering/
/blog/material-engineering/
/blog/art-athletic/
/blog/economics/
```

### 3.2 Dùng làm gì

Blog posts dài hơn → phù hợp làm **RAG documents** hơn là structured records. Mỗi bài embed toàn bộ và lưu kèm metadata:

```python
{
    "doc_id": "wegreened_blog_{slug}",
    "url": str,
    "title": str,
    "category": str,      # NIW | EB-1A | EB-1B
    "field": str,
    "published_date": str,
    "content": str,       # full text để embed
    "chunk_strategy": "full_doc"  # doc ngắn, không cần chunk
}
```

### 3.3 Embed và store

```python
# Embed dùng multilingual model vì L&C serve cả tiếng Việt
model = "text-embedding-3-small"  # hoặc multilingual-e5-large nếu self-host

# Store vào AstraDB collection: "wegreened_cases"
collection.insert({
    "doc_id": ...,
    "content": ...,
    "$vector": embed(content),
    "metadata": {...}
})
```

---

## 4. Source 3 — Approval Notice PDFs (Low priority)

### 4.1 Pattern

```
# Thumbnail JPG (public, no auth)
https://wegreened-evaluation-production.s3.amazonaws.com/approvals/jpgs_2026/{filename}.jpg

# PDF gốc (public, no auth)
https://wegreened-evaluation-production.s3.amazonaws.com/approvals/pdfs_2025/{filename}.pdf

# Approval viewer page
https://www.wegreened.com/Approval_Viewer?pdf={id}   # id là integer tăng dần
```

### 4.2 Có thể làm gì

- Download PDF → OCR → extract: date, category (NIW/EB-1A), service center, decision
- **Tuy nhiên**: tên đã bị redact, field của applicant không có trong PDF notice
- **Không nên ưu tiên** trừ khi cần verify approval date hoặc service center

---

## 5. Lịch crawl định kỳ

```yaml
# GitHub Actions schedule
schedule:
  - cron: "0 1 * * *"   # 1AM UTC = 8AM Vietnam, chạy sau khi WeGreened post daily

jobs:
  crawl_latest_info:
    # crawl /Latest-Information page 1
    # parse bài mới nhất
    # insert records vào DB

  crawl_blog_weekly:
    cron: "0 2 * * 1"   # Thứ 2 hàng tuần
    # crawl /blog/niw + /blog/eb1
    # detect bài mới bằng URL diff
    # embed + insert vào AstraDB
```

---

## 6. Schema database (Supabase / PostgreSQL)

```sql
CREATE TABLE wegreened_cases (
    id              SERIAL PRIMARY KEY,
    source_url      TEXT UNIQUE NOT NULL,
    crawl_date      DATE NOT NULL,
    approval_date   DATE,
    case_number     INT,

    -- Case info
    category        TEXT,   -- NIW, EB-1A, EB-1B
    field           TEXT,
    field_stem      BOOLEAN,

    -- Applicant
    country_birth   TEXT,
    residence       TEXT,
    outside_us      BOOLEAN DEFAULT FALSE,
    degree          TEXT,
    current_role    TEXT,
    proposed_role   TEXT,
    sector          TEXT,   -- academia, industry

    -- Evidence
    publications    INT,
    citations       INT,
    rec_letters     INT,
    testimonial_letters INT,
    no_letters      BOOLEAN DEFAULT FALSE,

    -- Adjudication
    service_center  TEXT,
    premium_processing TEXT,
    processing_days INT,
    had_rfe         BOOLEAN DEFAULT FALSE,

    -- Flags
    notable         TEXT[], -- array of flag strings

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes hữu ích cho analytics
CREATE INDEX ON wegreened_cases (category);
CREATE INDEX ON wegreened_cases (field);
CREATE INDEX ON wegreened_cases (approval_date);
CREATE INDEX ON wegreened_cases (country_birth);
CREATE INDEX ON wegreened_cases (citations);
CREATE INDEX ON wegreened_cases (had_rfe);
```

---

## 7. Queries analytics hữu ích

```sql
-- Approval rate by field (top fields)
SELECT field, COUNT(*) as cases, AVG(citations) as avg_citations
FROM wegreened_cases
WHERE category = 'NIW'
GROUP BY field
ORDER BY cases DESC
LIMIT 20;

-- Citations distribution for NIW approval (no RFE)
SELECT
    CASE
        WHEN citations < 10 THEN '0-9'
        WHEN citations < 50 THEN '10-49'
        WHEN citations < 200 THEN '50-199'
        WHEN citations < 500 THEN '200-499'
        ELSE '500+'
    END as citation_range,
    COUNT(*) as approved_cases
FROM wegreened_cases
WHERE category = 'NIW' AND had_rfe = FALSE
GROUP BY citation_range;

-- Processing time by service center (non-premium)
SELECT service_center, AVG(processing_days), MIN(processing_days), MAX(processing_days)
FROM wegreened_cases
WHERE premium_processing = 'none' AND processing_days IS NOT NULL
GROUP BY service_center;

-- Cases approved without letters
SELECT category, field, publications, citations
FROM wegreened_cases
WHERE no_letters = TRUE
ORDER BY citations DESC;

-- Vietnamese applicants (benchmark L&C clients)
SELECT * FROM wegreened_cases
WHERE country_birth = 'Vietnam'
ORDER BY approval_date DESC;
```

---

## 8. Rate limiting & etiquette

```python
REQUEST_DELAY = 3.0      # seconds between requests
MAX_CONCURRENT = 1       # sequential only, không parallel
USER_AGENT = "Mozilla/5.0 (compatible; research-bot/1.0)"
TIMEOUT = 15             # seconds per request

# Check robots.txt trước khi chạy full
# https://www.wegreened.com/robots.txt
```

Không crawl S3 PDFs ở quy mô lớn (68K files × bandwidth = không cần thiết).

---

## 9. Estimated dataset size

| Source | Records ước tính | Fields per record |
|---|---|---|
| /Latest-Information (backfill) | ~5,000 cases | 25+ fields |
| /Latest-Information (ongoing) | ~30–60 cases/ngày | 25+ fields |
| /blog success stories | ~500 documents | text + metadata |

Sau backfill đầy đủ: **~5,000 structured records** + **~500 RAG documents**.
Đủ để: benchmark hồ sơ client, phân tích citation threshold theo field, train similarity matching.
