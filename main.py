from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
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


def generate_strategies(situation_type, description) -> StrategiesResponse:
    """
    **Вызов 1 из 2.**

    Принимает описание ситуации клиента и возвращает:
    - `situation_summary` — краткий аналитический разбор
    - `strategies[]` — список стратегий, каждая с названием, целью, описанием,
      критериями применимости и неприменимости

    Полученный список стратегий показывается пользователю для выбора.
    Затем передайте выбранную стратегию в **/steps**.
    """
    user_prompt = f"""Проанализируй ситуацию и предложи {3} стратегии решения.

=== СИТУАЦИЯ КЛИЕНТА ===
Тип: {situation_type}
Описание: {description}

Стратегии должны принципиально отличаться по механике (например: диверсификация, \
выход в новый канал, трансформация бизнес-модели — а не три вариации одного подхода).
"""

    return call_openai_structured(
        model="gpt-5-nano",
        system_prompt=STRATEGIES_SYSTEM,
        user_prompt=user_prompt,
        response_schema=StrategiesResponse,
    )


import re
import json

def parse_strategy(text):
    # Убираем номера (1. 2. 3. ...)
    text = re.sub(r"\d+\.\s*", "", text)

    # Шаблон для поиска блоков
    pattern = r"(TITLE|GOAL|DESCRIPTION|APPLICABILITY|NON_APPLICABILITY):\s*(.*?)(?=\n[A-Z_]+:|$)"

    matches = re.findall(pattern, text, re.DOTALL)

    data = {}

    for key, value in matches:
        data[key.lower()] = value.strip().replace("\n", " ")

    return data


def generate_steps(situation_type, situation_description, text) -> StepsResponse:
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

    data = parse_strategy(text)


    user_prompt = f"""Разработай детальный пошаговый план реализации стратегии.

=== СИТУАЦИЯ КЛИЕНТА (контекст) ===
Тип: {situation_type}
Описание: {situation_description}

=== ВЫБРАННАЯ СТРАТЕГИЯ ===
Название: {data['title']}
Цель: {data['goal']}
Описание: {data['description']}

Шаги должны быть выполнимы в условиях реального корпоративного бизнеса. \
Учитывай контекст ситуации при определении приоритетов и рисков.
"""
    return call_openai_structured(
        model="gpt-5-nano",
        system_prompt=STEPS_SYSTEM,
        user_prompt=user_prompt,
        response_schema=StepsResponse,
    )


text = """
1. TITLE:
Продуктовая цифровая платформа и сервисы (As-a-Service)
GOAL:
За 12 месяцев запустить 2 новых цифровых сервиса (predictive maintenance и цифровой двойник); к концу 24 месяцев доля сервисной выручки достигнет 25% от общего оборота; незапланированные простои снизятся на 15% в течение 12–18 месяцев
2. DESCRIPTION:
Разделение бизнес-модели: создание цифровой платформы для мониторинга и обслуживания оборудования, подписочные услуги, внедрение цифрового двойника; формирование команды сервисного бизнеса, пилоты на 2–3 объектах; инфраструктура IoT/edge, data lake, аналитика в реальном времени
3. APPLICABILITY:
Наличие датчиков и телеметрии, готовность продавать сервисы по подписке, поддержка руководства и выделенный бюджет на развитие сервисной модели
4. NON_APPLICABILITY:
Невозможность доступа к данным клиентов для телеметрии; регуляторные ограничения на обмен данными; высокая стоимость инфраструктуры без чёткого ROI
"""
steps = generate_steps('Цифровая трансформация', 'Крупная производственная компания (1500 сотрудников) работает на устаревшей ERP-системе 2008 года. Руководство приняло решение о цифровой трансформации бизнеса: необходим переход на современную платформу, автоматизация производственных процессов и внедрение аналитики данных в режиме реального времени.', text)

def extract_step_titles(response: StepsResponse):
    return "\n".join(step.title for step in response.steps)

print(steps)
titles_text = extract_step_titles(steps)

print(titles_text)