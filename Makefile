.PHONY: all venv run test test-only clean

all: venv

venv: .venv/bin/python
.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install -e .

run: venv
	.venv/bin/python sokoban.py

test: venv
	.venv/bin/python -m tests.qa

# Pattern subset: make test-only PAT=undo
test-only: venv
	.venv/bin/python -m tests.qa $(PAT)

perf: venv
	.venv/bin/python -m tests.perf

clean:
	rm -rf __pycache__ */__pycache__ tests/out/*.svg
