#!/bin/bash
set -ev

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

env

#
# Skip Install if Python 2.7 or PyPy and not a PR
#
if [ "${TRAVIS_PULL_REQUEST}" == "false" ] && [ "${TRAVIS_BRANCH}" != "master" ]; then
    echo "Regular Push (not PR) on non-master branch:"
    echo "TRAVIS_PULL_REQUEST: ${TRAVIS_PULL_REQUEST}"
    echo "TRAVIS_BRANCH: ${TRAVIS_BRANCH}"
    if [ "${TRAVIS_PYTHON_VERSION}" == "2.7" ]; then
        echo "Skipping Python 2.7"
        exit 0
    fi
    if [ "${TRAVIS_PYTHON_VERSION}" == "pypy" ]; then
        echo "Skipping Python PyPy"
        exit 0
    fi
    if [ "${PYSMT_SOLVER}" == "all" ]; then
        echo "Skipping 'all' configuration"
        exit 0
    fi
    # if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
    #     echo "Skipping MacOSX build"
    #     exit 0
    # fi
fi

function brew_install_or_upgrade {
    brew install "$1" || (brew upgrade "$1" && brew cleanup "$1")
}

if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
    ulimit -n 4096
    ulimit -a
    brew update
    brew bundle
    brew_install_or_upgrade python
    brew_install_or_upgrade openssl
    brew_install_or_upgrade readline
    brew_install_or_upgrade swig
    brew_install_or_upgrade gperf

    brew_install_or_upgrade mpfr
    brew_install_or_upgrade libmpc
    brew_install_or_upgrade gmp

    brew_install_or_upgrade pyenv
    brew_install_or_upgrade pyenv-virtualenv

    brew_install_or_upgrade readline
    brew_install_or_upgrade xz
    brew_install_or_upgrade zlib

    brew_install_or_upgrade libffi
    brew_install_or_upgrade ncurses

    brew_install_or_upgrade glib
    brew_install_or_upgrade gobject-introspection
    brew_install_or_upgrade py3cairo
    brew_install_or_upgrade gtk+3
    brew_install_or_upgrade gst-plugins-base
    brew_install_or_upgrade gst-plugins-bad
    brew_install_or_upgrade gst-plugins-ugly
    brew_install_or_upgrade gst-plugins-good
    # brew_install_or_upgrade pygobject3 --with-libffi
    brew_install_or_upgrade pygobject3

    env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install ${TRAVIS_PYTHON_VERSION}

    pyenv virtualenv ${TRAVIS_PYTHON_VERSION} venv

    eval "$(pyenv init -)"
    pyenv activate venv
fi

# Check that the correct version of Python is running.
python ${DIR}/check_python_version.py "${TRAVIS_PYTHON_VERSION}"
