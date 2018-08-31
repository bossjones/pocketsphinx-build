#!/bin/bash
set -ev

# if [ "${YCM_BENCHMARK}" == "true" ]; then
#   ./benchmark.py
# elif [ "${YCM_CLANG_TIDY}" == "true" ]; then
#   ./build.py --clang-completer --clang-tidy --quiet --no-regex
# else
#   ./run_tests.py
# fi

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

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

    if [ "${PS_BUILD_SOLVER}" == "all" ]; then
        echo "Skipping 'all' configuration"
        exit 0
    fi
    # if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
    #     echo "Skipping MacOSX build"
    #     exit 0
    # fi
fi

if [ "${TRAVIS_OS_NAME}" == "osx" ]; then
    eval "$(pyenv init -)"
    pyenv activate venv
fi
echo "Check that the correct version of Python is running"
python ${DIR}/check_python_version.py "${TRAVIS_PYTHON_VERSION}"

# #
# # Run the test suite
# #  * Coverage is enabled only on master / all
# if [ "${TRAVIS_BRANCH}" == "master" ] && [ "${PS_BUILD_SOLVER}" == "all" ];
# then
#     # python -m nose pysmt -v # --with-coverage --cover-package=pysmt
# else
#     # python -m nose pysmt -v
# fi

# #
# # Test examples in examples/ folder
# #
# if [ "${PS_BUILD_SOLVER}" == "all" ];
# then
#     python install.py --msat --conf --force;
#     cp -v $(find ~/.smt_solvers/ -name mathsat -type f) /tmp/mathsat;
#     (for ex in `ls examples/*.py`; do echo $ex; python $ex || exit $?; done);
# fi
