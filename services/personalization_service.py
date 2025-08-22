from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select

from database import get_sessionmaker, User
from ai_agents import query_memory, _llm_available  # type: ignore

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore
    ChatPromptTemplate = None  # type: ignore


class ContentPersonalizer:
    def __init__(self, temperature: float = 0.8, model: str | None = None) -> None:
        self.temperature = temperature
        self.model = model or "gpt-4o-mini"

    async def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        Session = get_sessionmaker()
        async with Session() as session:
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalar_one_or_none()
            if not user:
                return {}
            return {
                "goal": user.goal,
                "level": user.level,
                "age": user.age,
                "height_cm": user.height_cm,
                "weight_kg": user.weight_kg,
                "sex": user.sex,
                "diet_pref": user.diet_pref,
                "equipment": user.equipment,
                "sessions_per_week": user.sessions_per_week,
            }

    async def get_user_memory(self, user_id: int) -> str:
        # Query vector memory; join texts
        results = query_memory(user_id, "предпочтения цели прогресс", n=8) or []
        return "\n".join([r.get("text", "") for r in results if r.get("text")])

    async def personalize_content(self, user_id: int, content_type: str) -> str:
        """Персонализация контента на основе предпочтений пользователя"""
        profile = await self.get_user_profile(user_id)
        memory_text = await self.get_user_memory(user_id)

        system = "Ты помощник по фитнесу и питанию. Кратко и по делу, с персонализацией."
        user_prompt = (
            f"Персонализируй {content_type} для пользователя.\n"
            f"Профиль:\n{profile}\n\nИстория и предпочтения:\n{memory_text}\n"
        )

        if _llm_available() and ChatOpenAI is not None and ChatPromptTemplate is not None:
            llm = ChatOpenAI(model=self.model, temperature=self.temperature)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system),
                ("user", "{input}")
            ])
            chain = prompt | llm
            out = await chain.ainvoke({"input": user_prompt})
            return getattr(out, "content", str(out))

        # Fallback to OpenAI HTTP client via ai_agents._call_llm (sync), run in thread
        from ai_agents import _call_llm  # type: ignore
        import asyncio
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _call_llm, system, user_prompt)
        return text or ""