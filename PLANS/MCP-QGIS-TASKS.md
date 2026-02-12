# MCP + QGIS: План реализации (MVP)

Версия: 0.1  
Дата: 2026-02-12  
Проект: 4114

## 1. Назначение файла

Этот файл фиксирует **практический план разработки** рабочего MCP-сервиса для QGIS на базе:

- `4114/QGIS/MCP-QGIS-CONCEPT.md`
- `4114/QGIS/MCP-QGIS-CONCEPT-TASKS.md`
- уже подготовленных спецификаций (`MCP-TOOLS-SCHEMA.md`, `PLAN-IR-SCHEMA.json`, `MCP-SECURITY.md` и др.)

## 2. Что уже готово (база)

- [x] Сформирована концепция архитектуры (`MCP-QGIS-CONCEPT.md`)
- [x] Закрыты блоки предТЗ (`MCP-QGIS-CONCEPT-TASKS.md`)
- [x] Определен контракт MCP tools (`MCP-TOOLS-SCHEMA.md`)
- [x] Определена схема Plan IR (`PLAN-IR-SCHEMA.json`)
- [x] Определены Data/Security/Deployment/Transactions/Sessions/Regulatory/HITL спецификации
- [x] Определен тест-план и заготовлены сценарии в `4114/QGIS/testdata/`

## 3. Границы MVP

MVP должен поддерживать:

- open/save проекта;
- каталог слоев;
- преобразование intent -> Plan IR;
- preview/validate/execute плана;
- топологическую проверку;
- создание и сравнение вариантов;
- Git snapshot;
- экспорт результатов.

## 4. Реализационные блоки

## Блок A. Bootstrap кода и структура сервиса (P0)

Ожидаемый результат: рабочий каркас MCP-сервера и модульная структура.

- [ ] Создать рабочую структуру проекта `mcp_qgis/` (core, tools, adapters, validators, infra).
- [ ] Создать единый файл конфигурации профилей (`local`, `server`).
- [ ] Подключить логирование и correlation id (`request_id`, `session_id`, `transaction_id`).
- [ ] Добавить базовые CLI-команды: `run`, `check-config`, `doctor`.
- [ ] Добавить `README` для запуска MVP.

Критерий готовности:

- сервис стартует локально и отвечает на healthcheck.

## Блок B. API слой и валидация контрактов (P0)

Ожидаемый результат: строгая проверка входа/выхода всех инструментов.

- [ ] Имплементировать envelope из `4114/QGIS/MCP-TOOLS-SCHEMA.md`.
- [ ] Подключить JSON-schema validation из `4114/QGIS/schemas/mcp-tools.schema.json`.
- [ ] Добавить единый mapper ошибок (`E_VALIDATION`, `E_CONFLICT`, `E_INTERNAL` и т.д.).
- [ ] Добавить версионность `api_version` и отказ на несовместимых версиях.
- [ ] Реализовать примеры позитивных/негативных контрактных тестов.

Критерий готовности:

- все входы tools валидируются автоматически до бизнес-логики.

## Блок C. Session/Lock/Transaction Core (P0)

Ожидаемый результат: безопасное выполнение изменений с rollback.

- [ ] Реализовать менеджер сессий по `4114/QGIS/MCP-SESSIONS.md`.
- [ ] Реализовать lock manager (project/layer write lock, read lock).
- [ ] Реализовать transaction manager по `4114/QGIS/MCP-TRANSACTIONS.md`.
- [ ] Добавить recovery для `recovery_pending` транзакций.
- [ ] Добавить журнал tx-событий.

Критерий готовности:

- при ошибке в середине плана состояние корректно откатывается.

## Блок D. QGIS Adapter Layer (P0)

Ожидаемый результат: единый адаптер исполнения операций в QGIS.

- [ ] Реализовать Mode A (через открытый QGIS / plugin bridge).
- [ ] Реализовать Mode B (через `qgis_process` для headless шагов).
- [ ] Реализовать адаптеры для `native:*` алгоритмов из allowlist.
- [ ] Добавить контроль CRS/единиц перед каждой гео-операцией.
- [ ] Добавить безопасный timeout + retry для внешних вызовов.

Критерий готовности:

- split/fix/snap/difference/translate/validate выполняются воспроизводимо в обоих режимах (где применимо).

## Блок E. Реализация 12 MCP Tools (P0)

Ожидаемый результат: полный набор инструментов MVP по контракту.

- [ ] `project_open`
- [ ] `project_state`
- [ ] `layer_catalog`
- [ ] `intent_to_plan`
- [ ] `plan_preview`
- [ ] `plan_validate`
- [ ] `plan_execute`
- [ ] `topology_validate`
- [ ] `variant_create`
- [ ] `variant_compare`
- [ ] `git_snapshot`
- [ ] `export_result`

Критерий готовности:

- каждый tool имеет контрактные тесты и обработку ошибок по spec.

## Блок F. Plan IR Engine (P0)

Ожидаемый результат: валидируемый и исполняемый plan-пайплайн.

- [ ] Подключить `4114/QGIS/PLAN-IR-SCHEMA.json` в runtime.
- [ ] Реализовать parser/validator Plan IR.
- [ ] Реализовать dependency resolution между шагами (`depends_on`).
- [ ] Реализовать step executor + postchecks.
- [ ] Реализовать dry-run режим на уровне execution graph.

Критерий готовности:

- невалидный план блокируется; валидный выполняется и протоколируется.

## Блок G. Validation & Ruleset Engine (P0)

Ожидаемый результат: обязательные кадастровые guardrails.

- [ ] Реализовать ruleset loader по `4114/QGIS/MCP-REGULATORY-RULES.md`.
- [ ] Реализовать hard/soft validation pipeline.
- [ ] Реализовать topology checks (overlap/gap/self-intersection).
- [ ] Реализовать проверку доступа к дороге для лотов.
- [ ] Реализовать проверку ограничений по площади/дистанциям.

Критерий готовности:

- hard violation блокирует commit.

## Блок H. Planner & Intent Workflow (P1)

Ожидаемый результат: перевод пользовательского текста в исполняемый план.

- [ ] Реализовать intent parser (ключевые параметры: N лотов, ширина дороги, отступы, коммуникации).
- [ ] Реализовать генерацию Plan IR шаблонов для основных сценариев.
- [ ] Реализовать механизм `missing_inputs` + уточняющие вопросы.
- [ ] Реализовать preview summary (оценка изменений до commit).

Критерий готовности:

- сценарии “раздели на N + дорога” и “сдвинь границу на X м” формируют валидные планы.

## Блок I. Variant Engine и отчеты (P1)

Ожидаемый результат: объективное сравнение вариантов.

- [ ] Реализовать ветвление вариантов (`variant_create`).
- [ ] Реализовать расчет метрик по `4114/QGIS/MCP-VARIANT-REPORT.md`.
- [ ] Реализовать итоговый score и tie-breakers.
- [ ] Реализовать JSON + Markdown отчеты сравнения.

Критерий готовности:

- система стабильно выбирает winner на одинаковом наборе входов.

## Блок J. Security + HITL реализация (P1)

Ожидаемый результат: защищенный режим выполнения с подтверждениями риска.

- [ ] Реализовать role-based authorization (`read_only`/`editor`/`admin`).
- [ ] Реализовать default deny для `execute_code`.
- [ ] Реализовать allowlist processing algorithms.
- [ ] Реализовать HITL confirmation token flow.
- [ ] Реализовать полный audit trail.

Критерий готовности:

- high-risk операции не проходят без подтверждения.

## Блок K. Artifacts + Git Integration (P1)

Ожидаемый результат: воспроизводимость и откаты на уровне проекта.

- [ ] Реализовать `git_snapshot` с проверкой dirty state.
- [ ] Реализовать единый layout артефактов (`artifacts/<plan_id>/...`).
- [ ] Реализовать экспорт в gpkg/geojson/qgs.
- [ ] Реализовать привязку артефактов к `plan_id` и `transaction_id`.

Критерий готовности:

- каждое выполнение оставляет полный trace + экспорт.

## Блок L. Deployment (Local -> Server) (P2)

Ожидаемый результат: переносимый запуск без ручных костылей.

- [ ] Реализовать local profile (Mac + open QGIS).
- [ ] Реализовать server profile (headless path где возможно).
- [ ] Подготовить backup/restore скрипты.
- [ ] Добавить healthchecks и smoke script.

Критерий готовности:

- локальный запуск и перенос на сервер документированы и повторяемы.

## Блок M. QA, CI и приемка MVP (P0/P1)

Ожидаемый результат: проверяемое качество и готовность к старту эксплуатации.

- [ ] Подключить unit/integration/e2e suites по `4114/QGIS/MCP-TEST-PLAN.md`.
- [ ] Подключить smoke/regression pipeline.
- [ ] Прогнать 5 эталонных сценариев из `4114/QGIS/testdata/`.
- [ ] Проверить выполнение SLO/SLA из `4114/QGIS/MCP-QGIS-CONCEPT.md`.
- [ ] Подготовить MVP release checklist.

Критерий готовности:

- все критичные тесты зелёные, критерии приемки достигнуты.

## 5. Последовательность выполнения

- [ ] Шаг 1: Блоки A+B+C
- [ ] Шаг 2: Блоки D+E+F+G
- [ ] Шаг 3: Блоки H+I+J+K
- [ ] Шаг 4: Блоки L+M

## 6. Definition of Done (MVP)

- [ ] Все P0 блоки завершены
- [ ] Не менее 80% unit coverage
- [ ] Все e2e критичные сценарии пройдены
- [ ] Есть rollback и audit trace для каждого `plan_execute`
- [ ] SLO/SLA достигнуты
- [ ] Документация запуска и эксплуатации завершена

## 7. Журнал статуса

2026-02-12:

- Создан `MCP-QGIS-TASKS.md` как основной execution-план реализации MVP.
- Стартовая фаза: planning complete, implementation not started.

