.PHONY: webserver
PROJECT := finja
GIT_HUB := "https://github.com/adfinis-sygroup/finja"

include pyproject/Makefile

FAIL_UNDER := 10

test_ext:
	make install
	finja -i
	finja finja
