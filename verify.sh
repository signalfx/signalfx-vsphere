#!/usr/bin/env bash

set -e

flake8 --max-line-length=120 --exclude=tests/

if [ "$?" -ne 0 ]; then
    exit 1;
fi

cd tests/
python3 -m unittest test_suite.py