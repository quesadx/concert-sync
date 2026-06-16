.PHONY: test build build-server build-client run-server run-client clean

test:
	uv sync --group dev --group pyside6 && uv run pytest tests/

build:
	bash scripts/build_mac.sh both

build-server:
	bash scripts/build_mac.sh server

build-client:
	bash scripts/build_mac.sh client

run-server:
	uv run python main.py

run-client:
	uv sync --group pyside6 && uv run python -m frontend_pyside6 --mode client

run-dashboard:
	uv sync --group pyside6 && uv run python -m frontend_pyside6 --mode dashboard

clean:
	rm -rf build/ dist/ .venv-build-mac/
