# TODO — Остаток плана GhostLab (все незавершённые задачи)

## Задача 1: Создание проекта с выбором Integration Group
- Добавить select "Серверная группа" в модалку создания/редактирования проекта  
- Загрузка групп через API при открытии модалки

## Задача 2: Daily Deduction Worker + Bonus Credits
- Модель: User.bonus_credits (копейки, бонусный баланс)
- Расширить BalanceTransaction.type для plan_deduction/user_charge логики
- Worker ежедневного списания за тариф
- Worker списания user charges (prepay_per_click * active clicks)

## Задача 3: Dashboard табы + Live счётчики
- Tab: "Обзор" — основные метрики и графики в стиле GhostLab
- Tab: "Пользователи" — управление командой
- Tab: "Серверы/Интеграции" — статус групп интеграций  
- Live counters: RPM индикатор, клики done/plan

## Задача 4: XMLStock SERP Scraping полноценный
- API endpoints для SERP scraping через XMLStock
- UI в настройках внешних сервисов для управления ключами и просмотра результатов

## Задача 5: Referral ссылки регистрации
- Модель: ReferralLink с уникальным кодом
- API endpoints для создания/отслеживания реферальных ссылок
- Связка с бонусными кредитами
