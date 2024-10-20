#!/bin/bash
export OTEL_EXPORTER_CONSOLE=true
[ -e .venv/bin/activate ] && . .venv/bin/activate
uvicorn --reload --log-level=debug app:app
