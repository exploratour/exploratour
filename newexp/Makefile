

help:
	@echo "Usage:"
	@echo
	@echo "make run           Run the server"
	@echo "make fmt           Format the code"
	@echo


run: .venv/stampfile
	FLASK_APP=exploratour FLASK_ENV=development .venv/bin/flask run -h 0.0.0.0

fmt: .venv/stampfile
	.venv/bin/black config.py exploratour import_export

import: .venv/stampfile
	PYTHONPATH=. .venv/bin/python import_export/load_json.py ../web/collections.jsonl ../web/records.jsonl 1


.venv/stampfile:
	rm -rf .venv
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	touch $@


.PHONY: help run
