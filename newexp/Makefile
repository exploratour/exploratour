

help:
	@echo "Usage:"
	@echo
	@echo "make run           Run the server"
	@echo "make fmt           Format the code"
	@echo


run: .venv/stampfile
	FLASK_APP=exploratour FLASK_ENV=development .venv/bin/flask run

fmt: .venv/stampfile
	.venv/bin/black config.py exploratour import_export

.venv/stampfile:
	rm -rf .venv
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	touch $@


.PHONY: help run
