.PHONY: install install-root install-api install-web migrate seed dev dev-turbo dev-raw dev-api dev-web test test-api test-web lint clean

install: install-root install-api

install-root:
	yarn install

install-api:
	cd apps/api && yarn bootstrap

install-web: install-root

migrate:
	cd apps/api && yarn migrate

seed:
	cd apps/api && ./scripts/with-venv.sh uv run python -m ouroboros_api.seeds.bootstrap

dev: dev-turbo

dev-turbo:
	@echo "Starting api on :8000 and web on :3000 via Turborepo (Ctrl+C to stop both)"
	yarn turbo run dev --parallel

dev-raw:
	@echo "Starting api on :8000 and web on :3000 (Ctrl+C to stop both)"
	@(trap 'kill 0' INT; \
	  (cd apps/api && yarn dev) & \
	  (cd apps/web && yarn dev) & \
	  wait)

dev-api:
	cd apps/api && yarn dev

dev-web:
	yarn workspace ouroboros-web dev

test: test-api test-web

test-api:
	cd apps/api && yarn test

test-web:
	yarn workspace ouroboros-web test

lint:
	cd apps/api && yarn lint
	yarn workspace ouroboros-web lint

clean:
	rm -rf data/ouroboros.sqlite data/runs/* data/logs/* apps/web/.next apps/api/.pytest_cache .turbo
