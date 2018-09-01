#!/usr/bin/env bash

env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.7.0

# pyenv virtualenv 3.7.0 pocketsphinx-build37

PYENV_DEBUG=1 pyenv virtualenv --system-site-packages 3.7.0 pocketsphinx-build37
