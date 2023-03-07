.PHONY: default format mypy build push test tox precommit

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
	@mypy .

test:
	PYTHONPATH=. pytest tests

tox:
	docker volume create tox-testenv
	docker build -t tox-testenv -f ./docker/tox-testenv.Dockerfile .
	docker run -it --rm -v tox-testenv:/app/.tox tox-testenv
	if [ -n ${BARK_TOKEN} ]; then curl https://api.day.app/$(BARK_TOKEN)/$(PROJECT_NAME)%20tox%20success; fi;
