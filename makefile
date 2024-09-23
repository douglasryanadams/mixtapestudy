
.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt -r requirements-test.txt

.PHONY: init
init: .venv/bin/python

.PHONY: clean
clean:
	rm -rf .venv

.PHONY: tidy
tidy:
	.venv/bin/ruff check --fix mixtapestudy
	.venv/bin/ruff format mixtapestudy

.PHONY: lint
lint:
	.venv/bin/ruff check mixtapestudy
	@# Pyright's quirky about discovering the virtual environment for resolving dependencies
	@# and activating the virtual environment was easier than understanding the config for now.
	source .venv/bin/activate && .venv/bin/pyright

.PHONY: test
test:
	.venv/bin/python -m pytest test

.PHONY: check
check: .venv/bin/python tidy lint test

.PHONY: run
run:
	trap 'docker-compose down --volumes --remove-orphans' EXIT; docker-compose up --build

.PHONY: dev
dev:
	OAUTH_REDIRECT_BASE_URL='http://127.0.0.1:5000' DATABASE_URL='sqlite:///dev.db' \
		.venv/bin/flask --app mixtapestudy.app run --debug
