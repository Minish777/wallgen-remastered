.PHONY: install dev run lint version clean test

install: ## Установить wallgen (системно, с --break-system-packages)
	pip install -e . --break-system-packages

dev: ## Установить в venv
	python3 -m venv .venv && . .venv/bin/activate && pip install -e .

run: ## Запустить wallgen
	wallgen

version: ## Показать версию
	wallgen --version

lint: ## Проверить синтаксис
	python3 -m py_compile wallgen/*.py

clean: ## Удалить виртуальное окружение и кэш
	rm -rf .venv __pycache__ wallgen/__pycache__
