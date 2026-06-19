"""Extract structured entities (country, category, topic) from a user query via DeepSeek."""
from __future__ import annotations
import json
import os
import random
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_SYSTEM_PROMPT = """\
You are an immigration query parser. Extract structured entities from the user question.
Return ONLY valid JSON with these exact fields (use null if unknown):
{
  "country": "usa" | "canada" | "newzealand" | null,
  "category": one of [EB1-A, EB1-B, EB1-C, EB2-NIW, L1-Visa, Express-Entry, PNP, TFWP, LMIA, skilled_migrant, work_visa] or null,
  "topic": short topic phrase in English (3-5 words)
}"""


def _pick_deepseek_key() -> str:
    keys_str = os.environ.get("DEEPSEEK_API_KEYS", "")
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    if not keys:
        keys = [os.environ["DEEPSEEK_API_KEY"]]
    return random.choice(keys)


class EntityExtractor:
    def __init__(self) -> None:
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    def extract(self, query: str) -> dict:
        client = OpenAI(api_key=_pick_deepseek_key(), base_url=self.base_url)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=128,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip("` \n")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"country": None, "category": None, "topic": query[:60]}
