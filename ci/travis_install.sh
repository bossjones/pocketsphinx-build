#!/bin/bash
set -ev

# SOURCE: https://github.com/pysmt/pysmt/tree/fdf00e26081f92573198e1bdd3069d1a89b13b6e/ci

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

#
# Skip Install if Python 2.7 or PyPy and not a PR
#
if [ "${TRAVIS_PULL_REQUEST}" == "false" ] && [ "${TRAVIS_BRANCH}" != "master" ]; then
    echo "Regular Push (not PR) on non-master branch:"
    if [ "${TRAVIS_PYTHON_VERSION}" == "2.7" ]; then
        echo "Skipping Python 2.7"
        exit 0
    fi
    if [ "${TRAVIS_PYTHON_VERSION}" == "pypy" ]; then
        echo "Skipping Python PyPy"
        exit 0
    fi
    if [ "${PS_BUILD_SOLVER}" == "all" ]; then
        echo "Skipping 'all' configuration"
        exit 0
    fi
    if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
        echo "Skipping MacOSX build"
        exit 0
    fi
fi

if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
    eval "$(pyenv init -)"
    pyenv activate venv
fi
echo "Check that the correct version of Python is running"
python ${DIR}/check_python_version.py "${TRAVIS_PYTHON_VERSION}"

PIP_INSTALL="python -m pip install --upgrade"

$PIP_INSTALL configparser
$PIP_INSTALL six
$PIP_INSTALL cython
$PIP_INSTALL wheel

if [ "${PS_BUILD_SOLVER}" == "all" ] || [ "${PS_BUILD_SOLVER}" == *"btor"* ];
then
    $PIP_INSTALL python-coveralls;
fi
# Adding Python 3.6 library path to GCC search
if [ "${TRAVIS_PYTHON_VERSION}" == "3.6" ]; then
    export LIBRARY_PATH="/opt/python/3.6.3/lib:${LIBRARY_PATH}"
    export CPATH="/opt/python/3.6.3/include/python3.6m:${CPATH}"
fi


#
# Install Solvers
#

# On OSX install nosetest
if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
    $PIP_INSTALL pytest
fi
