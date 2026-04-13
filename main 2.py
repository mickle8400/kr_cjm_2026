"""
Solution Builder API
FastAPI + OpenAI Structured Outputs

Два эндпоинта:
  POST /strategies  — генерация стратегий по описанию ситуации
  POST /steps       — генерация шагов по выбранной стратегии

Контекст ситуации передаётся в каждый вызов явно, что делает
оба вызова независимыми и идемпотентными.
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from schemas import (
    StrategiesRequest,
    StrategiesResponse,
    StepsRequest,
    StepsResponse,
)

# ── Конфигурация ───────────────────────────────────────────────────────────────
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Переменная окружения OPENAI_API_KEY не задана")

client = OpenAI(api_key=OPENAI_API_KEY)

# ── Приложение ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Solution Builder API",
    description="""
## Генератор комплексных бизнес-решений

Два последовательных вызова:

1. **POST /strategies** — описываете ситуацию клиента → получаете список стратегий
2. **POST /steps** — выбираете стратегию → получаете детальный план шагов

Выходные данные всегда структурированы (JSON Schema через OpenAI Structured Outputs).
    """,
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Системные промпты ──────────────────────────────────────────────────────────

STRATEGIES_SYSTEM = """Ты — старший бизнес-консультант с 20-летним опытом работы \
с корпоративными клиентами (B2B, промышленность, торговля, услуги).

Твоя задача — проанализировать описанную ситуацию и предложить стратегии её решения.

Правила:
- Каждая стратегия должна отличаться по механике и логике (не просто по формулировке)
- Цель должна быть конкретной и измеримой (например: "снизить зависимость от одного \
клиента до 20% выручки за 6 месяцев")
- Критерии применимости и неприменимости должны содержать проверяемые условия
- Отвечай только на русском языке
"""

STEPS_SYSTEM = """Ты — операционный консультант, специализирующийся на реализации \
бизнес-стратегий в корпоративном секторе.

Твоя задача — разработать детальный пошаговый план реализации выбранной стратегии.

Правила:
- Каждый шаг должен быть конкретным и проверяемым (не "улучшить продажи", \
а "провести переговоры с 5 новыми потенциальными клиентами до 1 марта")
- Шаги должны идти в логической последовательности
- Для каждого шага укажи ответственного (роль, не конкретное имя) и длительность
- Ключевые риски должны быть специфичны для данной стратегии и ситуации
- Отвечай только на русском языке
- Подб
"""


# ── Вспомогательная функция вызова OpenAI ─────────────────────────────────────

def call_openai_structured(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_schema: type,
):
    """
    Вызывает OpenAI с Structured Outputs.
    response_schema — Pydantic-модель, определяющая структуру ответа.
    Возвращает распарсенный объект нужного типа.
    """
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_schema,
            # temperature=0.7,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("OpenAI вернул пустой ответ (refusal или ошибка парсинга)")
        return parsed

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка OpenAI API: {exc}") from exc


# ── Эндпоинт 1: Генерация стратегий ───────────────────────────────────────────

@app.post(
    "/strategies",
    response_model=StrategiesResponse,
    summary="Сгенерировать стратегии по ситуации клиента",
    response_description="Список стратегий и краткий анализ ситуации",
)
def generate_strategies(body: StrategiesRequest) -> StrategiesResponse:
    """
    **Вызов 1 из 2.**

    Принимает описание ситуации клиента и возвращает:
    - `situation_summary` — краткий аналитический разбор
    - `strategies[]` — список стратегий, каждая с названием, целью, описанием,
      критериями применимости и неприменимости

    Полученный список стратегий показывается пользователю для выбора.
    Затем передайте выбранную стратегию в **/steps**.
    """
    user_prompt = f"""Проанализируй ситуацию и предложи {body.strategies_count} стратегии решения.

=== СИТУАЦИЯ КЛИЕНТА ===
Тип: {body.situation_type}
Описание: {body.situation_description}

Стратегии должны принципиально отличаться по механике (например: диверсификация, \
выход в новый канал, трансформация бизнес-модели — а не три вариации одного подхода).
"""

    return call_openai_structured(
        model=body.model,
        system_prompt=STRATEGIES_SYSTEM,
        user_prompt=user_prompt,
        response_schema=StrategiesResponse,
    )


# ── Эндпоинт 2: Генерация шагов ───────────────────────────────────────────────

@app.post(
    "/steps",
    response_model=StepsResponse,
    summary="Сгенерировать шаги для выбранной стратегии",
    response_description="Пошаговый план реализации с рисками и ожидаемым результатом",
)
def generate_steps(body: StepsRequest) -> StepsResponse:
    """
    **Вызов 2 из 2.**

    Принимает контекст ситуации (из первого вызова) + выбранную стратегию.
    Возвращает:
    - `steps[]` — детальные шаги с описанием, критерием проверки, ответственным и длительностью
    - `expected_result` — итоговый результат после выполнения всех шагов
    - `key_risks[]` — ключевые риски реализации

    **Контекст ситуации передаётся повторно** — это делает вызов независимым
    и позволяет использовать его без сохранения состояния на сервере.
    """
    user_prompt = f"""Разработай детальный пошаговый план реализации стратегии.

=== СИТУАЦИЯ КЛИЕНТА (контекст) ===
Тип: {body.situation_type}
Описание: {body.situation_description}

=== ВЫБРАННАЯ СТРАТЕГИЯ ===
Название: {body.strategy_title}
Цель: {body.strategy_goal}
Описание: {body.strategy_description}

Шаги должны быть выполнимы в условиях реального корпоративного бизнеса. \
Учитывай контекст ситуации при определении приоритетов и рисков.
"""

    return call_openai_structured(
        model=body.model,
        system_prompt=STEPS_SYSTEM,
        user_prompt=user_prompt,
        response_schema=StepsResponse,
    )


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
