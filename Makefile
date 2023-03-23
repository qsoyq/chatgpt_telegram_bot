.PHONY: default format mypy test precommit

default: format

format: refactor precommit

refactor:
	@yapf -r -i . 
	@isort . 
	@pycln -a .

precommit:
	@pre-commit install
	@pre-commit run --all-file

mypy:
	@mypy app

test:
	PYTHONPATH=. pytest tests
