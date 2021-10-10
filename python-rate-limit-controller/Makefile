PYTHON ?= poetry run python

lint:
	$(PYTHON) -m black --check --diff .
	$(PYTHON) -m isort --check --diff .
	$(PYTHON) -m pylint ./src

lint/fix:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

mypy:
	$(PYTHON) -m mypy .
