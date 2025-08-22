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

# LangChain
try:  # optional dependency
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore

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
    return bool(os.getenv("OPENAI_API_KEY"))


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    # Prefer LangChain ChatOpenAI if available
    if _llm_available() and ChatOpenAI is not None and ChatPromptTemplate is not None:
        try:
            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.4)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{user_prompt}"),
            ])
            chain = prompt | llm
            out = chain.invoke({"user_prompt": user_prompt})
            return out.content if hasattr(out, "content") else str(out)
        except Exception:
            pass
    # Fallback to OpenAI client
    if _llm_available() and OpenAI is not None:
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
    return ""


def generate_workout(user: User, today_weekday: int, memory_context: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = "\n".join([m.get("text", "") for m in memory_context])
    system = "Ты профессиональный тренер. Формируй структурированный JSON с тренировкой."
    prompt = f"Пользователь: goal={user.goal}, level={user.level}, equipment={user.equipment}, sessions={user.sessions_per_week}. День недели={today_weekday}. Контекст: {ctx}. Верни JSON с полями: name, exercises(list of {{name, sets, reps, rest_s, technique}})."
    import json
    result = _call_llm(system, prompt)
    if result:
        try:
            return json.loads(result)
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
    prompt = f"Пользователь: goal={user.goal}, diet={user.diet_pref}, calories={calories}. Контекст: {ctx}. Верни JSON: meals(list of {{name, items, calories}})."
    import json
    result = _call_llm(system, prompt)
    if result:
        try:
            return json.loads(result)
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
    result = _call_llm(system, prompt)
    if result:
        return result.strip()
    return "Ты справишься! Маленькие шаги каждый день приводят к большим результатам."


def generate_analysis(user: User, memory_context: List[Dict[str, Any]], recent_weights: List[float] | None = None) -> str:
    ctx = "\n".join([m.get("text", "") for m in memory_context])
    trend = "нет данных"
    if recent_weights and len(recent_weights) >= 2:
        diff = recent_weights[-1] - recent_weights[0]
        trend = f"{diff:+.1f} кг за период"
    system = (
        "Ты фитнес-аналитик. Проанализируй прогресс кратко, предложи корректировки по питанию и тренировкам."
        " Пиши по делу, 3-5 пунктов."
    )
    prompt = (
        f"Цель={user.goal}, уровень={user.level}, диета={user.diet_pref}, оборудование={user.equipment}, сессий/нед={user.sessions_per_week}.\n"
        f"Контекст: {ctx}.\nТренд веса: {trend}. Дай рекомендации."
    )
    result = _call_llm(system, prompt)
    return result.strip() if result else (
        f"Прогресс: {trend}. Рекомендации: увеличить NEAT, держать белок 1.6-2.2 г/кг, сон 7-9 ч, техника и прогрессия нагрузок."
    )