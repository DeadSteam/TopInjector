# Feature Gap Analysis: TopInjector vs GhostLab

> Сгенерирован 2026-10-25 на основе сканирования всех страниц ghostlab.ru через Playwright.

---

## Навигация GhostLab (полная)

```
Top bar:
  ├── Сводка (dashboard)          ← /dashboard
  ├── Проекты                     ← /projects
  │   └── Создать проект
  │   └── фильтры по интеграциям (?integration=xxx)
  ├── Очередь                     ← /queue
  ├── Аналитика                   ← /analytics
  ├── Пользователи                ← /users
  ├── Настройки
  │   ├── Интеграции              ← /settings/integrations
  │   ├── Стоп-слова              ← /settings/stop-words
  │   ├── Преднагул               ← /warmups
  │   ├── Моя панель pro          ← /settings/admin
  │   └── Внешние сервисы         ← /settings/external-services
  └── Баланс (link in header)     ← /plan

Header stats bar:
  ├── Производительность (live counters)
  ├── RPM лимит
  ├── Клики (done/plan)
  ├── Поле поиска (Ctrl+E)
  ├── Уведомления
  ├── Пользователи count
  └── Баланс
```

---

## Сводка (/dashboard) — НЕДОСТАТКИ

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Табы Обзор / Пользователи / Серверы | ❌ Нет табов | 🔴 HIGH |
| Живые счётчики производительности (2 числа) | ⚠️ Частично | 🟡 MEDIUM |
| RPM лимит-индикатор ("12 / 300") | ✅ Есть | ✅ DONE |
| Клики done/plan counters | ⚠️ Частично | 🟡 MEDIUM |
| Фильтр по проектам в сводке | ❌ Нет | 🔴 HIGH |

---

## Пользователи (/users) — НЕДОСТАТКИ

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Табы Пользователи / Команды | ⚠️ Только базовые пользователи | 🔴 HIGH |
| Кнопка "Отчёт" | ❌ Нет | 🟡 MEDIUM |
| Ссылка регистрации для пользователей | ❌ Нет | 🔴 HIGH |
| Предоплата за пользователя (₽/клик) | ❌ Нет в модели User | 🔴 HIGH |
| Управление пользователем (edit/delete/role) | ⚠️ Частично | 🟡 MEDIUM |

---

## Интеграции (/settings/integrations) — ГЛАВНЫЙ ПРОБЕЛ

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Модель Integration (сервер-бот) | ❌ Нет модели | 🔴 HIGH |
| Поддержка Monstro/Alpine/Portal/Fantom | ❌ Нет | 🔴 HIGH |
| Группы интеграций (Ryzen7 PowerVPS, Ryzen9+7) | ❌ Нет модели | 🔴 HIGH |
| Белый список серверов (IP) | ❌ Нет | 🟡 MEDIUM |
| RPM лимит на интеграцию | ❌ Нет | 🟡 MEDIUM |
| Резервные сервера (toggle) | ❌ Нет | 🟡 MEDIUM |
| Активных проектов N из M | ❌ Нет | 🟡 MEDIUM |
| Пользователи использующие интеграцию | ❌ Нет | 🟡 MEDIUM |
| Public integration marketplace | ❌ Нет | 🟢 LOW |

---

## Моя панель Pro (/settings/admin) — Брендинг

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| White Label: поддомен + DNS CNAME | ❌ Нет модели | 🔴 HIGH |
| Название платформы | ❌ Нет поля | 🟡 MEDIUM |
| Accent color (выбор из палитры) | ⚠️ Хардкод #3B82F6 | 🟡 MEDIUM |
| Описание панели (Markdown) | ❌ Нет | 🟢 LOW |
| Логотип светлая тема | ❌ Нет upload | 🔴 HIGH |
| Логотип тёмная тема | ❌ Нет upload | 🔴 HIGH |
| Favicon | ⚠️ Есть статик файлы, но нет admin upload | 🟡 MEDIUM |
| Баннер каталога (1200×300) | ❌ Нет | 🟢 LOW |
| Баннер главной (220×130) | ❌ Нет | 🟢 LOW |
| Перенос пользователей между панелями | ❌ Нет | 🟢 LOW |

---

## Тарифный план (/plan) — Экономика

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Модель Plan/Subscription | ❌ Нет модели | 🔴 HIGH |
| Тарифы (Start/Lite/Plus/Pro/Ultra/Max) | ❌ Нет | 🔴 HIGH |
| Лимиты серверов по тарифу | ❌ Нет проверки | 🔴 HIGH |
| Лимиты запросов (счётчик) | ❌ Нет | 🟡 MEDIUM |
| Цена пользователя ₽/день | ❌ Нет | 🔴 HIGH |
| RPM лимит тарифа (300 для Lite) | ❌ Нет | 🟡 MEDIUM |
| Оплата: предоплата / постоплата режим | ❌ Нет | 🟡 MEDIUM |
| Деньги на сервере (Op/Pay mode) | ⚠️ balance_credits display only | 🔴 HIGH |
| Списание за тариф ежедневно | ❌ Нет worker | 🔴 HIGH |
| Бонусные кредиты | ❌ Нет поля bonus_credits | 🟢 LOW |

---

## Внешние сервисы (/settings/external-services) — ДОСМОТРЕНО

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Яндекс Вебмастер (аккаунты, мониторинг позиций/CTR) | ❌ Нет модели | 🔴 HIGH |
| XMLRiver (user_id + API ключ для частотности Вордстат) | ❌ Нет модели | 🟡 MEDIUM |
| XMLStock (SERP scraping keys) | ❌ Нет модели | 🟢 LOW |

External services = хранилище API-ключей внешних сервисов + привязка Вебмастера к проектам.

---

## Очередь (/queue) — ФУНКЦИОНАЛ

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Фильтры по Проект/Интеграция/Статус/Источник | ⚠️ Частично | 🟡 MEDIUM |
| Date range picker (от/до) | ❌ Нет в UI | 🟡 MEDIUM |
| Статистика Источников + Статусов сверху | ❌ Нет | 🔴 HIGH |
| "Очистить очередь" кнопка | ⚠️ Возможно есть | 🟢 LOW |
| Показано N из M с пагинацией | ⚠️ Есть пагинация | ✅ DONE (частично) |

---

## Аналитика (/analytics) — ФУНКЦИОНАЛ

| Фича GhostLab | Status в TopInjector | Приоритет |
|---------------|---------------------|-----------|
| Период дата-пикер (Старт/Конец) | ❌ Нет в UI | 🔴 HIGH |
| Фильтр по проекту | ⚠️ Есть query param | ✅ DONE (частично) |
| Кнопка "Отчёт" | ❌ Нет | 🟡 MEDIUM |
| Графики/таблицы запросов | ⚠️ Частично | 🟡 MEDIUM |

---

## Модель данных GhostLab (вывод из UI)

На основе анализа UI, вот модель которую GhostLab использует:

```python
# Пользователь
User {
  id, email, password_hash, display_name, is_admin, is_active
  prepay_per_click: float          # стоимость клика за пользователя
  team_id: FK -> Team
}

# Команда
Team {
  id, name, owner_user_id
  balance_credits: int             # общий баланс команды
}

# Интеграция (сервер-бот) — ГЛАВНАЯ НОВАЯ МОДЕЛЬ
IntegrationGroup {
  id, name, user_id
  max_projects: int               # лимит по тарифу
  current_projects: int           # счётчик
  ip_whitelist: list[str]         # белый список IP
  rpm_limit: int                  # RPM лимит для этой группы
  use_reserved: bool              # резервные сервера
  is_public: bool                 # для marketplace
}

IntegrationServer {               # отдельный сервер в группе
  id, integration_group_id, name, ip_address, software_type
  # software_type: alpine | monstro | portal | fantom
}

# План/Тариф
Plan {
  id, name                       # Start, Lite, Plus, Pro, Ultra, Max
  max_servers: int
  max_requests_per_month: int    # 0 = unlimited (Pro/Ultra/Max)
  user_cost_per_day: float       # цена за активного пользователя
  base_price_per_day: float      # базовая цена тарифа
  rpm_limit: int                 # скорость обращений
}

UserPlan {                        # текущий план пользователя
  id, user_id, plan_id
  start_date, end_date
  active_users_count: int        # для биллинга
  requests_used: int             # счётчик запросов в месяце
}

# White Label
WhiteLabel {
  id, user_id, domain, platform_name, accent_color
  logo_light: str, logo_dark: str, favicon: str
  description: str               # markdown
  banner_catalog: str            # 1200x300 image
  banner_homepage: str           # 220x130 image
  welcome_text: str              # markdown
  dns_status: enum {pending, verified, error}
}

# Баланс/Транзакции (уже есть, но расширить)
BalanceTransaction {            # существующая — добавить:
  id, project_id, amount, description, type
  # NEW: user_id instead of project_id for team billing
  # NEW: plan_deduction flag
}

# Проект (расширить существующий)
Project {                       # текущие поля + новые:
  # ...existing fields...
  integration_group_id: FK      # привязка к интеграции
  priority: int                 # "Приоритет" бейдж
  is_active: bool               # активный/неактивный проект
}

# Стоп-слова (уже есть)
StopWord {                      # существующая ✅
  id, project_id, word
}

# Преднагул / Warmup кампании (уже есть)
WarmupCampaign {                # существующая ✅
  id, project_id, name, clicks_per_hour, total_target
  start_time, end_time
}
```

---

## Приоритизация реализации

### ФАЗА 1: Ядро экономики (🔴 HIGH — must have)
1. **Модель IntegrationGroup + IntegrationServer** — основа всей системы серверов
2. **Модель Plan/Subscription** — тарифы и лимиты
3. **Расширение BalanceTransaction** — списание за тариф ежедневно
4. **Предоплата за пользователя** — prepay_per_click в User модели

### ФАЗА 2: White Label (🔴 HIGH — must have)
5. **Модель WhiteLabel** — брендинг панели
6. API для white label настроек
7. Динамический CSS/JS на основе настроек брендинга

### ФАЗА 3: Dashboard + Users (🟡 MEDIUM)
8. Улучшение /dashboard с табами и счётчиками
9. Команды пользователей — модель Team + UI
10. Ссылка регистрации для реселлеров

### ФАЗА 4: Queue enhancements (🟡 MEDIUM)
11. Фильтры по интеграции, date range
12. Статистика источников/статусов вверху очереди
13. Кнопка "Очистить очередь"

### ФАЗА 5: Аналитика (🟡 MEDIUM)
14. Дата-пикер периода для аналитики
15. Экспорт отчётов

### ФАЗА 6: External services (🟢 LOW)
16. API ключи внешних сервисов
17. Webhooks

---

## ИТОГО

**Новых моделей:** 4-5 (IntegrationGroup, IntegrationServer, Plan/Subscription, WhiteLabel, Team)
**Новых эндпоинтов API:** ~30-40
**Изменений существующих моделей:** 3 (Project, User, BalanceTransaction)
**Новых миграций:** 5-7
