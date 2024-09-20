
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
	.venv/bin/ruff check --fix mock-spotify
	.venv/bin/ruff format mixtapestudy
	.venv/bin/ruff format mock-spotify

.PHONY: lint
lint:
	.venv/bin/ruff check mixtapestudy
	.venv/bin/ruff check mock-spotify

.PHONY: test
test:
	.venv/bin/pytest test

.PHONY: check
check: .venv/bin/python tidy lint test

.PHONY: run
run:
	trap 'docker-compose down --volumes --remove-orphans' EXIT; docker-compose up --build
