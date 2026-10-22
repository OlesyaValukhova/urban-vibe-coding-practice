# AGENTS.md

Инструкции для ИИ-агента при работе с этим репозиторием.

## Что это за проект

`my_package` — учебный шаблон (boilerplate) Python-пакета для Института
дизайна и урбанистики (IDU). Используется в курсе «Технологии искусственного
интеллекта в урбанистике». Реальный код библиотеки пока минимален, задача —
освоить структуру пакета и рабочий процесс разработки с помощью ИИ.

## Структура

- `my_package/` — исходный код библиотеки (`my_module.py`, `__init__.py`).
- `tests/` — тесты на `pytest`.
- `examples/` — примеры использования, включая блокнот `my_example.ipynb`
  и данные в `examples/data/`.
- `docs/` — исходники документации (`sphinx`), собираются из `docs/source`.
- `Makefile` — готовые команды для окружения, установки и проверок.
- `pyproject.toml` — метаданные пакета, зависимости и группы `dev`/`tests`/`docs`.
- `.github/workflows/` — CI: тесты, документация, публикация в PyPI.

## Требования

- Python **3.10 или новее** (CI использует 3.10; локально — `.venv` на 3.12).
- Git, GNU Make.

## Команды

Виртуальное окружение (Windows, Git Bash):

```sh
make venv
source .venv/Scripts/activate
make install-dev
```

macOS/Linux:

```sh
make venv
source .venv/bin/activate
make install-dev
```

Проверка установки:

```sh
python -c "import my_package; print('Проект готов к работе')"
```

Прочее из `Makefile`:

- `make tests` — запустить `pytest`.
- `make lint` — `pylint` по `my_package`.
- `make format` — `isort` + `black`.
- `make build` — собрать пакет.

Все команды запускать из корня репозитория, где лежат `Makefile` и `pyproject.toml`.

## Правила для агента

- Следуй стилю существующего кода и структуре пакета.
- После изменений в `my_package` запускай `make tests`.
- Не коммить `.venv/`, `build/`, `dist/`.
- Примеры запускай в активированном окружении `.venv`.
