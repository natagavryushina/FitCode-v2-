## Roadmap: Телеграм-бот «Персональный тренер, нутрициолог и наставник»

Коротко:
- Голос → Whisper (turbo) → текст
- Текст + список всех категорий → LLM через OpenRouter
- Персональные тренировки без повторов под цель/уровень и для каждой группы мышц
- Индивидуальные планы питания
- Все данные LLM сохраняются в SQLite
- Тон сообщений: дружелюбный, «Пиши, сокращай», эмодзи
- Приоритет: безопасность уровня прод

---

## Архитектура и стек
- Язык: Python 3.11+
- Телеграм: `aiogram` 3.x (webhook или long polling для локальной разработки)
- ORM и БД: `SQLAlchemy 2.x` + `SQLite` (возможность замены на SQLCipher для шифрования)
- Модели данных и валидация: `pydantic`
- Аудио-конвертация: `ffmpeg` (OGG/Opus → WAV/MP3 при необходимости)
- Расшифровка аудио: OpenAI Whisper (turbo)
- LLM: OpenRouter API (модель выбирается при интеграции; кандидат — Claude 3.5 Sonnet или GPT-4o-mini)
- Планировщик задач: `APScheduler` (генерация расписаний, напоминания)
- Логирование: стандартный `logging` + структурированные логи
- Конфигурация: `.env` + безопасное управление секретами

Компоненты:
- Bot Service (обработка апдейтов Telegram, маршрутизация команд и сообщений)
- ASR Service (загрузка и конвертация аудио, вызов Whisper (turbo))
- LLM Service (формирование промптов, вызовы OpenRouter, постобработка и сохранение)
- Workout & Nutrition Engine (генератор тренировок/рационов с гарантиями уникальности и покрытием групп мышц)
- Content Store (библиотека упражнений/рецептов)
- Persistence (SQLite, ORM-модели, репозитории)

---

## Категории, передаваемые в LLM вместе с текстом пользователя
- **Профиль**: пол, дата рождения, рост, вес, уровень (новичок/средний/продвинутый), опыт, травмы/ограничения
- **Цели**: жиросжигание, набор мышц, сила, выносливость, mobility, реабилитация
- **Инвентарь**: домашний/зал, доступное оборудование (гантели, штанга, тренажёры, резинки и т. п.)
- **Расписание**: дни недели, длительность, часовой пояс
- **Предпочтения**: формат тренировок, стиль коммуникации, эмодзи/без
- **Питание**: калорийность, макрораспределение, тип диеты (омни/вег/веган/кето и т. п.), аллергии, непереносимости, кухня, бюджет, время готовки
- **История**: выполненные тренировки, усталость, RPE, отзывы
- **Ограничения**: медицинские замечания, запрещённые движения

Пример полезной структуры для LLM (JSON):
```json
{
  "profile": {"sex": "male", "age": 29, "height_cm": 182, "weight_kg": 84, "level": "intermediate"},
  "goals": ["fat_loss", "muscle_gain_minor"],
  "equipment": ["dumbbells", "pullup_bar"],
  "schedule": {"days": ["Mon","Wed","Fri"], "duration_min": 50, "timezone": "+03:00"},
  "nutrition": {"target_kcal": 2300, "diet_type": "omnivorous", "allergens": ["peanuts"], "cuisine": ["mediterranean"]},
  "history": {"recent_workouts": [123,124,130], "avoid_exercises": ["back_squat"]},
  "constraints": {"no_knee_pain": true}
}
```

---

## Схема данных (SQLite, укрупнённо)

```sql
-- Пользователи
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  tg_user_id TEXT UNIQUE NOT NULL,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  sex TEXT,
  birth_date TEXT,
  height_cm INTEGER,
  weight_kg REAL,
  level TEXT,
  activity_level TEXT,
  injuries TEXT,
  allergies TEXT,
  diet_type TEXT,
  preferences_json TEXT,
  timezone TEXT,
  created_at TEXT,
  updated_at TEXT
);

-- Сообщения и транскрипции
CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  direction TEXT CHECK(direction IN ('in','out')),
  type TEXT CHECK(type IN ('text','voice','system')),
  content TEXT,
  created_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE transcriptions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  telegram_file_id TEXT,
  audio_duration_sec REAL,
  format TEXT,
  text TEXT,
  confidence REAL,
  created_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Взаимодействие с LLM
CREATE TABLE llm_requests (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  provider TEXT,
  model TEXT,
  prompt TEXT,
  categories_json TEXT,
  created_at TEXT,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE llm_responses (
  id INTEGER PRIMARY KEY,
  request_id INTEGER NOT NULL,
  content TEXT,
  tokens_prompt INTEGER,
  tokens_completion INTEGER,
  metadata_json TEXT,
  created_at TEXT,
  FOREIGN KEY(request_id) REFERENCES llm_requests(id)
);

-- Контент: мышцы, упражнения, тренировки
CREATE TABLE muscles (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE exercises (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE,
  name TEXT NOT NULL,
  primary_muscle_id INTEGER,
  equipment TEXT,
  level TEXT,
  instructions TEXT,
  video_url TEXT,
  is_bodyweight INTEGER,
  FOREIGN KEY(primary_muscle_id) REFERENCES muscles(id)
);

CREATE TABLE exercise_muscle_secondary (
  exercise_id INTEGER,
  muscle_id INTEGER,
  PRIMARY KEY (exercise_id, muscle_id)
);

CREATE TABLE workouts (
  id INTEGER PRIMARY KEY,
  title TEXT,
  description TEXT,
  level TEXT,
  goal TEXT,
  duration_min INTEGER,
  focus_muscle_group TEXT,
  equipment TEXT,
  uniqueness_hash TEXT,
  source_type TEXT CHECK(source_type IN ('curated','llm','hybrid'))
);

CREATE TABLE workout_exercises (
  workout_id INTEGER,
  exercise_id INTEGER,
  sets INTEGER,
  reps TEXT,
  tempo TEXT,
  rest_sec INTEGER,
  PRIMARY KEY (workout_id, exercise_id)
);

-- Пользовательские планы и сессии
CREATE TABLE user_workout_plans (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  goal TEXT,
  start_date TEXT,
  end_date TEXT,
  schedule_json TEXT,
  is_active INTEGER,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE user_workout_sessions (
  id INTEGER PRIMARY KEY,
  plan_id INTEGER,
  date TEXT,
  workout_id INTEGER,
  status TEXT CHECK(status IN ('planned','done','skipped')),
  rpe INTEGER,
  feedback TEXT,
  FOREIGN KEY(plan_id) REFERENCES user_workout_plans(id)
);

-- Питание
CREATE TABLE meal_plans (
  id INTEGER PRIMARY KEY,
  title TEXT,
  total_kcal INTEGER,
  protein_g REAL,
  fat_g REAL,
  carbs_g REAL,
  diet_type TEXT,
  cuisine TEXT,
  allergens_excluded TEXT,
  goal TEXT,
  level TEXT
);

CREATE TABLE meals (
  id INTEGER PRIMARY KEY,
  meal_plan_id INTEGER,
  title TEXT,
  kcal INTEGER,
  protein_g REAL,
  fat_g REAL,
  carbs_g REAL,
  recipe TEXT,
  ingredients_json TEXT,
  FOREIGN KEY(meal_plan_id) REFERENCES meal_plans(id)
);
```

---

## Правила генератора тренировок (уникальность и качество)
- Уникальность по пользователю: вычислять `uniqueness_hash` на основе набора упражнений, сетов/повторов/темпа/отдыха; хранить историю и исключать дубликаты (скользящее окно ≥ 90 дней)
- Покрытие групп мышц за неделю: гарантировать баланс push/pull/legs/core + прицельная работа под цель пользователя
- Прогрессия нагрузки: постепенное увеличение объёма/интенсивности с недельными блоками (безопасные шаги)
- Ограничения движений: учитывать травмы, запрещённые упражнения, доступный инвентарь
- Структура каждой тренировки: разминка → основная часть → заминка/мобилити
- Детерминизм: опциональный `seed` для воспроизводимости
- Валидация: отбраковка нереалистичных схем (слишком большой объём, конфликт с ограничениями)

---

## Промпт-стратегия (копирайтинг «Пиши, сокращай», дружелюбный тон, эмодзи)
Системный промпт для OpenRouter:
```text
Ты — профессиональный фитнес-наставник и копирайтер. Пиши кратко и ясно, по принципам «Пиши, сокращай». Тон — дружелюбный, мотивирующий, без назидания. Добавляй уместные эмодзи. Соблюдай безопасность движений и мед. ограничения. Если данных мало — задавай 1-2 уточняющих вопроса.

Форматируй ответы для Телеграм: короткие абзацы, списки, заголовки. Не используй длинные простыни текста.
```

Шаблон пользовательского промпта:
```text
Контекст пользователя (JSON):
{{categories_json}}

Сообщение пользователя:
"""
{{user_text}}
"""

Задача: дай конкретный, безопасный и краткий ответ + предложи следующий шаг (кнопка/команда). Если запрос про тренировку — учти уникальность и историю. Если про питание — учти калорийность и ограничения.
```

---

## Пользовательские потоки (основные)
- Onboarding `/start`: сбор профиля, целей, уровня, инвентаря, расписания → сохранение в БД → подтверждение
- Голосовое сообщение: загрузка аудио → ffmpeg-конвертация (если нужно) → Whisper (turbo) → текст → компоновка `categories_json` → вызов LLM (OpenRouter) → сохранение запроса/ответа → ответ пользователю
- «Тренировка на сегодня»: генерация по плану/целям с гарантией уникальности → отправка с кнопками «Сделал/Пропустить/Заменить» → сохранение статуса и фидбэка
- «Питание на сегодня»: расчёт калорий/макро → выдача меню/рецептов → возможность заменить блюда с учётом ограничений

---

## Безопасность (ключевые требования)
- Хранение секретов только в переменных окружения (`TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`)
- Валидация входных данных (Pydantic), ограничение размера аудио, проверка MIME, отказ от опасных путей/имён файлов
- Минимизация контекста в LLM, защита от prompt injection (строгий системный промпт, экранирование пользовательского текста)
- Ограничение частоты (rate limit) по пользователю и по глобальным API
- Шифрование в транзите (HTTPS), опционально — шифрование в хранении (SQLCipher/полевая криптография для PII)
- Управление доступом к отладочным логам, отсутствие секретов в логах
- Очистка временных файлов аудио, политики хранения персональных данных

---

## Пошаговый план работ (чек-лист)

### 0. Инициализация проекта
- [ ] Создать репозиторий и базовую структуру директорий (`/bot`, `/services`, `/db`, `/content`)
- [ ] Добавить `pyproject.toml` или `requirements.txt` (aiogram, sqlalchemy, pydantic, httpx, python-dotenv, apscheduler)
- [ ] Подготовить `.env.template` (TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, OPENROUTER_API_KEY, OPENROUTER_BASE_URL)
- [ ] Настроить базовый `logging` и конфиг-менеджер

### 1. Базовый каркас Телеграм-бота
- [ ] Поднять обработчик апдейтов (aiogram), команды `/start`, `/help`, `/profile`
- [ ] Реализовать хранение сессий пользователя (FSM/простая сессия)
- [ ] Скелет экшенов: «Тренировка сегодня», «Питание сегодня», «Голосовое сообщение»

### 2. База данных и ORM
- [ ] Описать ORM-модели под таблицы из схемы (выше)
- [ ] Создать и инициализировать `SQLite` файл, функции репозиториев
- [ ] Репозитории: пользователи, сообщения, транскрипции, LLM-запросы/ответы

### 3. Интеграция Whisper (turbo)
- [ ] Обработка голосовых сообщений: скачивание файла из Telegram
- [ ] Конвертация через `ffmpeg` при необходимости (ограничение длительности/размера)
- [ ] Вызов OpenAI Whisper (turbo), парсинг результата, сохранение транскрипта в БД
- [ ] Обработка ошибок/ретраи/таймауты, очистка временных файлов

### 4. Интеграция OpenRouter (LLM)
- [ ] Подготовить системный и пользовательский промпты (копирайтинг, безопасность)
- [ ] Реализовать клиент к OpenRouter: модель, заголовки, таймауты, ретраи
- [ ] Компоновка `categories_json` из профиля/состояния
- [ ] Сохранять промпт, категории и ответ LLM в БД (учёт токенов/метаданных)

### 5. Контент: упражнения и рецепты
- [ ] Сформировать базовую библиотеку мышц и упражнений (≥ 200), импорт в БД
- [ ] Добавить рецепты/блюда с макро-профилем и тегами (диеты, аллергены, кухня)
- [ ] Утилита импорта CSV/JSON в таблицы контента

### 6. Генератор тренировок (уникальность и покрытие)
- [ ] Реализовать расчёт `uniqueness_hash` + хранение истории по пользователю
- [ ] Алгоритм подбора по целям/уровню/инвентарю/ограничениям
- [ ] Балансировка недельного плана (push/pull/legs/core), прогрессия нагрузки
- [ ] API: получить/создать «тренировку на сегодня», заменить упражнение

### 7. План питания
- [ ] Расчёт КБЖУ (Mifflin-St Jeor/HB + коэффициенты активности)
- [ ] Конструктор меню с учётом диеты, аллергенов, бюджета и времени готовки
- [ ] Замены блюд и пересчёт макро

### 8. Диалоги и сообщения бота
- [ ] Шаблоны сообщений в стиле «Пиши, сокращай» + эмодзи
- [ ] Консистентные карточки тренировки/рациона, короткие CTA-кнопки
- [ ] Обработка уточняющих вопросов, сбор недостающих данных

### 9. Безопасность и устойчивость
- [ ] Валидация файлов и ограничение нагрузки (размер/частота)
- [ ] Санитизация пользовательского ввода, защита от prompt injection
- [ ] Секреты только через env, отсутствуют в логах/репозитории
- [ ] Очистка временных аудио, политика хранения персональных данных

### 10. Аналитика продукта
- [ ] Метрики использования: активные пользователи, доля голосовых, средняя длина сессии
- [ ] Нон-персональные логи для улучшения UX (без PII)

### 11. Полировка UX
- [ ] Гид по командам, короткие подсказки, пустые состояния
- [ ] Улучшения формулировок, тональности и эмодзи

---

## Критерии готовности MVP (без тестирования и деплоя)
- [ ] Онбординг сохраняет профиль и цели в БД
- [ ] Голосовые сообщения корректно транскрибируются Whisper (turbo)
- [ ] Текст + категории уходит в LLM (OpenRouter), ответы сохраняются в SQLite
- [ ] Доступна «Тренировка на сегодня» с уникальностью и историей
- [ ] Доступен базовый «Рацион на сегодня» по целям и ограничениям
- [ ] Сообщения лаконичны, дружелюбны, с эмодзи
- [ ] Базовые меры безопасности включены (валидации, лимиты, секреты, очистка временных файлов)