from __future__ import annotations

import os
from typing import Any, Dict, List
from datetime import datetime

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

from database import get_sessionmaker, User


CHROMA_DIR = os.path.join(os.getcwd(), "data", "chroma")

_client = None
_embedding_fn = None


def get_memory_client() -> chromadb.Client:
    global _client, _embedding_fn
    os.makedirs(CHROMA_DIR, exist_ok=True)
    if _client is None:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            _embedding_fn = OpenAIEmbeddingFunction(api_key=openai_api_key, model_name="text-embedding-3-small")
        _client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=CHROMA_DIR))
    return _client


def _collection_name_for_user(user_id: int) -> str:
    return f"user_{user_id}_memory"


def add_memory(user_id: int, texts: List[str], metadatas: List[Dict[str, Any]] | None = None) -> None:
    client = get_memory_client()
    name = _collection_name_for_user(user_id)
    col = client.get_or_create_collection(name=name, embedding_function=_embedding_fn)
    ids = [f"{user_id}-{datetime.utcnow().timestamp()}-{i}" for i in range(len(texts))]
    col.add(ids=ids, documents=texts, metadatas=metadatas)


def query_memory(user_id: int, query: str, n: int = 5) -> List[Dict[str, Any]]:
    client = get_memory_client()
    name = _collection_name_for_user(user_id)
    try:
        col = client.get_or_create_collection(name=name, embedding_function=_embedding_fn)
        res = col.query(query_texts=[query], n_results=n)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        return [{"text": d, "meta": m} for d, m in zip(docs, metas)]
    except Exception:
        return []


def _llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    if not _llm_available():
        return ""
    client = OpenAI()
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content or ""


def generate_workout(user: User, today_weekday: int, memory_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = "\n".join([m.get("text", "") for m in memory_context])
    system = "Ты профессиональный тренер. Формируй структурированный JSON с тренировкой."
    prompt = f"Пользователь: goal={user.goal}, level={user.level}, equipment={user.equipment}, sessions={user.sessions_per_week}. День недели={today_weekday}. Контекст: {ctx}. Верни JSON с полями: name, exercises(list of {name, sets, reps, rest_s, technique})."
    if _llm_available():
        try:
            text = _call_llm(system, prompt)
            import json
            return json.loads(text)
        except Exception:
            pass
    # Fallback rule-based
    plan = {
        "name": "Силовая тренировка всего тела",
        "exercises": [
            {"name": "Приседания", "sets": 4, "reps": 8, "rest_s": 90, "technique": "Спина нейтральна, колени по линии носков."},
            {"name": "Жим гантелей лёжа", "sets": 4, "reps": 10, "rest_s": 90, "technique": "Лопатки сведены, контролируй траекторию."},
            {"name": "Тяга в наклоне", "sets": 4, "reps": 10, "rest_s": 90, "technique": "Корпус стабилен, тяга к поясу."},
            {"name": "Планка", "sets": 3, "reps": 45, "rest_s": 60, "technique": "Корпус прямой, пресс напряжён."},
        ],
    }
    return plan


def generate_meal_plan(user: User, calories: int, memory_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = "\n".join([m.get("text", "") for m in memory_context])
    system = "Ты нутрициолог. Верни JSON с приёмами пищи на день под ограничения."
    prompt = f"Пользователь: goal={user.goal}, diet={user.diet_pref}, calories={calories}. Контекст: {ctx}. Верни JSON: meals(list of {name, items, calories})."
    if _llm_available():
        try:
            text = _call_llm(system, prompt)
            import json
            return json.loads(text)
        except Exception:
            pass
    return {
        "meals": [
            {"name": "Завтрак", "items": ["Овсянка на воде", "Ягоды", "Орехи"], "calories": int(calories * 0.25)},
            {"name": "Обед", "items": ["Куриная грудка", "Киноа", "Салат"], "calories": int(calories * 0.35)},
            {"name": "Ужин", "items": ["Лосось", "Овощи на пару"], "calories": int(calories * 0.30)},
            {"name": "Перекус", "items": ["Греческий йогурт"], "calories": calories - int(calories * 0.25) - int(calories * 0.35) - int(calories * 0.30)},
        ]
    }


def generate_motivation(user: User, memory_context: List[Dict[str, Any]]) -> str:
    ctx = "\n".join([m.get("text", "") for m in memory_context])
    system = "Ты мотивационный коуч. Кратко, позитивно, конкретно."
    prompt = f"Цель: {user.goal}, уровень: {user.level}. Контекст: {ctx}. Сообщение 1-2 предложения."
    if _llm_available():
        try:
            text = _call_llm(system, prompt)
            return text.strip()
        except Exception:
            pass
    return "Ты справишься! Маленькие шаги каждый день приводят к большим результатам."