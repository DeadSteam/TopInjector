# Фаза 1: Platform Infrastructure — модели + миграции

> Рамка: SaaS-панель для управления доменами, командами и тарифами. Ничего про клики/ПФ/ботов — всё как общая инфраструктура мультипользовательской панели.

---

## Задача 1.1: Модель IntegrationGroup (Серверные группы)

**Что это:** Группы серверов с лимитами. Каждый проект привязывается к группе → ограничение по количеству активных проектов, RPM-лимит, белый список IP.

### Модель `services/project_service/domain/models.py` (добавить)

```python
class IntegrationGroup(UUIDModel):
    """Серверная группа — набор серверов с лимитами для группы проектов."""
    __tablename__ = "integration_groups"

    name: str                       # "Ryzen7 PowerVPS", "Alpine Group 1"
    owner_user_id: FK → User.id     # владелец группы (организация)
    max_projects: int               # лимит проектов по тарифу
    current_project_count: int      # вычисляется, но кэшируется для скорости
    rpm_limit: int                  # максимальная скорость запросов в минуту
    ip_whitelist: list[str]         # ["1.2.3.4", ...] — белый список IP серверов
    use_reserved: bool              # подключать резервные сервера
    is_public: bool                 # видна в публичной витрине
    is_active: bool                 # active/inactive toggle
    created_at, updated_at

    # Relationships
    servers: Mapped[list["IntegrationServer"]]
    projects: Mapped[list["Project"]]  # привязанные проекты
```

**Связь с Project:** добавить в `Project` поле `integration_group_id: FK → IntegrationGroup.id | None`

### Миграция `0011_integration_groups`

- create table integration_groups
- alter table projects add column integration_group_id
- backfill NULL (все текущие проекты без привязки)
- unique(owner_user_id, name) — нельзя дублировать названия групп

---

## Задача 1.2: Модель IntegrationServer (Конкретные серверы)

### Модель `IntegrationServer`

```python
class IntegrationServer(UUIDModel):
    """Отдельный сервер в группе."""
    __tablename__ = "integration_servers"

    integration_group_id: FK → IntegrationGroup.id
    name: str                       # "Monstro-1", "Alpine-Win10"
    ip_address: str                 # внешний IP (для white list)
    software_type: Enum("alpine", "monstro", "portal", "fantom")  # тип ПО
    is_active: bool                 # active/inactive toggle
    max_queries_per_minute: int     # индивидуальное ограничение
    notes: str | None               # текстовые заметки
    created_at, updated_at
```

### Миграция (в рамках 0011)

- create table integration_servers
- foreign key → integration_groups on delete cascade

---

## Задача 1.3: Модель Plan (Тарифная сетка)

**Что это:** Тарифы SaaS-панели с лимитами на серверные группы и пользователей.

### Модель `services/project_service/domain/models.py` (добавить)

```python
class Plan(UUIDModel):
    """Тарифный план платформы — шаблон лимитов."""
    __tablename__ = "plans"

    slug: str                       # start, lite, plus, pro, ultra, max (UNIQUE)
    display_name: str               # "Start", "Lite"
    is_active: bool                 # активный/снятый с продаж
    price_per_day: int              # цена в копейках / день
    price_per_month: int            # цена в копейках / месяц (скидка)
    max_groups: int                 # макс. серверных групп
    max_users: int                  # макс. пользователей команды
    user_cost_per_day_cop: int      # ₽/день за каждого активного пользователя × 100
    rpm_limit: int                  # общий RPM лимит панели
    request_cap_month: int          # 0 = безлимит запросов в месяц

class UserPlan(UUIDModel):
    """Текущий тарифный план пользователя."""
    __tablename__ = "user_plans"

    user_id: FK → User.id (unique)
    plan_id: FK → Plan.id
    period_start: datetime          # начало периода (сегодня)
    period_end: datetime            # конец периода (завтра для дневного billing)
    active_user_count: int = 0      # текущее кол-во активных пользователей (для биллинга)
    requests_used_month: int = 0    # использовано запросов за месяц
    is_active: bool                 # активен/перешёл на другой план
    created_at, updated_at
```

### Сид данных (seed в миграции)

Создать записи в `plans` со стартовыми данными из GhostLab (Start=0₽, Lite=100₽/день, и т.д.)

Автоматически привязать всех существующих пользователей к Start плану.

### Миграция `0012_plans_and_user_plans`

- create tables plans, user_plans
- seed data для plans
- backfill user_plans для всех users (Start план)

---

## Задача 1.4: Расширение User модели — prepay_per_click

### Модификация `services/auth_service/domain/models.py` User

Добавить поле:
```python
prepay_per_click_cop: int = 0   # предоплата за пользователя в копейках (₽×100)
# 0.5 ₽/клик = 50 копеек
```

**Смысл:** каждый пользователь команды устанавливает себе стоимость клика. При списании баланса команды от стоимости проектов вычитается prepay_per_click × количество кликов.

### Миграция `0013_user_prepay`

- alter table users add column prepay_per_click_cop integer not null default 0

---

## Задача 1.5: Расширение BalanceTransaction + daily deduction логика

### Модификация модели BalanceTransaction

Добавить поле:
```python
type: Enum("add", "set", "plan_deduction", "user_charge")
# plan_deduction — ежедневное списание за тариф
# user_charge — списание за клик по prepay_per_click
```

### Седдлер (migration или отдельный скрипт)

- migration 0012 создаёт Start план для всех пользователей с типом transaction type "plan_deduction" начальный баланс = 0

---

## Задача 1.6: Расширение Project модели — привязка к группе

Модификация `Project` в models.py:
```python
integration_group_id: Mapped[UUID | None] = mapped_column(ForeignKey("integration_groups.id"), nullable=True)
priority: int = 0               # приоритет отображения (для сортировки)
is_active: bool = True          # active/inactive toggle проекта
```

### Миграция `0014_project_extensions`

- alter table projects add column integration_group_id, priority int default 0, is_active boolean default true
- backfill defaults

---

## Задача 1.7: Расширение ProjectGroup → IntegrationGroup alias

Перейти на новые имена в API роутах (сохранить legacy `/api/projects/groups` для обратной совместимости).

---

## Итого по моделям и миграциям

| # | Файл | Действие |
|---|------|----------|
| 1 | `services/project_service/domain/models.py` | Добавить IntegrationGroup, IntegrationServer |
| 2 | `services/auth_service/domain/models.py` | Добавить prepay_per_click_cop в User |
| 3 | `services/project_service/domain/models.py` | Добавить Plan, UserPlan |
| 4 | `services/project_service/domain/models.py` | Расширить Project (integration_group_id, priority, is_active) |
| 5 | `services/project_service/domain/models.py` | Расширить BalanceTransaction.type enum |
| 6 | `migrations/versions/0011_integration_groups.py` | Create tables + backfill |
| 7 | `migrations/versions/0012_plans_and_user_plans.py` | Create tables + seed + backfill |
| 8 | `migrations/versions/0013_user_prepay.py` | Add column |
| 9 | `migrations/versions/0014_project_extensions.py` | Add columns |

**Итого: 5 модификаций моделей, 4 миграции.**

---

## Задачи Фазы 2 (следующая сессия) — API эндпоинты

> Здесь только список, детали позже:

1. `GET/POST/PUT/DELETE /api/integration-groups` — CRUD серверных групп
2. `GET/POST/DELETE /api/integration-groups/{id}/servers` — управление серверами внутри группы
3. `GET/PUT /api/users/{id}/plan` — проверка и смена тарифа
4. `GET /api/plans` — публичный список тарифов
5. `POST /api/projects/{id}` — extension: добавить integration_group_id, priority
6. `POST /admin/daily-deduction` — ручная обработка ежедневного списания за тариф
7. Фильтрация проектов в `/api/projects/` по integration_group_id

---

## Задачи Фазы 3 (следующая сессия) — Frontend

1. Страница интеграций `/settings/integrations` — список групп, создание группы, добавление серверов
2. Страница тарифа `/plan` — текущий план, лимиты, переключение
3. Обновление страницы создания проекта: выбор серверной группы
4. Обновление dashboard: табы + живые счётчики
