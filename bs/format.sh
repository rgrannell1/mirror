#!/bin/bash

find . -name "*.py" -exec autopep8 --in-place --aggressive --aggressive {} +
yapf --in-place --recursive .
