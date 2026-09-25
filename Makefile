.PHONY: up down logs test build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	docker compose --profile test run --rm --build tests

build:
	docker compose build
