# MCP-QGIS

MCP-сервис и QGIS-плагин для управления геооперациями из LLM (через MCP) с фокусом на кадастровые сценарии.

![QGIS + MCP screenshot](docs/assets/qgis-mcp-screenshot.png)

## Что в репозитории

- `mcp_qgis/` — сервер, инструменты, адаптеры.
- `qgis_plugin/mcp_qgis_bridge/` — плагин-мост QGIS (Mode A).
- `docs/` — инструкции по интеграции и запуску.
- `tests/` — unit/integration/e2e/regression тесты.
- `PLANS/` — рабочие планы и дорожная карта.
- `scripts/` — smoke/backup/restore/launcher скрипты.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Проверка окружения:

```bash
mcp-qgis check-config
mcp-qgis doctor
```

Локальный запуск MCP HTTP-сервера:

```bash
mcp-qgis run
# health: GET  http://127.0.0.1:8765/health
# tool:   POST http://127.0.0.1:8765/tool
```

Запуск с профилем:

```bash
set -a
source deploy/profiles/local.env
set +a
mcp-qgis run
```

Тесты:

```bash
pytest --cov=mcp_qgis --cov-report=term-missing
```

Smoke:

```bash
./scripts/smoke.sh
```

## QGIS Bridge

Документация:

- `docs/PLUGIN-BRIDGE.md`
- `docs/CLIENT-INTEGRATION.md`

Запуск QGIS + MCP (удобный launcher):

```bash
./scripts/qgis_mcp_launcher.sh
```

## Backup/Restore

```bash
./scripts/backup_runtime.sh runtime runtime/backups
./scripts/restore_runtime.sh runtime/backups/<archive>.tar.gz .
```

## Публикация в GitHub

```bash
git remote add origin git@github.com:<your-user>/<your-repo>.git
git push -u origin main
```

Перед публикацией рекомендуется:

- Проверить `git status` (чистый рабочий каталог).
- Проверить отсутствие локальных секретов/приватных данных в коммитах.
- Прогнать `pytest`.

## Лицензия

MIT, см. `LICENSE`.
