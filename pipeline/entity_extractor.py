"""Extract structured entities (country, category, topic) from a user query via Groq."""
from __future__ import annotations
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_SYSTEM_PROMPT = """\
You are an immigration query parser. Extract structured entities from the user question.
Return ONLY valid JSON with these exact fields (use null if unknown):
{
  "country": "usa" | "canada" | "newzealand" | null,
  "category": one of [EB1-A, EB1-B, EB1-C, EB2-NIW, L1-Visa, Express-Entry, PNP, TFWP, LMIA, skilled_migrant, work_visa] or null,
  "topic": short topic phrase in English (3-5 words)
}"""


class EntityExtractor:
    def __init__(self) -> None:
        self.client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = os.environ.get("GROQ_MODEL", "llama3-70b-8192")

    def extract(self, query: str) -> dict:
        resp = self.client.chat.completions.create(
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
