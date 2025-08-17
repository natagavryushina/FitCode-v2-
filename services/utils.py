from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def compute_uniqueness_hash(text: str) -> str:
	data = text.strip().lower()
	return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def extract_json_block(text: str) -> Dict[str, Any] | None:
	start = text.find("{")
	end = text.rfind("}")
	if start != -1 and end != -1 and end > start:
		candidate = text[start : end + 1]
		try:
			return json.loads(candidate)
		except Exception:
			return None
	return None