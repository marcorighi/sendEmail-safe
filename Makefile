PYTHON ?= python3
PREFIX ?= /usr/local

.PHONY: test install uninstall

test:
	PYTHON="$(PYTHON)" ./run-tests.sh

install:
	PREFIX="$(PREFIX)" ./install.sh

uninstall:
	PREFIX="$(PREFIX)" ./uninstall.sh
