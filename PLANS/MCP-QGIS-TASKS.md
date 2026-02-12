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

- [x] Создать рабочую структуру проекта `mcp_qgis/` (core, tools, adapters, validators, infra).
- [x] Создать единый файл конфигурации профилей (`local`, `server`).
- [x] Подключить логирование и correlation id (`request_id`, `session_id`, `transaction_id`).
- [x] Добавить базовые CLI-команды: `run`, `check-config`, `doctor`.
- [x] Добавить `README` для запуска MVP.

Критерий готовности:

- сервис стартует локально и отвечает на healthcheck.

## Блок B. API слой и валидация контрактов (P0)

Ожидаемый результат: строгая проверка входа/выхода всех инструментов.

- [x] Имплементировать envelope из `4114/QGIS/MCP-TOOLS-SCHEMA.md`.
- [x] Подключить JSON-schema validation из `4114/QGIS/schemas/mcp-tools.schema.json`.
- [x] Добавить единый mapper ошибок (`E_VALIDATION`, `E_CONFLICT`, `E_INTERNAL` и т.д.).
- [x] Добавить версионность `api_version` и отказ на несовместимых версиях.
- [x] Реализовать примеры позитивных/негативных контрактных тестов.

Критерий готовности:

- все входы tools валидируются автоматически до бизнес-логики.

## Блок C. Session/Lock/Transaction Core (P0)

Ожидаемый результат: безопасное выполнение изменений с rollback.

- [x] Реализовать менеджер сессий по `4114/QGIS/MCP-SESSIONS.md`.
- [x] Реализовать lock manager (project/layer write lock, read lock).
- [x] Реализовать transaction manager по `4114/QGIS/MCP-TRANSACTIONS.md`.
- [x] Добавить recovery для `recovery_pending` транзакций.
- [x] Добавить журнал tx-событий.

Критерий готовности:

- при ошибке в середине плана состояние корректно откатывается.

## Блок D. QGIS Adapter Layer (P0)

Ожидаемый результат: единый адаптер исполнения операций в QGIS.

- [x] Реализовать Mode A (через открытый QGIS / plugin bridge).
- [x] Реализовать Mode B (через `qgis_process` для headless шагов).
- [x] Реализовать адаптеры для `native:*` алгоритмов из allowlist.
- [x] Добавить контроль CRS/единиц перед каждой гео-операцией.
- [x] Добавить безопасный timeout + retry для внешних вызовов.

Критерий готовности:

- split/fix/snap/difference/translate/validate выполняются воспроизводимо в обоих режимах (где применимо).

## Блок E. Реализация 12 MCP Tools (P0)

Ожидаемый результат: полный набор инструментов MVP по контракту.

- [x] `project_open`
- [x] `project_state`
- [x] `layer_catalog`
- [x] `intent_to_plan`
- [x] `plan_preview`
- [x] `plan_validate`
- [x] `plan_execute`
- [x] `topology_validate`
- [x] `variant_create`
- [x] `variant_compare`
- [x] `git_snapshot`
- [x] `export_result`

Критерий готовности:

- каждый tool имеет контрактные тесты и обработку ошибок по spec.

## Блок F. Plan IR Engine (P0)

Ожидаемый результат: валидируемый и исполняемый plan-пайплайн.

- [x] Подключить `4114/QGIS/PLAN-IR-SCHEMA.json` в runtime.
- [x] Реализовать parser/validator Plan IR.
- [x] Реализовать dependency resolution между шагами (`depends_on`).
- [x] Реализовать step executor + postchecks.
- [x] Реализовать dry-run режим на уровне execution graph.

Критерий готовности:

- невалидный план блокируется; валидный выполняется и протоколируется.

## Блок G. Validation & Ruleset Engine (P0)

Ожидаемый результат: обязательные кадастровые guardrails.

- [x] Реализовать ruleset loader по `4114/QGIS/MCP-REGULATORY-RULES.md`.
- [x] Реализовать hard/soft validation pipeline.
- [x] Реализовать topology checks (overlap/gap/self-intersection).
- [x] Реализовать проверку доступа к дороге для лотов.
- [x] Реализовать проверку ограничений по площади/дистанциям.

Критерий готовности:

- hard violation блокирует commit.

## Блок H. Planner & Intent Workflow (P1)

Ожидаемый результат: перевод пользовательского текста в исполняемый план.

- [x] Реализовать intent parser (ключевые параметры: N лотов, ширина дороги, отступы, коммуникации).
- [x] Реализовать генерацию Plan IR шаблонов для основных сценариев.
- [x] Реализовать механизм `missing_inputs` + уточняющие вопросы.
- [x] Реализовать preview summary (оценка изменений до commit).

Критерий готовности:

- сценарии “раздели на N + дорога” и “сдвинь границу на X м” формируют валидные планы.

## Блок I. Variant Engine и отчеты (P1)

Ожидаемый результат: объективное сравнение вариантов.

- [x] Реализовать ветвление вариантов (`variant_create`).
- [x] Реализовать расчет метрик по `4114/QGIS/MCP-VARIANT-REPORT.md`.
- [x] Реализовать итоговый score и tie-breakers.
- [x] Реализовать JSON + Markdown отчеты сравнения.

Критерий готовности:

- система стабильно выбирает winner на одинаковом наборе входов.

## Блок J. Security + HITL реализация (P1)

Ожидаемый результат: защищенный режим выполнения с подтверждениями риска.

- [x] Реализовать role-based authorization (`read_only`/`editor`/`admin`).
- [x] Реализовать default deny для `execute_code`.
- [x] Реализовать allowlist processing algorithms.
- [x] Реализовать HITL confirmation token flow.
- [x] Реализовать полный audit trail.

Критерий готовности:

- high-risk операции не проходят без подтверждения.

## Блок K. Artifacts + Git Integration (P1)

Ожидаемый результат: воспроизводимость и откаты на уровне проекта.

- [x] Реализовать `git_snapshot` с проверкой dirty state.
- [x] Реализовать единый layout артефактов (`artifacts/<plan_id>/...`).
- [x] Реализовать экспорт в gpkg/geojson/qgs.
- [x] Реализовать привязку артефактов к `plan_id` и `transaction_id`.

Критерий готовности:

- каждое выполнение оставляет полный trace + экспорт.

## Блок L. Deployment (Local -> Server) (P2)

Ожидаемый результат: переносимый запуск без ручных костылей.

- [x] Реализовать local profile (Mac + open QGIS).
- [x] Реализовать server profile (headless path где возможно).
- [x] Подготовить backup/restore скрипты.
- [x] Добавить healthchecks и smoke script.

Критерий готовности:

- локальный запуск и перенос на сервер документированы и повторяемы.

## Блок M. QA, CI и приемка MVP (P0/P1)

Ожидаемый результат: проверяемое качество и готовность к старту эксплуатации.

- [x] Подключить unit/integration/e2e suites по `4114/QGIS/MCP-TEST-PLAN.md`.
- [x] Подключить smoke/regression pipeline.
- [x] Прогнать 5 эталонных сценариев из `4114/QGIS/testdata/`.
- [x] Проверить выполнение SLO/SLA из `4114/QGIS/MCP-QGIS-CONCEPT.md`.
- [x] Подготовить MVP release checklist.

Критерий готовности:

- все критичные тесты зелёные, критерии приемки достигнуты.

## 5. Последовательность выполнения

- [x] Шаг 1: Блоки A+B+C
- [x] Шаг 2: Блоки D+E+F+G
- [x] Шаг 3: Блоки H+I+J+K
- [x] Шаг 4: Блоки L+M

## 6. Definition of Done (MVP)

- [x] Все P0 блоки завершены
- [x] Не менее 80% unit coverage
- [x] Все e2e критичные сценарии пройдены
- [x] Есть rollback и audit trace для каждого `plan_execute`
- [x] SLO/SLA достигнуты
- [x] Документация запуска и эксплуатации завершена

## 7. Журнал статуса

2026-02-12:

- Создан `MCP-QGIS-TASKS.md` как основной execution-план реализации MVP.
- Стартовая фаза: planning complete, implementation not started.

2026-02-12 (итерация 1):

- Выполнены блоки `A`, `B`, `C` (bootstrap, API envelope/validation, session-lock-transaction core).
- Добавлен рабочий сервер с healthcheck и endpoint `/tool`.
- Реализованы 12 инструментов MVP на уровне каркаса и базовой логики.
- Добавлены тесты; статус: `10 passed`.

2026-02-12 (итерация 2):

- Выполнены блоки `E`, `F`, `G` (12 tools, Plan IR engine, ruleset/validation pipeline).
- По блоку `D` выполнены headless mode B + allowlist + CRS check + timeout/retry.
- В блоке `D` остался незакрытым пункт по полноценному `Mode A` через desktop plugin bridge.
- Расширен тестовый контур; статус: `20 passed`.

2026-02-12 (итерация 3):

- Закрыт блок `D`: добавлен `Mode A` plugin bridge с timeout/retry и тестом подключения.
- Закрыты блоки `H`, `I`, `J`, `K`: intent planner + templates/missing_inputs, variant scoring/reports, RBAC/HITL/audit, artifact binding/export.
- Закрыт блок `L`: профили `local/server`, скрипты `backup/restore`, smoke-check и deployment документация.
- Закрыт блок `M`: добавлены unit/integration/e2e/regression наборы, CI pipeline, прогон 5 сценариев из `testdata`, SLO/SLA проверки, release checklist.
- Итог тестов: `44 passed`, coverage `82%`, smoke: `ok`.
