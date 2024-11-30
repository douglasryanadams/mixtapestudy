
.venv/bin/python: requirements.txt requirements-test.txt
	python3.11 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt -r requirements-test.txt

.PHONY: init
init: .venv/bin/python

.PHONY: clean
clean:
	rm -rf .venv

.PHONY: tidy
tidy:
	.venv/bin/ruff check --fix mixtapestudy
	.venv/bin/ruff check --fix alembic
	.venv/bin/ruff check --fix test
	.venv/bin/ruff format mixtapestudy
	.venv/bin/ruff format alembic
	.venv/bin/ruff format test

.PHONY: lint
lint:
	.venv/bin/ruff check mixtapestudy
	.venv/bin/ruff check alembic
	.venv/bin/ruff check test

.PHONY: test
test:
	.venv/bin/python -m pytest test

.PHONY: revision
revision:
	trap 'docker compose logs --timestamps --no-color > docker.log && docker compose down --volumes --remove-orphans' EXIT; \
	bash -c "docker compose up --build --detach migration_done && DATABASE_URL='postgresql://local:admin@localhost:5432/mixtapestudy' .venv/bin/alembic revision --autogenerate"


.PHONY: check
check: .venv/bin/python tidy lint test

.PHONY: run
run:
	trap 'docker compose down --volumes --remove-orphans' EXIT; docker compose up --build --timestamps

.PHONY: dev
dev:
	trap 'docker compose logs --timestamps --no-color > docker.log && docker compose down --volumes --remove-orphans' EXIT; \
	bash -c "docker compose up --build --detach migration_done && \
		SESSION_SECRET='WP9zwHnJ' \
		OAUTH_REDIRECT_BASE_URL='http://127.0.0.1:5000' \
		DATABASE_URL='postgresql://local:admin@localhost:5432/mixtapestudy' \
		LOG_FILE='./dev_mixtapestudy.log' \
		RECOMMENDATION_SERVICE='listenbrainz' \
		.venv/bin/flask --app mixtapestudy.app run --debug"
