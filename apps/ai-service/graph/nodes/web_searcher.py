from tavily import TavilyClient
from graph.state import ChatState
from config import settings

# Keywords that indicate user needs real-time / latest data
_WEB_TRIGGERS = [
    # Vietnamese
    "mới nhất", "hiện tại", "tuần này", "tháng này", "năm nay", "gần đây",
    "vừa", "mới ra", "cập nhật", "thời gian xử lý", "điểm cắt", "điểm cut",
    "vòng mời", "draw gần", "draw mới", "ngưỡng crs", "cut-off", "cutoff",
    "quota còn", "chỉ tiêu", "bao lâu", "processing",
    # English
    "latest", "current", "today", "this week", "this month", "this year",
    "recent", "draw", "processing time", "wait time", "how long",
]

_COUNTRY_DOMAINS = {
    "canada": [
        "canada.ca", "ircc.canada.ca", "cic.gc.ca",
        "moving2canada.com", "canadavisa.com",
    ],
    "usa": [
        "uscis.gov", "travel.state.gov", "dhs.gov",
        "visabulletin.com",
    ],
    "newzealand": [
        "immigration.govt.nz", "mbie.govt.nz",
    ],
}


def _needs_web_search(query: str) -> bool:
    ql = query.lower()
    return any(kw in ql for kw in _WEB_TRIGGERS)


def _build_search_query(state: ChatState) -> str:
    """Compose an effective English search query from state."""
    country = state.get("country")
    category = state.get("category")
    query = state["query"]

    suffix_map = {
        "canada": "Canada immigration IRCC",
        "usa": "USA immigration USCIS",
        "newzealand": "New Zealand immigration INZ",
    }
    suffix = suffix_map.get(country or "", "immigration")

    if category:
        return f"{category} {query} {suffix}"
    return f"{query} {suffix}"


def web_search(state: ChatState) -> dict:
    """Call Tavily only when query contains real-time signal keywords."""
    if not settings.tavily_api_key:
        return {"web_chunks": []}

    if not _needs_web_search(state["query"]):
        return {"web_chunks": []}

    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        country = state.get("country")
        include_domains = _COUNTRY_DOMAINS.get(country or "", [])

        response = client.search(
            query=_build_search_query(state),
            search_depth="advanced",
            max_results=4,
            include_domains=include_domains or None,
        )

        chunks = []
        for r in response.get("results", []):
            url = r.get("url", "")
            content = r.get("content", "").strip()
            title = r.get("title", "").strip()
            if not content or not title:
                continue
            chunks.append({
                "chunk_id": f"web_{abs(hash(url)) % 10**9}",
                "title": title,
                "content": content,
                "source_url": url,
                "category": state.get("category") or "",
                "country": state.get("country") or "",
                "trust_score": 0.85,
                "score": 0.80,
                "is_web": True,
            })
        return {"web_chunks": chunks}

    except Exception:
        return {"web_chunks": []}
