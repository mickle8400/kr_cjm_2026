"""
Pydantic-схемы для запросов и ответов API.
Используются и для валидации входных данных, и для Structured Outputs от OpenAI.
"""

from pydantic import BaseModel, Field
from typing import List


# ─── Входные данные ────────────────────────────────────────────────────────────

class StrategiesRequest(BaseModel):
    """Запрос на генерацию стратегий."""

    situation_type: str = Field(
        ...,
        description="Тип бизнес-ситуации",
        examples=["Цифровая трансформация", "Операционный кризис"],
    )
    situation_description: str = Field(
        ...,
        min_length=20,
        description="Подробное описание ситуации клиента",
        examples=["Крупный клиент, формировавший 60% выручки, ушёл к конкурентам..."],
    )
    strategies_count: int = Field(
        default=3,
        ge=2,
        le=6,
        description="Сколько стратегий сгенерировать (2–6)",
    )
    model: str = Field(
        default="gpt-5-nano",
        description="OpenAI-модель для генерации",
    )


class StepsRequest(BaseModel):
    """Запрос на генерацию шагов по выбранной стратегии."""

    # Контекст ситуации (передаётся повторно для независимости вызова)
    situation_type: str = Field(..., description="Тип ситуации (из первого запроса)")
    situation_description: str = Field(..., description="Описание ситуации (из первого запроса)")

    # Выбранная стратегия
    strategy_title: str = Field(..., description="Название выбранной стратегии")
    strategy_goal: str = Field(..., description="Цель выбранной стратегии")
    strategy_description: str = Field(..., description="Описание выбранной стратегии")

    model: str = Field(default="gpt-5-nano", description="OpenAI-модель")


# ─── Structured Output-схемы (то, что возвращает LLM) ─────────────────────────

class Strategy(BaseModel):
    """Одна стратегия решения ситуации."""

    title: str = Field(..., description="Краткое название стратегии (5–10 слов)")
    goal: str = Field(..., description="Конкретная измеримая цель стратегии")
    description: str = Field(..., description="Развёрнутое описание логики и механики стратегии")
    applicability: str = Field(..., description="Когда эта стратегия применима")
    non_applicability: str = Field(..., description="Когда эта стратегия НЕ подходит")


class StrategiesResponse(BaseModel):
    """Ответ на запрос генерации стратегий."""

    strategies: List[Strategy] = Field(
        ...,
        description="Список предложенных стратегий",
        min_length=2,
    )
    situation_summary: str = Field(
        ...,
        description="Краткий аналитический разбор ситуации (2–3 предложения)",
    )


class Step(BaseModel):
    """Один конкретный шаг реализации стратегии."""

    title: str = Field(..., description="Краткое название шага")
    description: str = Field(..., description="Детальное описание: что делать и как")
    verification_criteria: str = Field(
        ..., description="Критерий проверки: как понять, что шаг выполнен"
    )
    responsible: str = Field(
        ..., description="Кто отвечает за шаг (роль или функция, например 'Директор по IT')"
    )
    duration: str = Field(
        ..., description="Примерная длительность (например, '2 недели', '1 месяц')"
    )


class StepsResponse(BaseModel):
    """Ответ на запрос генерации шагов."""

    steps: List[Step] = Field(..., description="Шаги реализации стратегии", min_length=3)
    expected_result: str = Field(
        ..., description="Ожидаемый результат после выполнения всех шагов"
    )
    key_risks: List[str] = Field(
        ...,
        description="Ключевые риски реализации (3–5 пунктов)",
        min_length=2,
    )
