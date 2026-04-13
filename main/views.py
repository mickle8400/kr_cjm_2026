import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import SituationForm, StrategyForm
from .models import Step
from .models import Strategy, Situation
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

load_dotenv()
import os

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

    strategies_r =  call_openai_structured(
        model="gpt-5-nano",
        system_prompt=STRATEGIES_SYSTEM,
        user_prompt=user_prompt,
        response_schema=StrategiesResponse,
    )

    data_1 = dict(re.findall(r"(\w+)='([^']*)'", str(strategies_r.strategies[0])))
    data_2 = dict(re.findall(r"(\w+)='([^']*)'", str(strategies_r.strategies[1])))
    data_3 = dict(re.findall(r"(\w+)='([^']*)'", str(strategies_r.strategies[2])))
    # 👉 всё в одну переменную
    result_1 = ""
    result_2 = ""
    result_3 = ""
    for key, value in data_1.items():
        result_1 += f"{key.upper()}:\n{value}\n"
    for key, value in data_2.items():
        result_2 += f"{key.upper()}:\n{value}\n"
    for key, value in data_3.items():
        result_3 += f"{key.upper()}:\n{value}\n"

    return {
        "field1": result_1,
        "field2": result_2,
        "field3": result_3
    }

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

def extract_step_titles(response: StepsResponse):
    return "\n".join(step.title for step in response.steps)



def generate_steps(situation_type, situation_description, text) -> StepsResponse:
    data = parse_strategy(text)

    user_prompt = f"""Разработай детальный пошаговый план реализации стратегии.

=== СИТУАЦИЯ КЛИЕНТА (контекст) ===
Тип: {situation_type}
Описание: {situation_description}

=== ВЫБРАННАЯ СТРАТЕГИЯ ===
Название: {data['title']}
Цель: {data['goal']}
Описание: {data['description']}
"""

    response = call_openai_structured(
        model="gpt-5-nano",
        system_prompt=STEPS_SYSTEM,
        user_prompt=user_prompt,
        response_schema=StepsResponse,
    )

    return response

@login_required
def home(request):
    if request.method == 'POST':
        form = SituationForm(request.POST)
        if form.is_valid():
            situation = form.save(commit=False)
            situation.user = request.user
            situation.save()

            # 👉 ВЫЗЫВАЕМ ФУНКЦИЮ
            strategies_data = generate_strategies(
                situation.type,
                situation.description
            )

            # 👉 СОЗДАЁМ СТРАТЕГИЮ СРАЗУ
            from .models import Strategy

            strategy = Strategy.objects.create(
                situation=situation,
                field1=strategies_data["field1"],
                field2=strategies_data["field2"],
                field3=strategies_data["field3"],
            )

            return redirect('strategy', situation_id=situation.id)
    else:
        form = SituationForm()

    return render(request, 'home.html', {'form': form})

@login_required
def strategy(request, situation_id):
    from .models import Strategy, Step

    strategy = Strategy.objects.filter(situation_id=situation_id).first()
    situation = get_object_or_404(Situation, id=situation_id)

    if request.method == 'POST':
        form = StrategyForm(request.POST, instance=strategy)
        if form.is_valid():
            form.save()  # 🔥 сохраняем изменения текста
        selected = request.POST.get('selected')

        if selected == 'field1':
            selected_text = strategy.field1
        elif selected == 'field2':
            selected_text = strategy.field2
        elif selected == 'field3':
            selected_text = strategy.field3
        else:
            selected_text = ""

        # 🔥 Генерируем шаги
        response = generate_steps(
            situation.type,
            situation.description,
            selected_text
        )

        # 🔥 Удаляем старые шаги
        Step.objects.filter(strategy=strategy).delete()

        # 🔥 Сохраняем каждый шаг отдельно
        for step_data in response.steps:
            Step.objects.create(
                strategy=strategy,
                title=step_data.title,
                description=step_data.description,
                responsible=step_data.responsible,
                duration=step_data.duration
            )

        if selected:
            chosen_value = getattr(strategy, selected)
            request.session['chosen_strategy'] = chosen_value

        return redirect('steps', strategy_id=strategy.id)

    else:
        form = StrategyForm(instance=strategy)

    return render(request, 'strategy.html', {'form': form})



@login_required
def steps_view(request, strategy_id):
    from .models import Step

    strategy = get_object_or_404(Strategy, id=strategy_id)
    steps = Step.objects.filter(strategy=strategy)

    if request.method == 'POST':
        selected_step_id = request.POST.get('selected_step')

        # 🔥 обновляем все шаги
        for step in steps:
            step.title = request.POST.get(f"title_{step.id}")
            step.description = request.POST.get(f"desc_{step.id}")
            step.responsible = request.POST.get(f"resp_{step.id}")
            step.duration = request.POST.get(f"dur_{step.id}")
            step.save()

        # 🔥 сохраняем выбранный шаг
        if selected_step_id:
            request.session['selected_step'] = selected_step_id

        return redirect('home')

    return render(request, 'steps.html', {
        'steps': steps
    })
