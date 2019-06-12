SOURCES = pretf/pretf pretf.aws/pretf examples tests

.PHONY: all
all:
	isort --recursive $(SOURCES)
	black $(SOURCES)
	flake8 --ignore E501 $(SOURCES)
	mypy -m pretf.api -m pretf.cli -m pretf.collections -m pretf.log -m pretf.parser -m pretf.render
	cd examples; terraform fmt -recursive
	python -m unittest discover tests

clean:
	cd pretf; make clean
	cd pretf.aws; make clean
