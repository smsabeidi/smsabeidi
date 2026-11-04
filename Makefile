.PHONY: all verify contributions build test

all: build test

verify:
	python3 scripts/verify.py

contributions:
	python3 scripts/contributions.py

build:
	python3 scripts/build.py

test:
	python3 -m unittest discover -s tests
