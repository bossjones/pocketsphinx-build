#!/usr/bin/env bash

env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.7.0

# pyenv virtualenv 3.7.0 pocketsphinx-build37

PYENV_DEBUG=1 pyenv virtualenv --system-site-packages 3.7.0 pocketsphinx-build37

pyenv activate pocketsphinx-build37

env PKG_CONFIG_PATH="/usr/local/opt/libffi/lib/pkgconfig" pip install pygobject==3.28.3 ptpython black isort
