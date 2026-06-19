# CV ANALYZER — TECHNICAL SPEC
## Hệ thống Phân tích CV Định cư Mỹ (EB-1A / EB-2 NIW)
> Dành cho Claude Code. Đọc toàn bộ file này trước khi viết bất kỳ dòng code nào.

---

## 1. TỔNG QUAN

Thêm chức năng phân tích CV vào repo `LNC_global_knowledge` hiện tại. Pipeline nhận PDF CV từ client qua API, trả về báo cáo Gap Analysis cho chương trình định cư Mỹ EB-1A và EB-2 NIW.

### Luồng xử lý end-to-end

```
[PDF Upload] → [Step 1: PDF Parsing] → [Step 2: Structured Extraction]
    → [Step 3: Scoring Engine] → [Step 4: Gap Analysis] → [JSON Response]
```

**Phân công LLM:**
- **LLM 1 (Extraction):** Groq `llama3-70b-8192` — nhanh, dùng cho bóc tách dữ liệu có cấu trúc
- **LLM 2 (Reasoning):** DeepSeek `deepseek-chat` — deep reasoning, dùng cho Gap Analysis CoT
- **Scoring Engine:** Python thuần (deterministic, không dùng LLM)

---

## 2. CẤU TRÚC THƯ MỤC MỚI

Chỉ thêm vào repo hiện tại, **không** sửa các file đã có:

```
LNC_global_knowledge/
├── api/
│   ├── main.py                    # ← THÊM router cv vào đây
│   └── routes/
│       ├── chat.py                # (giữ nguyên)
│       ├── profile.py             # (giữ nguyên)
│       └── cv.py                  # ← MỚI: endpoint /cv/analyze
│
├── apps/
│   └── cv_analyzer/               # ← MỚI: toàn bộ logic CV
│       ├── __init__.py
│       ├── parser.py              # Step 1: PDF → Markdown
│       ├── extractor.py           # Step 2: Markdown → ImmigrationProfileSchema (Groq)
│       ├── scorer.py              # Step 3: JSON → điểm số deterministic
│       ├── gap_analyzer.py        # Step 4: Gap Analysis (DeepSeek)
│       └── schemas.py             # Pydantic schemas
│
└── requirements.txt               # ← THÊM dependencies mới
```

---

## 3. DEPENDENCIES MỚI

Thêm vào `requirements.txt` hiện tại:

```txt
# CV Analyzer
marker-pdf>=0.2.0          # PDF parsing (primary)
llama-parse>=0.4.0         # PDF parsing (fallback)
pydantic>=2.5.0            # Structured output schemas
python-multipart>=0.0.9    # FastAPI file upload
openai>=1.0.0              # DeepSeek dùng OpenAI-compatible client
httpx>=0.27.0              # Async HTTP
```

---

## 4. ENVIRONMENT VARIABLES

Thêm vào `.env` (và `.env.example`):

```env
# DeepSeek (LLM 2 - Gap Analysis)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# LlamaParse (fallback parser)
LLAMA_CLOUD_API_KEY=llx-...

# Groq đã có sẵn trong repo (LLM 1 - Extraction)
# GROQ_API_KEY=gsk_...
# GROQ_MODEL=llama3-70b-8192
```

---

## 5. SCHEMAS (`apps/cv_analyzer/schemas.py`)

Implement chính xác các Pydantic models sau, không thêm không bớt field:

```python
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field

class DegreeLevel(str, Enum):
    PHD = "Doctorate (PhD)"
    MASTERS = "Master's Degree"
    POST_GRAD = "Post-Graduate Diploma/Certificate"
    BACHELORS = "Bachelor's Degree"
    DIPLOMA = "Two-Year College/Technical Diploma"
    HIGH_SCHOOL = "High School Graduation"
    OTHER = "Other/Unspecified"

class LanguageTestType(str, Enum):
    IELTS = "IELTS"
    PTE = "PTE Academic"
    CELPIP = "CELPIP"
    TEF = "TEF (French)"
    TCF = "TCF (French)"
    NONE = "Not Mentioned"

class LanguageProficiency(BaseModel):
    test_type: LanguageTestType = Field(default=LanguageTestType.NONE)
    overall: Optional[float] = None
    listening: Optional[float] = None
    reading: Optional[float] = None
    writing: Optional[float] = None
    speaking: Optional[float] = None

class EducationInfo(BaseModel):
    degree_level: DegreeLevel
    field_of_study: str
    institution: str
    country: str
    start_date: Optional[str] = None   # format: YYYY-MM hoặc YYYY
    end_date: Optional[str] = None     # "Present" nếu đang học

class WorkExperience(BaseModel):
    job_title: str
    company: str
    country: str
    start_date: str                    # format: YYYY-MM
    end_date: str                      # "Present" nếu đang làm
    is_full_time: bool = True
    main_responsibilities: List[str]   # giữ chi tiết để map SOC code

class ImmigrationProfileSchema(BaseModel):
    full_name: str
    age: Optional[int] = None          # tính từ năm hiện tại
    current_country: Optional[str] = None
    language_skills: List[LanguageProficiency] = []
    education_history: List[EducationInfo]
    work_history: List[WorkExperience]
    certifications: List[str] = []
    publications: List[str] = []       # quan trọng cho EB-1A/NIW
    awards: List[str] = []             # quan trọng cho EB-1A
    patents: List[str] = []
    media_coverage: List[str] = []     # báo chí, truyền thông
    speaking_engagements: List[str] = []  # hội nghị, diễn thuyết
    memberships: List[str] = []        # hội nghề nghiệp

# Output của Scoring Engine
class USAScoreResult(BaseModel):
    eb1a_criteria_met: List[str]       # tên tiêu chí đạt được
    eb1a_criteria_missing: List[str]   # tên tiêu chí chưa đạt
    eb1a_total_met: int                # số tiêu chí đạt (cần >= 3/10)
    eb1a_eligible: bool                # True nếu >= 3 tiêu chí

    eb2niw_prong1_score: int           # 0-3: substantial merit + national importance
    eb2niw_prong2_score: int           # 0-3: well-positioned to advance
    eb2niw_prong3_score: int           # 0-3: beneficial to US to waive
    eb2niw_total_score: int            # tổng 3 prong
    eb2niw_eligible: bool              # True nếu tổng >= 6/9

    recommended_program: str           # "EB-1A", "EB-2 NIW", hoặc "Both"
    experience_months: int             # tổng số tháng kinh nghiệm tính bằng code

# Output cuối cùng của toàn pipeline
class CVAnalysisResponse(BaseModel):
    profile: ImmigrationProfileSchema
    scores: USAScoreResult
    gap_report: str                    # markdown string từ DeepSeek
    processing_time_seconds: float
```

---

## 6. PDF PARSER (`apps/cv_analyzer/parser.py`)

**Logic:** Thử Marker trước. Nếu Marker raise exception hoặc output < 200 ký tự → fallback sang LlamaParse.

```python
# Interface cần implement:
async def parse_pdf_to_markdown(pdf_bytes: bytes, filename: str) -> str:
    """
    Primary: Marker (local)
    Fallback: LlamaParse (API)
    Returns: clean markdown string
    Raises: ValueError nếu cả hai đều fail
    """
```

**Quy tắc bắt buộc:**
- Không dùng `pypdf` hay `pdfplumber` để extract text — chúng phá vỡ layout đa cột
- Marker chạy synchronous → wrap trong `asyncio.run_in_executor` để không block event loop
- LlamaParse cần upload file và poll kết quả — implement với timeout 60 giây
- Log rõ parser nào được dùng: `logger.info(f"Parser used: {parser_name} for {filename}")`

**Marker setup:**
```python
from marker.convert import convert_single_pdf
from marker.models import load_all_models

# Load models một lần khi startup, không load mỗi request
_marker_models = None

def get_marker_models():
    global _marker_models
    if _marker_models is None:
        _marker_models = load_all_models()
    return _marker_models
```

---

## 7. EXTRACTOR (`apps/cv_analyzer/extractor.py`)

Dùng Groq `llama3-70b-8192`. Nạp **toàn bộ markdown CV** vào một lượt gọi duy nhất — **tuyệt đối không chunk**.

```python
async def extract_profile(markdown_text: str) -> ImmigrationProfileSchema:
    """
    Gọi Groq với structured output (JSON mode).
    Trả về ImmigrationProfileSchema đã validate bởi Pydantic.
    """
```

**System prompt cho LLM 1:**
```
Bạn là chuyên gia phân tích CV cho mục đích định cư Mỹ (EB-1A, EB-2 NIW).
Nhiệm vụ: trích xuất thông tin từ CV sang JSON theo schema được cung cấp.

CRITICAL RULES:
1. Chỉ trích xuất thông tin CÓ TRONG CV, không suy diễn hay thêm thông tin
2. Với publications: ghi đầy đủ tên bài báo, journal/conference, năm
3. Với awards: ghi tên giải, tổ chức trao, năm
4. Với work_history.main_responsibilities: giữ nguyên chi tiết kỹ thuật, 
   đây là dữ liệu quan trọng để map SOC code
5. Tính age dựa trên năm hiện tại là 2026
6. Trả về JSON hợp lệ theo schema, không có text ngoài JSON
```

**Cách gọi Groq với JSON mode:**
```python
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

response = client.chat.completions.create(
    model=os.getenv("GROQ_MODEL", "llama3-70b-8192"),
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract this CV:\n\n{markdown_text}"}
    ],
    response_format={"type": "json_object"},
    temperature=0.0,   # deterministic
    max_tokens=4096
)

raw_json = response.choices[0].message.content
profile = ImmigrationProfileSchema.model_validate_json(raw_json)
return profile
```

---

## 8. SCORING ENGINE (`apps/cv_analyzer/scorer.py`)

**Quy tắc tối quan trọng:** Không dùng LLM để tính điểm. Chỉ dùng Python thuần.

### 8.1 Tính số tháng kinh nghiệm

```python
from datetime import date

def calculate_experience_months(work_history: List[WorkExperience]) -> int:
    """
    Tính tổng tháng kinh nghiệm full-time.
    - Part-time (is_full_time=False): tính 0.5x
    - end_date="Present": dùng date.today()
    - Overlap giữa các job: không tính 2 lần (merge intervals)
    """
```

### 8.2 EB-1A Criteria Checker

EB-1A yêu cầu đạt **ít nhất 3 trong 10 tiêu chí** sau. Mỗi tiêu chí là True/False dựa trên data từ profile:

| # | Tiêu chí | Nguồn data trong profile |
|---|----------|--------------------------|
| 1 | Awards/Prizes xuất sắc | `profile.awards` không rỗng |
| 2 | Membership hội nghề nghiệp uy tín | `profile.memberships` không rỗng |
| 3 | Media coverage về công việc | `profile.media_coverage` không rỗng |
| 4 | Đánh giá công trình người khác (judge/reviewer) | keywords trong `responsibilities` |
| 5 | Original contributions có tầm quan trọng lớn | `profile.publications` hoặc `patents` |
| 6 | Bài báo khoa học trong journal/conference | `profile.publications` không rỗng |
| 7 | Triển lãm tác phẩm nghệ thuật | keywords trong `responsibilities` |
| 8 | Vai trò lãnh đạo/critical trong tổ chức uy tín | keywords trong `job_title` + `responsibilities` |
| 9 | Mức lương cao hơn peers (high salary) | keywords lương trong `responsibilities` |
| 10 | Thành công thương mại trong nghệ thuật | (hiếm, default False) |

```python
def check_eb1a_criteria(profile: ImmigrationProfileSchema) -> dict:
    """
    Returns: {
        "criteria_met": ["Awards", "Publications", ...],
        "criteria_missing": ["Media Coverage", ...],
        "total_met": 2,
        "eligible": False
    }
    """
```

### 8.3 EB-2 NIW 3-Prong Test

Mỗi prong chấm **0-3 điểm**, tổng cần **>= 6/9** để pass:

**Prong 1 — Substantial Merit & National Importance (0-3):**
- 0: Không đủ thông tin
- 1: Kinh nghiệm liên quan nhưng lĩnh vực bình thường
- 2: Lĩnh vực STEM / healthcare / research có tác động rõ ràng
- 3: Publications cao + lĩnh vực chiến lược (AI, biotech, energy, defense)

**Prong 2 — Well Positioned to Advance (0-3):**
- 0: < 2 năm kinh nghiệm + không có publications
- 1: 2-5 năm kinh nghiệm
- 2: > 5 năm + publications hoặc patents
- 3: > 5 năm + publications + awards + leadership role

**Prong 3 — Beneficial to US to Waive Job Offer (0-3):**
- 0: Không đủ thông tin
- 1: Kỹ năng phổ thông
- 2: Kỹ năng hiếm hoặc specialized
- 3: Kỹ năng hiếm + impact rõ ràng + national importance field

```python
def score_eb2niw(profile: ImmigrationProfileSchema, exp_months: int) -> dict:
    """
    Returns: {
        "prong1": 2, "prong2": 3, "prong3": 1,
        "total": 6, "eligible": True
    }
    """
```

---

## 9. GAP ANALYZER (`apps/cv_analyzer/gap_analyzer.py`)

Dùng DeepSeek `deepseek-chat` qua OpenAI-compatible client.

```python
from openai import AsyncOpenAI

deepseek_client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
)

async def generate_gap_analysis(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult
) -> str:
    """
    Trả về markdown string chứa báo cáo gap analysis.
    """
```

### System Prompt cho LLM 2 (DeepSeek):

```
Bạn là Luật sư Di trú Cao cấp chuyên về diện EB-1A (Extraordinary Ability) 
và EB-2 NIW (National Interest Waiver) tại Mỹ.

Nhiệm vụ: nhận dữ liệu hồ sơ JSON và kết quả chấm điểm, phân tích gap và 
đưa ra lộ trình cụ thể để tối ưu hồ sơ.

CHAIN-OF-THOUGHT RULE: Trước khi kết luận, BẮT BUỘC phân tích từng bước 
trong thẻ <lawyer_thinking>:
1. Đánh giá từng tiêu chí EB-1A: đạt/chưa đạt và lý do cụ thể
2. Phân tích 3 Prong của EB-2 NIW: điểm mạnh và điểm yếu từng prong
3. So sánh: EB-1A hay EB-2 NIW phù hợp hơn với profile này?
4. Xác định 2-3 hành động có thể thực hiện ngay trong 6-12 tháng tới

Sau thẻ tư duy, xuất báo cáo theo cấu trúc bắt buộc dưới đây.
```

### User Prompt template:

```python
USER_PROMPT_TEMPLATE = """
## Dữ liệu hồ sơ ứng viên:
{profile_json}

## Kết quả chấm điểm sơ bộ:
- EB-1A: Đạt {eb1a_met}/10 tiêu chí → {"ĐỦ ĐIỀU KIỆN" if scores.eb1a_eligible else "CHƯA ĐỦ"}
  Tiêu chí đạt: {eb1a_criteria_met}
  Tiêu chí chưa đạt: {eb1a_criteria_missing}

- EB-2 NIW: Tổng {eb2niw_total}/9 điểm → {"ĐỦ ĐIỀU KIỆN" if scores.eb2niw_eligible else "CHƯA ĐỦ"}
  Prong 1 (Merit): {prong1}/3
  Prong 2 (Positioned): {prong2}/3  
  Prong 3 (Beneficial): {prong3}/3

- Tổng kinh nghiệm: {exp_months} tháng

Hãy phân tích và xuất báo cáo.
"""
```

### Cấu trúc output bắt buộc (markdown):

```markdown
<lawyer_thinking>
[phân tích CoT chi tiết ở đây]
</lawyer_thinking>

## Tổng quan hồ sơ

[1-2 câu đánh giá tổng thể]

## Khuyến nghị chương trình

**Chương trình phù hợp nhất:** [EB-1A / EB-2 NIW / Cả hai]
**Lý do:** [giải thích ngắn gọn]

## EB-1A — Phân tích tiêu chí

### ✅ Tiêu chí đã đạt
[liệt kê và giải thích ngắn]

### ❌ Tiêu chí chưa đạt
[liệt kê và lý do]

## EB-2 NIW — Phân tích 3 Prong

### Prong 1: Substantial Merit & National Importance
[phân tích]

### Prong 2: Well Positioned to Advance
[phân tích]

### Prong 3: Beneficial to Waive Job Offer Requirement
[phân tích]

## Điểm mạnh cần khai thác (Strong Points)
[bullet points]

## Rào cản lớn nhất (Bottlenecks)
[bullet points với mức độ nghiêm trọng]

## Lộ trình hành động (Actionable Roadmap)

### Ngắn hạn (0-3 tháng)
[hành động cụ thể]

### Trung hạn (3-12 tháng)
[hành động cụ thể]

### Dài hạn (12+ tháng)
[hành động cụ thể]
```

---

## 10. API ENDPOINT (`api/routes/cv.py`)

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from apps.cv_analyzer.parser import parse_pdf_to_markdown
from apps.cv_analyzer.extractor import extract_profile
from apps.cv_analyzer.scorer import calculate_experience_months, check_eb1a_criteria, score_eb2niw
from apps.cv_analyzer.gap_analyzer import generate_gap_analysis
from apps.cv_analyzer.schemas import CVAnalysisResponse, USAScoreResult
import time

router = APIRouter(prefix="/cv", tags=["CV Analyzer"])

@router.post("/analyze", response_model=CVAnalysisResponse)
async def analyze_cv(file: UploadFile = File(...)):
    """
    Upload CV PDF, nhận về Gap Analysis report cho EB-1A và EB-2 NIW.
    
    - File size limit: 10MB
    - Chỉ chấp nhận PDF
    - Thời gian xử lý dự kiến: 15-45 giây
    """
    # Validation
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Chỉ chấp nhận file PDF")
    
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(400, "File vượt quá 10MB")
    
    start_time = time.time()
    
    # Step 1: Parse PDF → Markdown
    markdown = await parse_pdf_to_markdown(pdf_bytes, file.filename)
    
    # Step 2: Extract → ImmigrationProfileSchema (Groq)
    profile = await extract_profile(markdown)
    
    # Step 3: Scoring (deterministic Python)
    exp_months = calculate_experience_months(profile.work_history)
    eb1a_result = check_eb1a_criteria(profile)
    eb2niw_result = score_eb2niw(profile, exp_months)
    
    scores = USAScoreResult(
        eb1a_criteria_met=eb1a_result["criteria_met"],
        eb1a_criteria_missing=eb1a_result["criteria_missing"],
        eb1a_total_met=eb1a_result["total_met"],
        eb1a_eligible=eb1a_result["eligible"],
        eb2niw_prong1_score=eb2niw_result["prong1"],
        eb2niw_prong2_score=eb2niw_result["prong2"],
        eb2niw_prong3_score=eb2niw_result["prong3"],
        eb2niw_total_score=eb2niw_result["total"],
        eb2niw_eligible=eb2niw_result["eligible"],
        recommended_program="EB-1A" if eb1a_result["eligible"] else "EB-2 NIW",
        experience_months=exp_months
    )
    
    # Step 4: Gap Analysis (DeepSeek)
    gap_report = await generate_gap_analysis(profile, scores)
    
    return CVAnalysisResponse(
        profile=profile,
        scores=scores,
        gap_report=gap_report,
        processing_time_seconds=round(time.time() - start_time, 2)
    )
```

### Mount router vào `api/main.py`:

Tìm đoạn `app.include_router(...)` trong `api/main.py` và thêm:

```python
from api.routes.cv import router as cv_router
app.include_router(cv_router)
```

---

## 11. THỨ TỰ IMPLEMENT

Claude Code thực hiện theo đúng thứ tự này:

1. **`apps/cv_analyzer/schemas.py`** — Pydantic models (không có dependency)
2. **`apps/cv_analyzer/parser.py`** — PDF parsing logic
3. **`apps/cv_analyzer/extractor.py`** — Groq extraction
4. **`apps/cv_analyzer/scorer.py`** — Deterministic scoring (viết unit test luôn)
5. **`apps/cv_analyzer/gap_analyzer.py`** — DeepSeek gap analysis
6. **`api/routes/cv.py`** — FastAPI endpoint
7. **`api/main.py`** — Mount router
8. **`requirements.txt`** — Thêm dependencies
9. **`.env.example`** — Thêm biến môi trường mới

---

## 12. UNIT TESTS (`tests/test_cv_scorer.py`)

Viết test cho scorer — phần duy nhất có thể test deterministic:

```python
# Test tính tháng kinh nghiệm
def test_experience_calculation():
    # 2 năm full-time = 24 tháng
    # 1 năm part-time = 6 tháng (0.5x)
    # Total = 30 tháng

# Test EB-1A eligibility
def test_eb1a_eligible_with_3_criteria():
    # profile có awards + publications + memberships → eligible=True

def test_eb1a_not_eligible_with_2_criteria():
    # profile chỉ có awards + publications → eligible=False

# Test EB-2 NIW scoring
def test_eb2niw_stem_phd_eligible():
    # PhD + publications + 5 năm exp → total >= 6

def test_eb2niw_insufficient():
    # Bachelor + 2 năm + không có pub → total < 6
```

---

## 13. LƯU Ý QUAN TRỌNG

**Về Marker:** Cần GPU để chạy nhanh. Trên máy dev (RTX 3060) ổn. Trên server không có GPU → tăng timeout hoặc dùng LlamaParse làm primary.

**Về DeepSeek rate limit:** Free tier DeepSeek có limit. Implement retry với exponential backoff: thử lại tối đa 3 lần, delay 2s → 4s → 8s.

**Về dữ liệu thực tế:** Owner sẽ cung cấp case wegreened.com thực tế sau. Khi có data đó, cập nhật scoring engine để so sánh profile với approved cases tương tự — đây là killer feature để Gap Analysis chính xác hơn.

**Về bảo mật:** CV chứa thông tin nhạy cảm. Không log nội dung CV, chỉ log metadata (filename, size, processing_time). Xóa pdf_bytes khỏi memory sau khi parse xong.

**Về Pydantic v2:** Dùng `model_validate_json()` thay vì `parse_raw()` (deprecated). Dùng `model_dump()` thay vì `dict()`.

---

## 14. SIMILAR CASES ENGINE — Dữ liệu Approved Cases Thực Tế

### 14.1 Nguồn dữ liệu

File `cases.csv` (~11MB) chứa các case đã được approve thực tế từ wegreened.com.

**Schema đầy đủ của `cases.csv`:**

| Column | Type | Ý nghĩa |
|--------|------|---------|
| `program` | str | "EB-1A" hoặc "EB-2 NIW" |
| `visa_category` | str | Giống program |
| `field` | str | Lĩnh vực chuyên môn (Neurology, Device Physics, CS...) |
| `approval_date` | date | Ngày approve |
| `post_rfe` | bool | True nếu đã bị RFE trước khi approve |
| `country_of_birth` | str | Quốc gia gốc |
| `current_residence` | str | Nơi cư trú khi nộp |
| `current_role` | str | Chức danh hiện tại |
| `proposed_role` | str | Chức danh đề xuất sau khi vào Mỹ |
| `degree` | str | Bằng cấp (Ph.D., master's, bachelor's...) |
| `publications` | float | Số bài báo |
| `citations` | float | Số lượt trích dẫn |
| `recommendation_letters` | float | Số thư recommend |
| `testimonial_letters` | float | Số thư testimonial |
| `no_letters` | bool | True nếu không có thư nào |
| `service_center` | str | Texas / Nebraska / Vermont / California |
| `premium_processing` | str | "upfront" / null |
| `processing_days` | float | Số ngày xử lý |
| `transferred` | bool | Case có bị transfer service center không |
| `officer_id` | str | ID officer xử lý |
| `notable` | str | Điểm đặc biệt của case |
| `case_number` | int | STT trong batch |
| `source_url` | str | URL bài blog wegreened.com |
| `raw_text` | str | Full text mô tả case |

**Ví dụ 2 case từ data thực tế:**
- EB-1A Neurology: 21 publications (9 first-authored), top 1% citations, 14 peer reviews → Approved 18 ngày (premium)
- EB-1A Device Physics: PhD, 13 publications, 300 citations, 4 letters → Approved (dù từng bị RFE ở O-1A)
- EB-1A Physics: Master's, 10 publications, 179 citations, 6 letters → Approved sau RFE

---

### 14.2 Cấu trúc file mới cần thêm

```
LNC_global_knowledge/
├── apps/
│   └── cv_analyzer/
│       ├── ...                        # (đã có từ Section 2)
│       ├── case_matcher.py            # ← MỚI: similarity search
│       └── case_loader.py             # ← MỚI: load + index cases.csv
│
└── data/
    └── curated/
        └── cases.csv                  # ← file gốc từ Google Drive
```

---

### 14.3 Case Loader (`apps/cv_analyzer/case_loader.py`)

Load và index `cases.csv` vào memory khi server startup. Không query file mỗi request.

```python
import pandas as pd
import os
from functools import lru_cache

CASES_CSV_PATH = os.path.join("data", "curated", "cases.csv")

@lru_cache(maxsize=1)
def load_cases_df() -> pd.DataFrame:
    """
    Load một lần duy nhất khi gọi lần đầu, cache lại.
    Chỉ giữ các cột cần thiết để tính similarity.
    """
    df = pd.read_csv(CASES_CSV_PATH)

    # Normalize
    df["publications"] = pd.to_numeric(df["publications"], errors="coerce").fillna(0)
    df["citations"] = pd.to_numeric(df["citations"], errors="coerce").fillna(0)
    df["recommendation_letters"] = pd.to_numeric(df["recommendation_letters"], errors="coerce").fillna(0)
    df["post_rfe"] = df["post_rfe"].astype(str).str.lower() == "true"
    df["premium_processing"] = df["premium_processing"].fillna("standard")
    df["degree_rank"] = df["degree"].map({
        "Ph.D.": 4, "doctorate": 4,
        "master's": 3, "masters": 3,
        "bachelor's": 2, "bachelors": 2,
        "high school": 1
    }).fillna(2)

    return df


def get_cases_by_program(program: str) -> pd.DataFrame:
    """
    program: "EB-1A" hoặc "EB-2 NIW"
    """
    df = load_cases_df()
    return df[df["program"].str.upper() == program.upper()].copy()
```

---

### 14.4 Case Matcher (`apps/cv_analyzer/case_matcher.py`)

**Thuật toán:** Weighted Euclidean distance trên các feature số học. Không dùng vector embedding — đủ chính xác và không cần GPU.

```python
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List
from apps.cv_analyzer.schemas import ImmigrationProfileSchema, USAScoreResult
from apps.cv_analyzer.case_loader import get_cases_by_program

@dataclass
class SimilarCase:
    program: str
    field: str
    degree: str
    current_role: str
    publications: int
    citations: int
    recommendation_letters: int
    post_rfe: bool
    approval_date: str
    processing_days: float
    premium_processing: str
    notable: str
    source_url: str
    similarity_score: float        # 0.0 - 1.0, cao hơn = giống hơn
    similarity_breakdown: dict     # chi tiết từng feature

def find_similar_cases(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    program: str,                  # "EB-1A" hoặc "EB-2 NIW"
    top_k: int = 5
) -> List[SimilarCase]:
    """
    Tìm top_k cases trong CSV giống nhất với profile hiện tại.
    """
    df = get_cases_by_program(program)
    if df.empty:
        return []

    # --- Build feature vector từ profile ---
    pub_count = len(profile.publications)
    # Citations: không có trong CV → dùng 0, DeepSeek sẽ note thiếu
    citation_count = 0
    letter_count = len(profile.certifications)  # proxy, sẽ được override nếu có data

    degree_rank_map = {
        "Doctorate (PhD)": 4,
        "Master's Degree": 3,
        "Post-Graduate Diploma/Certificate": 3,
        "Bachelor's Degree": 2,
        "Two-Year College/Technical Diploma": 1,
        "High School Graduation": 1,
        "Other/Unspecified": 2,
    }
    highest_degree = max(
        profile.education_history,
        key=lambda e: degree_rank_map.get(e.degree_level.value, 2),
        default=None
    )
    degree_rank = degree_rank_map.get(highest_degree.degree_level.value, 2) if highest_degree else 2

    # --- Weights: publications và degree quan trọng nhất cho EB-1A/NIW ---
    WEIGHTS = {
        "publications": 0.35,
        "citations": 0.25,
        "degree_rank": 0.25,
        "recommendation_letters": 0.15,
    }

    # --- Normalize về [0, 1] dùng max của dataset ---
    df_max = {
        "publications": df["publications"].max() or 1,
        "citations": df["citations"].max() or 1,
        "degree_rank": 4,
        "recommendation_letters": df["recommendation_letters"].max() or 1,
    }

    profile_vec = np.array([
        pub_count / df_max["publications"],
        citation_count / df_max["citations"],
        degree_rank / df_max["degree_rank"],
        letter_count / df_max["recommendation_letters"],
    ])

    scores_list = []
    for _, row in df.iterrows():
        case_vec = np.array([
            row["publications"] / df_max["publications"],
            row["citations"] / df_max["citations"],
            row["degree_rank"] / df_max["degree_rank"],
            row["recommendation_letters"] / df_max["recommendation_letters"],
        ])
        weight_vec = np.array(list(WEIGHTS.values()))
        distance = np.sqrt(np.sum(weight_vec * (profile_vec - case_vec) ** 2))
        similarity = 1.0 / (1.0 + distance)   # chuyển distance → similarity
        scores_list.append((similarity, row))

    # Sort descending, lấy top_k
    scores_list.sort(key=lambda x: x[0], reverse=True)
    top = scores_list[:top_k]

    results = []
    for sim_score, row in top:
        breakdown = {
            "publications_profile": pub_count,
            "publications_case": int(row["publications"]),
            "citations_profile": citation_count,
            "citations_case": int(row["citations"]),
            "degree_rank_profile": degree_rank,
            "degree_rank_case": int(row["degree_rank"]),
        }
        results.append(SimilarCase(
            program=row["program"],
            field=str(row.get("field", "")),
            degree=str(row.get("degree", "")),
            current_role=str(row.get("current_role", "")),
            publications=int(row["publications"]),
            citations=int(row["citations"]),
            recommendation_letters=int(row["recommendation_letters"]),
            post_rfe=bool(row["post_rfe"]),
            approval_date=str(row.get("approval_date", "")),
            processing_days=float(row["processing_days"]) if pd.notna(row.get("processing_days")) else 0,
            premium_processing=str(row.get("premium_processing", "standard")),
            notable=str(row.get("notable", "")),
            source_url=str(row.get("source_url", "")),
            similarity_score=round(sim_score, 4),
            similarity_breakdown=breakdown,
        ))

    return results
```

---

### 14.5 Cập nhật Gap Analyzer — Nạp Similar Cases vào Prompt

Sửa `gap_analyzer.py` để nhận thêm `similar_cases` và đưa vào context của DeepSeek:

```python
async def generate_gap_analysis(
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    similar_cases: List[SimilarCase]    # ← THÊM tham số này
) -> str:
```

**Thêm đoạn này vào User Prompt (sau phần scoring):**

```python
SIMILAR_CASES_SECTION = """
## Hồ sơ tương tự đã được APPROVE (từ database thực tế):

{cases_text}

Dựa trên các case đã approve này, hãy:
1. Chỉ ra profile hiện tại đang ở mức nào so với các case đã pass
2. Cụ thể hóa khoảng cách (gap) bằng CON SỐ thực tế (ví dụ: "cần thêm X publications")
3. Nếu case tương tự bị RFE nhưng vẫn pass → cảnh báo rủi ro RFE
"""

def format_similar_cases(cases: List[SimilarCase]) -> str:
    lines = []
    for i, c in enumerate(cases, 1):
        rfe_note = " ⚠️ Bị RFE trước khi approve" if c.post_rfe else ""
        lines.append(
            f"Case #{i} ({c.program} - {c.field}):{rfe_note}\n"
            f"  - Bằng cấp: {c.degree} | Vai trò: {c.current_role}\n"
            f"  - Publications: {c.publications} | Citations: {c.citations}\n"
            f"  - Thư giới thiệu: {c.recommendation_letters}\n"
            f"  - Xử lý: {c.processing_days} ngày ({c.premium_processing})\n"
            f"  - Similarity score: {c.similarity_score:.2f}/1.0\n"
            f"  - Notable: {c.notable}\n"
            f"  - Nguồn: {c.source_url}"
        )
    return "\n\n".join(lines)
```

---

### 14.6 Cập nhật API Response Schema

Thêm `similar_cases` vào `CVAnalysisResponse`:

```python
class CVAnalysisResponse(BaseModel):
    profile: ImmigrationProfileSchema
    scores: USAScoreResult
    similar_cases_eb1a: List[SimilarCase]   # ← THÊM
    similar_cases_niw: List[SimilarCase]    # ← THÊM
    gap_report: str
    processing_time_seconds: float
```

---

### 14.7 Cập nhật API Endpoint (`api/routes/cv.py`)

Thêm vào Step 3 (sau scoring):

```python
from apps.cv_analyzer.case_matcher import find_similar_cases

# Step 3b: Tìm similar cases từ database thực tế
similar_eb1a = find_similar_cases(profile, scores, program="EB-1A", top_k=5)
similar_niw = find_similar_cases(profile, scores, program="EB-2 NIW", top_k=5)

# Step 4: Gap Analysis (DeepSeek) — truyền thêm similar cases
gap_report = await generate_gap_analysis(profile, scores, similar_eb1a + similar_niw)

return CVAnalysisResponse(
    profile=profile,
    scores=scores,
    similar_cases_eb1a=similar_eb1a,
    similar_cases_niw=similar_niw,
    gap_report=gap_report,
    processing_time_seconds=round(time.time() - start_time, 2)
)
```

---

### 14.8 Dependencies bổ sung

Thêm vào `requirements.txt`:

```txt
pandas>=2.0.0
numpy>=1.26.0
```

---

### 14.9 Ý nghĩa business của Similar Cases

Đây là **killer feature** phân biệt hệ thống này với các công cụ AI thông thường:

- **Thay vì nói chung chung:** "Bạn cần thêm publications"
- **Nói cụ thể bằng số thực:** "Các case EB-1A tương tự trong database đã pass với 10-21 publications. Bạn đang có X — cần thêm Y bài nữa để đạt ngưỡng an toàn"
- **Cảnh báo RFE có căn cứ:** "2/5 case tương tự nhất đã bị RFE về tiêu chí Critical Role — đây là rủi ro cao nhất cần chuẩn bị"
- **Benchmarking citations:** "Citation count của bạn (N) thấp hơn median của các approved case tương tự (M citations)"

**Thứ tự implement Section 14:**
1. Copy `cases.csv` vào `data/curated/`
2. `apps/cv_analyzer/case_loader.py`
3. `apps/cv_analyzer/case_matcher.py`
4. Cập nhật `schemas.py` — thêm `SimilarCase`, cập nhật `CVAnalysisResponse`
5. Cập nhật `gap_analyzer.py` — thêm tham số + format similar cases vào prompt
6. Cập nhật `api/routes/cv.py` — gọi `find_similar_cases` và truyền vào response

---

## 15. FRONTEND — CV UPLOAD BUTTON TRONG CHAT

### 15.1 UX Flow

```
User nhấn icon CV (màu tím) trong toolbar
    │
    ▼
File picker mở (chỉ accept .pdf)
    │
    ▼
Bubble file hiện trong chat (phía user)
    │
    ▼
Bot hiện progress card — 5 bước tick xanh dần:
  ① Parse PDF  ② Extract thông tin  ③ Tính điểm  ④ So sánh cases  ⑤ Gap Analysis
    │
    ▼
Bot hiện tin nhắn tóm tắt kết quả ngay trong chat
```

### 15.2 Cấu trúc file mới

```
apps/
└── [frontend-folder]/
    └── src/
        └── components/
            └── chat/
                ├── ChatInput.jsx          # ← SỬA: thêm CV upload button vào toolbar
                ├── CVUploadButton.jsx     # ← MỚI: button + hidden input
                ├── CVFileBubble.jsx       # ← MỚI: bubble hiển thị file đã upload
                ├── CVAnalyzingCard.jsx    # ← MỚI: progress card 5 bước
                └── CVResultBubble.jsx     # ← MỚI: tóm tắt kết quả trong chat
```

### 15.3 CVUploadButton Component

```jsx
// components/chat/CVUploadButton.jsx
import { useRef } from 'react';

export default function CVUploadButton({ onFileSelect }) {
  const inputRef = useRef(null);

  const handleChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate
    if (file.type !== 'application/pdf') {
      alert('Chỉ chấp nhận file PDF');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('File vượt quá 10MB');
      return;
    }

    onFileSelect(file);
    e.target.value = '';  // reset để có thể upload lại cùng file
  };

  return (
    <>
      <button
        className="tool-btn cv-btn"
        onClick={() => inputRef.current?.click()}
        title="Upload CV để phân tích EB-1A / EB-2 NIW"
        aria-label="Upload CV để phân tích"
        type="button"
      >
        {/* Icon: ID Badge — phân biệt rõ với paperclip thông thường */}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="5" width="20" height="16" rx="2"/>
          <path d="M8 5a4 4 0 0 1 8 0"/>
          <circle cx="12" cy="13" r="2"/>
          <path d="M8 19c0-2.2 1.8-4 4-4s4 1.8 4 4"/>
        </svg>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        onChange={handleChange}
        style={{ display: 'none' }}
      />
    </>
  );
}
```

**CSS cho button (thêm vào stylesheet hiện tại):**

```css
.tool-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: transparent;
  border: 0.5px solid var(--border-color, #e0e0e0);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: background 0.15s, color 0.15s;
}

/* CV button — màu tím để nổi bật */
.tool-btn.cv-btn {
  border-color: #AFA9EC;
  color: #534AB7;
  background: #EEEDFE;
}

.tool-btn.cv-btn:hover {
  background: #CECBF6;
}
```

### 15.4 CVFileBubble Component

Hiện phía bên phải (user side) ngay sau khi chọn file:

```jsx
// components/chat/CVFileBubble.jsx
export default function CVFileBubble({ file }) {
  const kb = file.size / 1024;
  const sizeStr = kb > 1024
    ? (kb / 1024).toFixed(1) + ' MB'
    : Math.round(kb) + ' KB';

  return (
    <div className="msg user">
      <div className="cv-file-bubble">
        <div className="cv-file-icon">
          {/* PDF icon màu cam */}
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke="#D85A30" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
            <line x1="9" y1="11" x2="11" y2="11"/>
          </svg>
        </div>
        <div className="cv-file-info">
          <span className="cv-file-name">{file.name}</span>
          <span className="cv-file-meta">{sizeStr} · PDF</span>
        </div>
      </div>
    </div>
  );
}
```

```css
.cv-file-bubble {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg-secondary, #f5f5f5);
  border: 0.5px solid var(--border-color, #e0e0e0);
  border-radius: 12px;
  padding: 10px 14px;
  max-width: 220px;
}

.cv-file-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #FAECE7;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cv-file-name {
  font-size: 13px;
  font-weight: 500;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.cv-file-meta {
  font-size: 11px;
  color: var(--text-secondary, #888);
  display: block;
}
```

### 15.5 CVAnalyzingCard Component

Hiện phía bot, xuất hiện ngay sau CVFileBubble, tự cập nhật từng bước:

```jsx
// components/chat/CVAnalyzingCard.jsx
import { useEffect, useState } from 'react';

const STEPS = [
  { id: 1, label: 'Đọc & parse PDF' },
  { id: 2, label: 'Trích xuất thông tin hồ sơ' },
  { id: 3, label: 'Tính điểm EB-1A / EB-2 NIW' },
  { id: 4, label: 'So sánh với approved cases' },
  { id: 5, label: 'Sinh báo cáo Gap Analysis' },
];

export default function CVAnalyzingCard({ currentStep }) {
  // currentStep: 1-5, do parent truyền vào dựa trên API response streaming
  // hoặc dùng polling interval nếu API không stream

  return (
    <div className="msg bot">
      <div className="cv-analyzing-card">
        <p className="analyzing-title">Đang phân tích hồ sơ...</p>
        {STEPS.map((step) => {
          const isDone = step.id < currentStep;
          const isActive = step.id === currentStep;
          return (
            <div
              key={step.id}
              className={`analyze-step ${isDone ? 'done' : isActive ? 'active' : 'pending'}`}
            >
              <div className="step-dot">
                {isDone && <CheckIcon />}
                {isActive && <SpinnerIcon />}
              </div>
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Nếu API không hỗ trợ streaming step — dùng timer để animate UI
export function CVAnalyzingCardAuto({ onDone }) {
  const [step, setStep] = useState(1);

  useEffect(() => {
    if (step > STEPS.length) { onDone?.(); return; }
    const t = setTimeout(() => setStep(s => s + 1), 800);
    return () => clearTimeout(t);
  }, [step]);

  return <CVAnalyzingCard currentStep={step} />;
}
```

```css
.cv-analyzing-card {
  background: var(--bg-secondary, #f5f5f5);
  border: 0.5px solid var(--border-color, #e0e0e0);
  border-radius: 12px;
  padding: 12px 16px;
  min-width: 240px;
}

.analyzing-title {
  font-size: 13px;
  font-weight: 500;
  margin: 0 0 10px;
}

.analyze-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  font-size: 12px;
  color: var(--text-secondary, #888);
}

.analyze-step.done { color: #0F6E56; }
.analyze-step.active { color: var(--text-primary, #111); font-weight: 500; }

.step-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 9px;
}

.analyze-step.done .step-dot { background: #E1F5EE; color: #0F6E56; }
.analyze-step.active .step-dot { background: #EEEDFE; }
.analyze-step.pending .step-dot { background: transparent; border: 0.5px solid var(--border-color, #e0e0e0); }

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.spinner { animation: spin 1s linear infinite; display: inline-block; }
```

### 15.6 CVResultBubble Component

Hiện sau khi API trả về, thay thế CVAnalyzingCard:

```jsx
// components/chat/CVResultBubble.jsx
export default function CVResultBubble({ data, onViewFullReport }) {
  const { scores } = data;

  return (
    <div className="msg bot">
      <div className="msg-bubble cv-result">
        <p className="result-headline">
          ✅ Phân tích hoàn tất trong {data.processing_time_seconds}s
        </p>

        <div className="result-scores">
          <div className="score-badge">
            <span className="score-label">EB-1A</span>
            <span className={`score-val ${scores.eb1a_eligible ? 'pass' : 'fail'}`}>
              {scores.eb1a_total_met}/10 tiêu chí
            </span>
            <span className={`score-tag ${scores.eb1a_eligible ? 'pass' : 'fail'}`}>
              {scores.eb1a_eligible ? 'Đủ điều kiện' : 'Chưa đủ'}
            </span>
          </div>
          <div className="score-badge">
            <span className="score-label">EB-2 NIW</span>
            <span className={`score-val ${scores.eb2niw_eligible ? 'pass' : 'fail'}`}>
              {scores.eb2niw_total_score}/9 điểm
            </span>
            <span className={`score-tag ${scores.eb2niw_eligible ? 'pass' : 'fail'}`}>
              {scores.eb2niw_eligible ? 'Đủ điều kiện' : 'Chưa đủ'}
            </span>
          </div>
        </div>

        <p className="result-recommend">
          🎯 Khuyến nghị: <strong>{scores.recommended_program}</strong>
        </p>

        <button className="view-report-btn" onClick={onViewFullReport}>
          Xem báo cáo đầy đủ →
        </button>
      </div>
    </div>
  );
}
```

```css
.cv-result { max-width: 85%; }

.result-headline {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 12px;
}

.result-scores {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.score-badge {
  flex: 1;
  background: var(--bg-primary, #fff);
  border: 0.5px solid var(--border-color, #e0e0e0);
  border-radius: 10px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.score-label { font-size: 11px; color: var(--text-secondary, #888); font-weight: 500; }
.score-val { font-size: 15px; font-weight: 500; }
.score-val.pass { color: #0F6E56; }
.score-val.fail { color: #993C1D; }

.score-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  width: fit-content;
}
.score-tag.pass { background: #E1F5EE; color: #0F6E56; }
.score-tag.fail { background: #FAECE7; color: #993C1D; }

.result-recommend { font-size: 13px; margin: 8px 0; }

.view-report-btn {
  font-size: 13px;
  color: #534AB7;
  background: #EEEDFE;
  border: none;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-weight: 500;
  margin-top: 4px;
}
.view-report-btn:hover { background: #CECBF6; }
```

### 15.7 Tích hợp vào ChatInput.jsx

Tìm component `ChatInput` hiện tại và sửa như sau:

```jsx
// Thêm import
import CVUploadButton from './CVUploadButton';

// Thêm handler trong ChatInput
const handleCVFile = async (file) => {
  // 1. Hiện file bubble trong chat
  addMessage({ type: 'cv-file', file });

  // 2. Hiện analyzing card
  addMessage({ type: 'cv-analyzing', id: 'analyzing-card' });

  // 3. Gọi API
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/cv/analyze', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) throw new Error(`API error: ${res.status}`);
    const data = await res.json();

    // 4. Xóa analyzing card, thêm result bubble
    removeMessage('analyzing-card');
    addMessage({ type: 'cv-result', data });

  } catch (err) {
    removeMessage('analyzing-card');
    addMessage({
      type: 'bot-text',
      text: '❌ Có lỗi khi phân tích CV. Vui lòng thử lại.',
    });
    console.error('CV analyze error:', err);
  }
};

// Thêm CVUploadButton vào toolbar (cạnh các button hiện có)
// Trong JSX của ChatInput:
<div className="toolbar">
  {/* ... các button cũ ... */}
  <CVUploadButton onFileSelect={handleCVFile} />
</div>
```

### 15.8 Render message types trong MessageList

Trong component render danh sách tin nhắn, thêm xử lý các type mới:

```jsx
// Trong MessageList.jsx hoặc ChatMessage.jsx
switch (message.type) {
  case 'cv-file':
    return <CVFileBubble key={message.id} file={message.file} />;

  case 'cv-analyzing':
    return (
      <CVAnalyzingCardAuto
        key={message.id}
        onDone={() => {/* no-op, API response sẽ xóa card */}}
      />
    );

  case 'cv-result':
    return (
      <CVResultBubble
        key={message.id}
        data={message.data}
        onViewFullReport={() => openFullReport(message.data.gap_report)}
      />
    );

  // ... các case cũ
}
```

### 15.9 Thứ tự implement Section 15

1. `CVUploadButton.jsx` — button + hidden input + validation
2. `CVFileBubble.jsx` — bubble hiển thị file
3. `CVAnalyzingCard.jsx` — progress card với animation
4. `CVResultBubble.jsx` — tóm tắt kết quả
5. Sửa `ChatInput.jsx` — thêm button vào toolbar + handler gọi API
6. Sửa `MessageList.jsx` — thêm render cho 3 type message mới
7. CSS — thêm vào stylesheet hiện tại (hoặc CSS module riêng)

### 15.10 Lưu ý kỹ thuật

**Timeout:** API phân tích CV mất 15-45 giây. Set `fetch` timeout 60s, hiện spinner suốt thời gian đó.

**File object không serialize được vào state thông thường:** Lưu `file.name` và `file.size` vào message state, không lưu `File` object. Truyền `File` object trực tiếp vào `handleCVFile` trước khi đưa vào state.

**CVAnalyzingCardAuto vs CVAnalyzingCard:** Dùng `CVAnalyzingCardAuto` (tự animate bằng timer) cho trường hợp API không có streaming. Nếu sau này muốn progress thật từ API, dùng `CVAnalyzingCard` với `currentStep` từ SSE/WebSocket.

**CORS:** Nếu frontend và API chạy port khác nhau trong dev, cần thêm CORS middleware vào FastAPI:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
```

---

## 16. LƯU TRỮ HỒ SƠ — GOOGLE DRIVE

### 16.1 Tổng quan

Mỗi lần user upload CV (PDF hoặc Word), hệ thống tự động lưu lên Google Drive theo cấu trúc thư mục có tổ chức. Lưu cả file gốc lẫn kết quả phân tích để consultant có thể tra cứu sau.

**Cấu trúc thư mục trên Drive:**

```
LNC_Global_CV_Storage/               ← folder gốc, tạo một lần
├── 2026-06/                         ← tháng upload (YYYY-MM)
│   ├── Nguyen_Van_A_20260618_143022/     ← {tên}_{date}_{time}
│   │   ├── CV_original.pdf              ← file gốc
│   │   ├── profile_extracted.json       ← ImmigrationProfileSchema
│   │   ├── scores.json                  ← USAScoreResult
│   │   └── gap_report.md                ← báo cáo Gap Analysis
│   └── Tran_Thi_B_20260618_160045/
│       └── ...
└── 2026-07/
    └── ...
```

**Luồng xử lý bổ sung:**

```
[Upload CV] → [Phân tích như cũ] → [Lưu Drive song song] → [Trả response + drive_url]
```

Lưu Drive chạy **sau khi phân tích xong**, không block response trả về client. Dùng `asyncio.create_task()` để fire-and-forget.

---

### 16.2 Setup Google Drive API

**Credentials:** Dùng Service Account (không cần OAuth flow — phù hợp cho server-side).

**Các bước thực hiện (một lần):**
1. Vào Google Cloud Console → tạo Service Account
2. Download file JSON credentials → đặt tại `credentials/google_service_account.json`
3. Share folder `LNC_Global_CV_Storage` với email của Service Account (Editor permission)
4. Lấy Folder ID từ URL Drive: `https://drive.google.com/drive/folders/{FOLDER_ID}`

**Thêm vào `.env`:**

```env
# Google Drive Storage
GOOGLE_SERVICE_ACCOUNT_PATH=credentials/google_service_account.json
GDRIVE_ROOT_FOLDER_ID=1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # ID của LNC_Global_CV_Storage
```

**Thêm vào `.gitignore`:**

```
credentials/
```

**Dependencies mới — thêm vào `requirements.txt`:**

```txt
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-auth-httplib2>=0.1.1
python-docx>=1.1.0    # đọc file .docx để convert sang text trước khi parse
```

---

### 16.3 Drive Client (`apps/cv_analyzer/drive_storage.py`)

```python
import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from io import BytesIO

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from functools import lru_cache

from apps.cv_analyzer.schemas import ImmigrationProfileSchema, USAScoreResult, SimilarCase

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']


@lru_cache(maxsize=1)
def get_drive_service():
    """Khởi tạo Drive API client một lần, cache lại."""
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/google_service_account.json")
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    """
    Tìm folder theo tên trong parent. Nếu chưa có thì tạo mới.
    Trả về folder_id.
    """
    query = (
        f"name='{name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])

    if files:
        return files[0]['id']

    # Tạo mới
    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = service.files().create(body=metadata, fields='id').execute()
    return folder['id']


def _upload_file(service, content: bytes, filename: str, mime_type: str, parent_id: str) -> str:
    """Upload bytes lên Drive. Trả về file_id."""
    metadata = {'name': filename, 'parents': [parent_id]}
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type)
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    return file.get('webViewLink', '')


def _make_folder_name(original_filename: str) -> str:
    """
    Tạo tên folder từ tên file + timestamp.
    Ví dụ: "Nguyen Van A CV.pdf" → "Nguyen_Van_A_20260618_143022"
    """
    stem = Path(original_filename).stem          # bỏ extension
    clean = stem.replace(' ', '_')[:40]          # giới hạn 40 ký tự
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{clean}_{ts}"


async def save_cv_to_drive(
    pdf_bytes: bytes,
    original_filename: str,
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    gap_report: str,
) -> str:
    """
    Lưu toàn bộ kết quả phân tích lên Google Drive.
    Trả về URL folder trên Drive (webViewLink).
    Chạy trong thread pool để không block event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _save_cv_sync,
        pdf_bytes, original_filename, profile, scores, gap_report
    )


def _save_cv_sync(
    pdf_bytes: bytes,
    original_filename: str,
    profile: ImmigrationProfileSchema,
    scores: USAScoreResult,
    gap_report: str,
) -> str:
    """Phần đồng bộ — chạy trong thread pool."""
    try:
        service = get_drive_service()
        root_id = os.getenv("GDRIVE_ROOT_FOLDER_ID")

        # 1. Folder tháng: "2026-06"
        month_folder = datetime.now().strftime('%Y-%m')
        month_id = _get_or_create_folder(service, month_folder, root_id)

        # 2. Folder case: "Nguyen_Van_A_20260618_143022"
        case_folder_name = _make_folder_name(original_filename)
        case_id = _get_or_create_folder(service, case_folder_name, month_id)

        # 3. Upload file gốc
        ext = Path(original_filename).suffix.lower()
        mime = 'application/pdf' if ext == '.pdf' else \
               'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        _upload_file(service, pdf_bytes, f"CV_original{ext}", mime, case_id)

        # 4. Upload profile JSON
        profile_json = profile.model_dump_json(indent=2).encode('utf-8')
        _upload_file(service, profile_json, "profile_extracted.json", "application/json", case_id)

        # 5. Upload scores JSON
        scores_json = scores.model_dump_json(indent=2).encode('utf-8')
        _upload_file(service, scores_json, "scores.json", "application/json", case_id)

        # 6. Upload gap report markdown
        gap_bytes = gap_report.encode('utf-8')
        _upload_file(service, gap_bytes, "gap_report.md", "text/markdown", case_id)

        # Lấy link folder case
        folder_meta = service.files().get(
            fileId=case_id, fields='webViewLink'
        ).execute()
        drive_url = folder_meta.get('webViewLink', '')

        logger.info(f"Saved CV to Drive: {case_folder_name} → {drive_url}")
        return drive_url

    except Exception as e:
        logger.error(f"Failed to save CV to Drive: {e}", exc_info=True)
        return ""   # Lỗi Drive không được làm crash response chính
```

---

### 16.4 Hỗ trợ file Word (.docx)

Parser hiện tại chỉ handle PDF. Thêm branch xử lý `.docx` trước khi đưa vào Marker/LlamaParse:

**Cập nhật `apps/cv_analyzer/parser.py`:**

```python
import docx as python_docx   # python-docx

def _docx_to_markdown(docx_bytes: bytes) -> str:
    """
    Convert .docx → markdown đơn giản.
    Giữ heading structure, paragraph, bullet list.
    Không cần layout parsing vì Word ít dùng multi-column.
    """
    from io import BytesIO
    doc = python_docx.Document(BytesIO(docx_bytes))
    lines = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append('')
            continue

        style = para.style.name.lower()
        if 'heading 1' in style:
            lines.append(f"# {text}")
        elif 'heading 2' in style:
            lines.append(f"## {text}")
        elif 'heading 3' in style:
            lines.append(f"### {text}")
        elif 'list' in style:
            lines.append(f"- {text}")
        else:
            lines.append(text)

    return '\n'.join(lines)


async def parse_cv_to_markdown(file_bytes: bytes, filename: str) -> str:
    """
    Entry point duy nhất — tự detect PDF vs Word.
    """
    ext = Path(filename).suffix.lower()

    if ext == '.docx':
        # Word: convert trực tiếp, không cần Marker
        loop = asyncio.get_event_loop()
        markdown = await loop.run_in_executor(None, _docx_to_markdown, file_bytes)
        logger.info(f"Parser used: python-docx for {filename}")
        return markdown

    elif ext == '.pdf':
        # PDF: Marker → LlamaParse fallback (logic cũ)
        return await parse_pdf_to_markdown(file_bytes, filename)

    else:
        raise ValueError(f"Unsupported file type: {ext}. Chỉ chấp nhận PDF hoặc DOCX.")
```

---

### 16.5 Cập nhật API Endpoint (`api/routes/cv.py`)

Thêm:
- Chấp nhận cả `.pdf` và `.docx`
- Gọi `save_cv_to_drive` sau khi phân tích xong (fire-and-forget)
- Trả `drive_folder_url` trong response

```python
from apps.cv_analyzer.drive_storage import save_cv_to_drive
from apps.cv_analyzer.parser import parse_cv_to_markdown   # ← đổi từ parse_pdf_to_markdown

ALLOWED_TYPES = {
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/msword': '.doc',   # .doc cũ — từ chối, yêu cầu convert sang docx
}

@router.post("/analyze", response_model=CVAnalysisResponse)
async def analyze_cv(file: UploadFile = File(...)):
    # Validation mở rộng
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Chỉ chấp nhận PDF hoặc Word (.docx)")
    if file.content_type == 'application/msword':
        raise HTTPException(400, "Vui lòng convert sang .docx trước khi upload")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File vượt quá 10MB")

    start_time = time.time()

    # Step 1: Parse (PDF hoặc DOCX)
    markdown = await parse_cv_to_markdown(pdf_bytes, file.filename)

    # Step 2-4: Giữ nguyên như cũ
    profile = await extract_profile(markdown)
    exp_months = calculate_experience_months(profile.work_history)
    eb1a_result = check_eb1a_criteria(profile)
    eb2niw_result = score_eb2niw(profile, exp_months)
    scores = USAScoreResult(...)
    similar_eb1a = find_similar_cases(profile, scores, "EB-1A", top_k=5)
    similar_niw = find_similar_cases(profile, scores, "EB-2 NIW", top_k=5)
    gap_report = await generate_gap_analysis(profile, scores, similar_eb1a + similar_niw)

    # Step 5: Lưu Drive — fire and forget, không await
    asyncio.create_task(
        save_cv_to_drive(
            pdf_bytes=pdf_bytes,
            original_filename=file.filename,
            profile=profile,
            scores=scores,
            gap_report=gap_report,
        )
    )

    return CVAnalysisResponse(
        profile=profile,
        scores=scores,
        similar_cases_eb1a=similar_eb1a,
        similar_cases_niw=similar_niw,
        gap_report=gap_report,
        drive_folder_url="",           # sẽ được điền async, client không chờ
        processing_time_seconds=round(time.time() - start_time, 2)
    )
```

> **Lý do không await Drive:** Lưu Drive mất 3-8 giây do upload nhiều file. Client không cần URL Drive ngay — response trả về trước, Drive upload chạy ngầm. Nếu sau này cần URL Drive trong response thì đổi thành `await`.

---

### 16.6 Cập nhật Schema

Thêm `drive_folder_url` vào `CVAnalysisResponse`:

```python
class CVAnalysisResponse(BaseModel):
    profile: ImmigrationProfileSchema
    scores: USAScoreResult
    similar_cases_eb1a: List[SimilarCase]
    similar_cases_niw: List[SimilarCase]
    gap_report: str
    drive_folder_url: str = ""         # ← THÊM, empty nếu Drive chưa xong
    processing_time_seconds: float
```

---

### 16.7 Cập nhật Frontend — Accept .docx

Sửa `CVUploadButton.jsx`, đổi `accept`:

```jsx
// Trước
<input type="file" accept=".pdf" ... />

// Sau
<input type="file" accept=".pdf,.docx" ... />
```

Sửa validation trong `handleChange`:

```jsx
const ALLOWED_TYPES = ['application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];

const handleChange = (e) => {
  const file = e.target.files[0];
  if (!file) return;

  if (!ALLOWED_TYPES.includes(file.type)) {
    alert('Chỉ chấp nhận PDF hoặc Word (.docx)');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    alert('File vượt quá 10MB');
    return;
  }
  onFileSelect(file);
  e.target.value = '';
};
```

Sửa icon trong `CVFileBubble.jsx` để hiển thị đúng theo loại file:

```jsx
const isWord = file.name.endsWith('.docx');

// Icon Word màu xanh, PDF màu cam
{isWord ? (
  <svg ... stroke="#185FA5"> {/* Word icon */} </svg>
) : (
  <svg ... stroke="#D85A30"> {/* PDF icon */} </svg>
)}

// Meta text
<span className="cv-file-meta">
  {sizeStr} · {isWord ? 'Word' : 'PDF'}
</span>
```

---

### 16.8 Thứ tự implement Section 16

1. Tạo Service Account trên Google Cloud, download JSON credentials
2. Share folder Drive với email Service Account
3. Thêm `GOOGLE_SERVICE_ACCOUNT_PATH` và `GDRIVE_ROOT_FOLDER_ID` vào `.env`
4. Thêm `credentials/` vào `.gitignore`
5. `apps/cv_analyzer/drive_storage.py` — Drive client + upload logic
6. Cập nhật `apps/cv_analyzer/parser.py` — thêm `_docx_to_markdown` + `parse_cv_to_markdown`
7. Cập nhật `apps/cv_analyzer/schemas.py` — thêm `drive_folder_url`
8. Cập nhật `api/routes/cv.py` — accept docx + fire-and-forget Drive upload
9. Cập nhật `CVUploadButton.jsx` — accept `.docx`
10. Cập nhật `CVFileBubble.jsx` — icon Word vs PDF

### 16.9 Lưu ý

**Service Account vs OAuth:** Service Account không cần user login, phù hợp chạy server-side tự động. Nhược điểm: phải share folder thủ công với email service account.

**`credentials/` không được commit:** File JSON Service Account chứa private key — tuyệt đối không push lên GitHub. Kiểm tra `.gitignore` trước khi commit.

**Drive quota:** Google Drive miễn phí 15GB. Với CV trung bình 500KB + JSON ~50KB, lưu được ~25,000 hồ sơ trước khi cần nâng cấp.

**Retry khi Drive lỗi:** `save_cv_to_drive` đã có try/except — lỗi chỉ log, không crash API. Nếu cần đảm bảo không mất data, sau này thêm queue (Redis/Celery) để retry.
