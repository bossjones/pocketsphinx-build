#!/usr/bin/env python

# SOURCE: https://github.com/Valloric/pocketsphinx-build

# Passing an environment variable containing unicode literals to a subprocess
# on Windows and Python2 raises a TypeError. Since there is no unicode
# string in this script, we don't import unicode_literals to avoid the issue.
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from distutils import sysconfig
from shutil import rmtree
from tempfile import mkdtemp
import errno
import multiprocessing
import os
import os.path as p
import platform
import re
import shlex
import subprocess
import sys
import tarfile
import shutil
import hashlib
import tempfile
import argparse
import contextlib
import getpass
import io
import select
import stat
import time

# 3, 6, 5
PY_MAJOR, PY_MINOR, PY_PATCH = sys.version_info[ 0 : 3 ]
if not ( ( PY_MAJOR == 2 and PY_MINOR == 7 and PY_PATCH >= 1 ) or
         ( PY_MAJOR == 3 and PY_MINOR >= 4 ) or
         PY_MAJOR > 3 ):
  sys.exit( 'pocketsphinx-build requires Python >= 2.7.1 or >= 3.4; '
            'your version of Python is ' + sys.version )


PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY2:
    from six.moves.urllib.parse import urlparse
elif PY3:
    from urllib.parse import urlparse

USERNAME = getpass.getuser()
USERHOME = os.path.expanduser("~")
PREFIX = os.path.join(USERHOME, "uninstalled")
CHECKOUTROOT = os.path.join(USERHOME, "checkout")
PY_VERSION = "3.6"
PY_VERSION_FULL = "{}.5".format(PY_VERSION)



DIR_OF_THIS_SCRIPT = p.dirname( p.abspath( __file__ ) )
PATH_TO_ENVRC_BUILD = os.path.join(DIR_OF_THIS_SCRIPT + "/.envrc.build")
PATH_TO_ENVRC_RUN = os.path.join(DIR_OF_THIS_SCRIPT + "/.envrc.run")


import argparse
# import requests

NO_DYNAMIC_PYTHON_ERROR = (
  'ERROR: found static Python library ({library}) but a dynamic one is '
  'required. You must use a Python compiled with the {flag} flag. '
  'If using pyenv, you need to run the command:\n'
  '  export PYTHON_CONFIGURE_OPTS="{flag}"\n'
  'before installing a Python version.' )
NO_PYTHON_LIBRARY_ERROR = 'ERROR: unable to find an appropriate Python library.'

# Regular expressions used to find static and dynamic Python libraries.
# Notes:
#  - Python 3 library name may have an 'm' suffix on Unix platforms, for
#    instance libpython3.4m.so;
#  - the linker name (the soname without the version) does not always
#    exist so we look for the versioned names too;
#  - on Windows, the .lib extension is used instead of the .dll one. See
#    https://en.wikipedia.org/wiki/Dynamic-link_library#Import_libraries
STATIC_PYTHON_LIBRARY_REGEX = '^libpython{major}\.{minor}m?\.a$'
DYNAMIC_PYTHON_LIBRARY_REGEX = """
  ^(?:
  # Linux, BSD
  libpython{major}\.{minor}m?\.so(\.\d+)*|
  # OS X
  libpython{major}\.{minor}m?\.dylib|
  # Windows
  python{major}{minor}\.lib|
  # Cygwin
  libpython{major}\.{minor}\.dll\.a
  )$
"""

BUILD_ERROR_MESSAGE = (
  'ERROR: the build failed.\n\n'
  'NOTE: it is *highly* unlikely that this is a bug but rather\n'
  'that this is a problem with the configuration of your system\n'
  'or a missing dependency. Please carefully read CONTRIBUTING.md\n'
  'and if you\'re sure that it is a bug, please raise an issue on the\n'
  'issue tracker, including the entire output of this script\n'
  'and the invocation line used to run it.' )

BUILD_SPHINXBASE = """
jhbuild run ./autogen.sh --prefix={PREFIX}; \
jhbuild run ./configure --prefix={PREFIX}; \
jhbuild run make clean all; \
jhbuild run make install
"""

BUILD_POCKETSPHINX = """
jhbuild run ./autogen.sh --prefix={PREFIX}; \
jhbuild run ./configure --prefix={PREFIX} --with-python; \
jhbuild run make clean all; \
jhbuild run make install
"""

repo_git_dicts = {
    "sphinxbase": {
        "repo": "https://github.com/cmusphinx/sphinxbase.git",
        "branch": "74370799d5b53afc5b5b94a22f5eff9cb9907b97",
        "compile-commands": BUILD_SPHINXBASE,
        "folder": "sphinxbase",
    },
    "pocketsphinx": {
        "repo": "https://github.com/cmusphinx/pocketsphinx.git",
        "branch": "68ef5dc6d48d791a747026cd43cc6940a9e19f69",
        "compile-commands": BUILD_POCKETSPHINX,
        "folder": "pocketsphinx",
    },
}


ENVRC_BUILD_TEMPLATE = """
export CFLAGS = '{CFLAGS}'
export PYTHON = 'python'
export GSTREAMER = '1.0'
export ENABLE_PYTHON3 = 'yes'
export ENABLE_GTK = 'yes'
export PYTHON_VERSION = '{PYTHON_VERSION}'
export PATH = '{PATH}'
export LD_LIBRARY_PATH = '{LD_LIBRARY_PATH}'
export PYTHONPATH = '{PYTHONPATH}'
export PKG_CONFIG_PATH = '{PKG_CONFIG_PATH}'
export XDG_DATA_DIRS = '{XDG_DATA_DIRS}'
export XDG_CONFIG_DIRS = '{XDG_CONFIG_DIRS}'
export CC = 'gcc'
export PROJECT_HOME = '{PROJECT_HOME}'
export PYTHONSTARTUP = '{PYTHONSTARTUP}'
"""

ENVRC_RUN_TEMPLATE = """
export CFLAGS = '{CFLAGS}'
export PYTHON = 'python'
export GSTREAMER = '1.0'
export ENABLE_PYTHON3 = 'yes'
export ENABLE_GTK = 'yes'
export PYTHON_VERSION = '{PYTHON_VERSION}'
export PATH = '{PATH}'
export LD_LIBRARY_PATH = '{LD_LIBRARY_PATH}'
export PYTHONPATH = '{PYTHONPATH}'
export PKG_CONFIG_PATH = '{PKG_CONFIG_PATH}'
export XDG_DATA_DIRS = '{XDG_DATA_DIRS}'
export XDG_CONFIG_DIRS = '{XDG_CONFIG_DIRS}'
export CC = 'gcc'
export PROJECT_HOME = '{PROJECT_HOME}'
export PYTHONSTARTUP = '{PYTHONSTARTUP}'
"""



# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------

# SOURCE: https://github.com/ARMmbed/mbed-cli/blob/f168237fabd0e32edcb48e214fc6ce2250046ab3/test/util.py
# Process execution
class ProcessException(Exception):
    pass


class Console:  # pylint: disable=too-few-public-methods

    quiet = False

    @classmethod
    def message(cls, str_format, *args):
        if cls.quiet:
            return

        if args:
            print(str_format % args)
        else:
            print(str_format)

        # Flush so that messages are printed at the right time
        # as we use many subprocesses.
        sys.stdout.flush()


def pquery(command, stdin=None, **kwargs):
    # SOURCE: https://github.com/ARMmbed/mbed-cli/blob/f168237fabd0e32edcb48e214fc6ce2250046ab3/test/util.py
    # Example:
    print(" ".join(command))
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    )
    stdout, _ = proc.communicate(stdin)

    if proc.returncode != 0:
        raise ProcessException(proc.returncode)

    return stdout.decode("utf-8")


# Directory navigation
@contextlib.contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(prevdir)


def scm(dir=None):
    if not dir:
        dir = os.getcwd()

    if os.path.isdir(os.path.join(dir, ".git")):
        return "git"
    elif os.path.isdir(os.path.join(dir, ".hg")):
        return "hg"


def _popen(cmd_arg):
    devnull = open("/dev/null")
    cmd = subprocess.Popen(cmd_arg, stdout=subprocess.PIPE, stderr=devnull, shell=True)
    retval = cmd.stdout.read().strip()
    err = cmd.wait()
    cmd.stdout.close()
    devnull.close()
    if err:
        raise RuntimeError("Failed to close %s stream" % cmd_arg)
    return retval


def _popen_stdout(cmd_arg, cwd=None):
    # if passing a single string, either shell mut be True or else the string must simply name the program to be executed without specifying any arguments
    cmd = subprocess.Popen(
        cmd_arg,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        bufsize=4096,
        shell=True,
    )
    Console.message("BEGIN: {}".format(cmd_arg))
    # output, err = cmd.communicate()

    for line in iter(cmd.stdout.readline, b""):
        # Print line
        _line = line.rstrip()
        Console.message(">>> {}".format(_line.decode("utf-8")))

    Console.message("END: {}".format(cmd_arg))


# Higher level functions
def remove(path):
    def remove_readonly(func, path, _):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(path, onerror=remove_readonly)


def move(src, dst):
    shutil.move(src, dst)


def copy(src, dst):
    shutil.copytree(src, dst)


def clone_all():
    for k, v in repo_git_dicts.items():
        k_full_path = os.path.join(CHECKOUTROOT, k)
        git_clone(v["repo"], k_full_path, sha=v["branch"])
# Clone everything that doesnt exist
def git_clone(repo_url, dest, sha="master"):
    # First check if folder exists
    if not os.path.exists(dest):
        # check if folder is a git repo
        if scm(dest) != "git":
            clone_cmd = "git clone {repo} {dest}".format(repo=repo_url, dest=dest)
            _popen_stdout(clone_cmd)

            # CD to directory
            with cd(dest):
                checkout_cmd = "git checkout {sha}".format(sha=sha)
                _popen_stdout(checkout_cmd)

def get_package_dict(package_to_build):
    if package_to_build in repo_git_dicts:
        return repo_git_dicts

def whoami():
    whoami = _popen("who")
    return whoami


# Some utility functions used here and in custom files:


def environ_append(key, value, separator=" ", force=False):
    old_value = os.environ.get(key)
    if old_value is not None:
        value = old_value + separator + value
    os.environ[key] = value


def environ_prepend(key, value, separator=" ", force=False):
    old_value = os.environ.get(key)
    if old_value is not None:
        value = value + separator + old_value
    os.environ[key] = value


def environ_remove(key, value, separator=":", force=False):
    old_value = os.environ.get(key)
    if old_value is not None:
        old_value_split = old_value.split(separator)
        value_split = [x for x in old_value_split if x != value]
        value = separator.join(value_split)
    os.environ[key] = value


def environ_set(key, value):
    os.environ[key] = value


def environ_get(key):
    return os.environ.get(key)


def path_append(value):
    if os.path.exists(value):
        environ_append("PATH", value, ":")


def path_prepend(value, force=False):
    if os.path.exists(value):
        environ_prepend("PATH", value, ":", force)

# Call either setup_debug or setup_release in your .jhbuildrc-custom
# or other customization file to get the compilation flags.
def setup_debug():
    environ_set("CFLAGS", "-fPIC -O0 -ggdb -fno-inline -fno-omit-frame-pointer")
    environ_set("CXXFLAGS", "-fPIC -O0 -ggdb -fno-inline -fno-omit-frame-pointer")
    # environ_prepend('CFLAGS', '-O0 -g')
    # environ_prepend('CXXFLAGS', '-O0 -g')


def setup_path_env():
    # print("before")
    # dump_env_var("PATH")
    # /home/pi/jhbuild/bin
    # /home/pi/jhbuild/sbin
    # /home/pi/jhbuild/bin
    # /home/pi/jhbuild/sbin
    # /home/pi/.pyenv/shims
    # ~/.pyenv/bin/
    # ~/.bin
    # /home/pi/.local/bin
    # /home/pi/.rbenv/shims
    # /home/pi/.rbenv/bin
    # /home/pi/.nvm/versions/node/v8.7.0/bin
    # /usr/lib64/ccache
    # /usr/local/bin
    # /usr/bin
    # /usr/local/sbin
    # /usr/sbin
    # /home/pi/.rvm/bin
    # /home/pi/.go/bin
    # /home/pi/go/bin
    path_prepend("/usr/sbin")
    path_prepend("/usr/local/sbin")
    path_prepend("/usr/bin")
    path_prepend("/usr/local/bin")
    path_prepend("/usr/lib64/ccache")
    path_prepend("{}/.rbenv/bin".format(USERHOME))
    path_prepend("{}/.rbenv/shims".format(USERHOME))
    path_prepend("{}/.local/bin".format(USERHOME))
    path_prepend("{}/.bin".format(USERHOME))
    path_prepend("{}/.pyenv/bin".format(USERHOME), True)
    path_prepend("{}/.pyenv/shims".format(USERHOME), True)
    Console.message("AFTER")
    dump_env_var("PATH")


def setup_python_version():
    environ_set("PYTHON_VERSION", PY_VERSION)


def setup_ld_library_path():
    # /home/pi/jhbuild/lib
    # /home/pi/jhbuild/lib
    # /usr/lib
    environ_prepend("LD_LIBRARY_PATH", "/usr/lib", ":")
    environ_prepend("LD_LIBRARY_PATH", "/usr/local/lib", ":")
    environ_prepend("LD_LIBRARY_PATH", "{}/uninstalled/lib".format(USERHOME), ":")
    Console.message("AFTER")
    dump_env_var("LD_LIBRARY_PATH")


def setup_pythonpath():
#     # /home/pi/.pyenv/versions/3.5.2/lib/python3.5/site-packages
#     # /home/pi/jhbuild/lib/python3.5/site-packages
#     # /usr/lib/python3.5/site-packages
#     environ_prepend(
#         "PYTHONPATH", "/usr/lib/python{}/site-packages".format(PY_VERSION), ":"
#     )
#     environ_prepend(
#         "PYTHONPATH",
#         "{}/jhbuild/lib/python{}/site-packages".format(USERHOME, PY_VERSION),
#         ":",
#     )
#     environ_prepend(
#         "PYTHONPATH",
#         "{}/.pyenv/versions/{}/lib/python{}/site-packages".format(
#             USERHOME, PY_VERSION_FULL, PY_VERSION
#         ),
#         ":",
#     )
#     Console.message("AFTER")
    dump_env_var("PYTHONPATH")

def write_envrc():
    rendered = render_envrc_dry_run()
    with open(PATH_TO_ENVRC_BUILD, "w+") as fp:
        fp.write(rendered)


def render_envrc_dry_run():
    rendered = ENVRC_BUILD_TEMPLATE.format(
        PREFIX=environ_get("PREFIX"),
        CHECKOUTROOT=environ_get("CHECKOUTROOT"),
        CFLAGS=environ_get("CFLAGS"),
        PYTHON_VERSION=environ_get("PYTHON_VERSION"),
        PATH=environ_get("PATH"),
        LD_LIBRARY_PATH=environ_get("LD_LIBRARY_PATH"),
        PYTHONPATH=environ_get("PYTHONPATH"),
        PKG_CONFIG_PATH=environ_get("PKG_CONFIG_PATH"),
        XDG_DATA_DIRS=environ_get("XDG_DATA_DIRS"),
        XDG_CONFIG_DIRS=environ_get("XDG_CONFIG_DIRS"),
        PROJECT_HOME=environ_get("PROJECT_HOME"),
        PYTHONSTARTUP=environ_get("PYTHONSTARTUP"),
    )
    Console.message("----------------[render_envrc_dry_run]----------------")
    Console.message(rendered)

    return rendered


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def dump_env_var(var):
    Console.message("Env Var:{}={}".format(var, os.environ.get(var, "<EMPTY>")))

# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------

def OnMac():
  return platform.system() == 'Darwin'


def OnWindows():
  return platform.system() == 'Windows'


def OnCiService():
  return 'CI' in os.environ


def FindExecutableOrDie( executable, message ):
  path = FindExecutable( executable )

  if not path:
    sys.exit( "ERROR: Unable to find executable '{0}'. {1}".format(
      executable,
      message ) )

  return path


# On Windows, distutils.spawn.find_executable only works for .exe files
# but .bat and .cmd files are also executables, so we use our own
# implementation.
def FindExecutable( executable ):
  # Executable extensions used on Windows
  WIN_EXECUTABLE_EXTS = [ '.exe', '.bat', '.cmd' ]

  paths = os.environ[ 'PATH' ].split( os.pathsep )
  base, extension = os.path.splitext( executable )

  if OnWindows() and extension.lower() not in WIN_EXECUTABLE_EXTS:
    extensions = WIN_EXECUTABLE_EXTS
  else:
    extensions = ['']

  for extension in extensions:
    executable_name = executable + extension
    if not os.path.isfile( executable_name ):
      for path in paths:
        executable_path = os.path.join(path, executable_name )
        if os.path.isfile( executable_path ):
          return executable_path
    else:
      return executable_name
  return None


def PathToFirstExistingExecutable( executable_name_list ):
  for executable_name in executable_name_list:
    path = FindExecutable( executable_name )
    if path:
      return path
  return None


def NumCores():
  ps_build_cores = os.environ.get( 'ps_build_cores' )
  if ps_build_cores:
    return int( ps_build_cores )
  try:
    return multiprocessing.cpu_count()
  except NotImplementedError:
    return 1


def CheckCall( args, **kwargs ):
  quiet = kwargs.pop( 'quiet', False )
  status_message = kwargs.pop( 'status_message', None )

  if quiet:
    _CheckCallQuiet( args, status_message, **kwargs )
  else:
    _CheckCall( args, **kwargs )


def _CheckCallQuiet( args, status_message, **kwargs ):
  if not status_message:
    status_message = 'Running {}'.format( args[ 0 ] )

  # __future__ not appear to support flush= on print_function
  sys.stdout.write( status_message + '...' )
  sys.stdout.flush()

  with tempfile.NamedTemporaryFile() as temp_file:
    _CheckCall( args, stdout=temp_file, stderr=subprocess.STDOUT, **kwargs )

  print( "OK" )


def _CheckCall( args, **kwargs ):
  exit_message = kwargs.pop( 'exit_message', None )
  stdout = kwargs.get( 'stdout', None )

  try:
    subprocess.check_call( args, **kwargs )
  except subprocess.CalledProcessError as error:
    if stdout is not None:
      stdout.seek( 0 )
      print( stdout.read().decode( 'utf-8' ) )
      print( "FAILED" )

    if exit_message:
      sys.exit( exit_message )
    sys.exit( error.returncode )


def GetGlobalPythonPrefix():
  # In a virtualenv, sys.real_prefix points to the parent Python prefix.
  if hasattr( sys, 'real_prefix' ):
    return sys.real_prefix
  # In a pyvenv (only available on Python 3), sys.base_prefix points to the
  # parent Python prefix. Outside a pyvenv, it is equal to sys.prefix.
  if PY_MAJOR >= 3:
    return sys.base_prefix
  return sys.prefix


def GetPossiblePythonLibraryDirectories():
  prefix = GetGlobalPythonPrefix()

  if OnWindows():
    return [ p.join( prefix, 'libs' ) ]
  # On pyenv and some distributions, there is no Python dynamic library in the
  # directory returned by the LIBPL variable. Such library can be found in the
  # "lib" or "lib64" folder of the base Python installation.
  return [
    sysconfig.get_config_var( 'LIBPL' ),
    p.join( prefix, 'lib64' ),
    p.join( prefix, 'lib' )
  ]


def FindPythonLibraries():
  # EG. '/Users/malcolm/.pyenv/versions/3.6.5/include/python3.6m'
  include_dir = sysconfig.get_config_var( 'INCLUDEPY' )
  library_dirs = GetPossiblePythonLibraryDirectories()

  # Since pocketsphinx-build is compiled as a dynamic library, we can't link it to a Python
  # static library. If we try, the following error will occur on Mac:
  #
  #   Fatal Python error: PyThreadState_Get: no current thread
  #
  # while the error happens during linking on Linux and looks something like:
  #
  #   relocation R_X86_64_32 against `a local symbol' can not be used when
  #   making a shared object; recompile with -fPIC
  #
  # On Windows, the Python library is always a dynamic one (an import library to
  # be exact). To obtain a dynamic library on other platforms, Python must be
  # compiled with the --enable-shared flag on Linux or the --enable-framework
  # flag on Mac.
  #
  # So we proceed like this:
  #  - look for a dynamic library and return its path;
  #  - if a static library is found instead, raise an error with instructions
  #    on how to build Python as a dynamic library.
  #  - if no libraries are found, raise a generic error.
  dynamic_name = re.compile( DYNAMIC_PYTHON_LIBRARY_REGEX.format(
    major = PY_MAJOR, minor = PY_MINOR ), re.X )
  static_name = re.compile( STATIC_PYTHON_LIBRARY_REGEX.format(
    major = PY_MAJOR, minor = PY_MINOR ), re.X )
  static_libraries = []

  for library_dir in library_dirs:
    if not p.exists( library_dir ):
      continue

    # Files are sorted so that we found the non-versioned Python library before
    # the versioned one.
    for filename in sorted( os.listdir( library_dir ) ):
      if dynamic_name.match( filename ):
        return p.join( library_dir, filename ), include_dir

      if static_name.match( filename ):
        static_libraries.append( p.join( library_dir, filename ) )

  if static_libraries and not OnWindows():
    dynamic_flag = ( '--enable-framework' if OnMac() else
                     '--enable-shared' )
    sys.exit( NO_DYNAMIC_PYTHON_ERROR.format( library = static_libraries[ 0 ],
                                              flag = dynamic_flag ) )

  sys.exit( NO_PYTHON_LIBRARY_ERROR )


def CustomPythonCmakeArgs( args ):
  # The CMake 'FindPythonLibs' Module does not work properly.
  # So we are forced to do its job for it.
  if not args.quiet:
    print( 'Searching Python {major}.{minor} libraries...'.format(
      major = PY_MAJOR, minor = PY_MINOR ) )

  python_library, python_include = FindPythonLibraries()

  if not args.quiet:
    print( 'Found Python library: {0}'.format( python_library ) )
    print( 'Found Python headers folder: {0}'.format( python_include ) )

  return [
    '-DPYTHON_LIBRARY={0}'.format( python_library ),
    '-DPYTHON_INCLUDE_DIR={0}'.format( python_include )
  ]


def GetGenerator( args ):
  if args.ninja:
    return 'Ninja'
  if OnWindows():
    return 'Visual Studio {version}{arch}'.format(
        version = args.msvc,
        arch = ' Win64' if platform.architecture()[ 0 ] == '64bit' else '' )
  return 'Unix Makefiles'

def BuildPsBuildLib( cmake, cmake_common_args, script_args ):
  if script_args.build_dir:
    build_dir = os.path.abspath( script_args.build_dir )
    if not os.path.exists( build_dir ):
      os.makedirs( build_dir )
  else:
    build_dir = mkdtemp( prefix = 'ps_build_build_' )

  try:
    os.chdir( build_dir )

    configure_command = ( [ cmake ] + cmake_common_args +
                          GetCmakeArgs( script_args ) )
    configure_command.append( p.join( DIR_OF_THIS_SCRIPT, 'cpp' ) )

    CheckCall( configure_command,
               exit_message = BUILD_ERROR_MESSAGE,
               quiet = script_args.quiet,
               status_message = 'Generating pocketsphinx-build build configuration' )

    build_targets = [ 'ps_build_core' ]
    if script_args.core_tests:
      build_targets.append( 'ps_build_core_tests' )
    if 'PS_BUILD_BENCHMARK' in os.environ:
      build_targets.append( 'ps_build_core_benchmarks' )

    build_config = GetCMakeBuildConfiguration( script_args )

    for target in build_targets:
      build_command = ( [ cmake, '--build', '.', '--target', target ] +
                        build_config )
      CheckCall( build_command,
                 exit_message = BUILD_ERROR_MESSAGE,
                 quiet = script_args.quiet,
                 status_message = 'Compiling pocketsphinx-build target: {0}'.format(
                   target ) )

    if script_args.core_tests:
      RunPsBuildTests( script_args, build_dir )
    if 'PS_BUILD_BENCHMARK' in os.environ:
      RunPsBuildBenchmarks( build_dir )
  finally:
    os.chdir( DIR_OF_THIS_SCRIPT )

    if script_args.build_dir:
      print( 'The build files are in: ' + build_dir )
    else:
      rmtree( build_dir, ignore_errors = OnCiService() )

# SOURCE: https://github.com/seanfisk/fly-compiler/blob/e4448e380f2705c44849d08be00488385fe17897/scripts/build
# Utility functions
def brew(*args):
    brew_bin = FindBrew()
    return subprocess.check_output([brew_bin] + list(args)).rstrip()

def run_pkg_config(*args):
    return subprocess.check_output(['/usr/local/bin/pkg-config'] + list(args)).rstrip()

def get_brew_path_prefix():
    """To get brew path"""
    brew_bin = FindBrew()
    try:
        return subprocess.check_output([brew_bin, '--prefix'],
                                       universal_newlines=True).strip()
    except:
        return None

def brew_bundle():
    """Run brew bundle"""
    # CD to directory
    ROOT_DIR = os.path.abspath(os.path.join(DIR_OF_THIS_SCRIPT, os.pardir))
    with cd(ROOT_DIR):
        checkout_cmd = "brew bundle"
        _popen_stdout(checkout_cmd)

# SOURCE: https://github.com/seanfisk/fly-compiler/blob/e4448e380f2705c44849d08be00488385fe17897/scripts/build
###################### -------------------------
# # Get the path to the LLVM CMake modules.
# llvm_cmake_dir = join(
#     brew('--cellar', 'llvm' + ''.join(LLVM_VERSION_TUPLE[:2])),
#     '.'.join(LLVM_VERSION_TUPLE),
#     'lib',
#     'llvm-{}'.format('.'.join(LLVM_VERSION_TUPLE[:2])),
#     'share', 'llvm', 'cmake')
###################### -------------------------

def AddKegsToPath():
  # Bison and Flex are keg-only, which means they are not symlinked into `brew
  # --prefix'. We can access the current versions through the opt/ directory,
  # given by `brew --prefix FORMULA'.
  #
  # We find these and put them on the PATH for CMake to find.
  try:
      paths_var = os.environ['PATH']
  except KeyError:
      paths = []
  else:
      paths = paths_var.split(os.pathsep)
  for tool in ['flex', 'bison', 'swig', 'autoconf', 'automake', 'libtool', 'pkg-config']:
      paths.insert(0, os.path.join(brew('--prefix', tool), 'bin'))
  cmake_env = os.environ.copy()
  cmake_env['PATH'] = os.pathsep.join(paths)

# ----------------------------
# SOURCE: https://github.com/jmwhitfi/cffi/blob/2a16b7c274850bb485769b4a3b023652096f0182/setup.py

def _ask_pkg_config(resultlist, option, result_prefix='', sysroot=False, pkg_name='libffi'):
    pkg_config = os.environ.get('PKG_CONFIG','pkg-config')
    try:
        p = subprocess.Popen([pkg_config, option, pkg_name],
                             stdout=subprocess.PIPE)
    except OSError as e:
        if e.errno not in [errno.ENOENT, errno.EACCES]:
            raise
    else:
        t = p.stdout.read().decode().strip()
        p.stdout.close()
        if p.wait() == 0:
            res = t.split()
            # '-I/usr/...' -> '/usr/...'
            for x in res:
                assert x.startswith(result_prefix)
            res = [x[len(result_prefix):] for x in res]
            print('PKG_CONFIG:', option, res)

            sysroot = sysroot and os.environ.get('PKG_CONFIG_SYSROOT_DIR', '')
            if sysroot:
                # old versions of pkg-config don't support this env var,
                # so here we emulate its effect if needed
                res = [path if path.startswith(sysroot)
                            else sysroot + path
                         for path in res]
            #
            resultlist[:] = res

def use_pkg_config():
    # sources = ['c/_cffi_backend.c']
    # libraries = ['ffi']
    # include_dirs = ['/usr/include/ffi',
    #                 '/usr/include/libffi']    # may be changed by pkg-config
    # define_macros = []
    # library_dirs = []
    # extra_compile_args = []
    # extra_link_args = []

    if sys.platform == 'darwin' and os.path.exists('/usr/local/bin/brew'):
        use_homebrew_for_libffi()

    # _ask_pkg_config(include_dirs,       '--cflags-only-I', '-I', sysroot=True)
    # _ask_pkg_config(extra_compile_args, '--cflags-only-other')
    # _ask_pkg_config(library_dirs,       '--libs-only-L', '-L', sysroot=True)
    # _ask_pkg_config(extra_link_args,    '--libs-only-other')
    # _ask_pkg_config(libraries,          '--libs-only-l', '-l')

def use_homebrew_for_libffi():
    # We can build by setting:
    # PKG_CONFIG_PATH = $(brew --prefix libffi)/lib/pkgconfig
    with os.popen('brew --prefix libffi') as brew_prefix_cmd:
        prefix = brew_prefix_cmd.read().strip()
    pkgconfig = os.path.join(prefix, 'lib', 'pkgconfig')
    os.environ['PKG_CONFIG_PATH'] = (
        os.environ.get('PKG_CONFIG_PATH', '') + ':' + pkgconfig)
# ----------------------------

def get_gst_plugin_path():
    return run_pkg_config('--variable','pluginsdir','gstreamer-1.0')

def get_gstreamer_pkgconfig_path():
    base = run_pkg_config('--variable','prefix','gstreamer-1.0')
    return os.path.join(base, 'lib', 'pkgconfig')

def get_gstreamer_base_pkgconfig_path():
    base = run_pkg_config('--variable','prefix','gstreamer-base-1.0')
    return os.path.join(base, 'lib', 'pkgconfig')

def get_gstreamer_plugins_base_pkgconfig_path():
    base = run_pkg_config('--variable','prefix','gstreamer-plugins-base-1.0')
    return os.path.join(base, 'lib', 'pkgconfig')

# SOURCE: https://github.com/mengdaya/fuckshell/blob/c88b0792b8a2db3c181938af6c357662993a30c3/thefuck/specific/brew.py

def ParseArguments():
  parser = argparse.ArgumentParser()
  parser.add_argument( '--sphinxbase', action = 'store_true',
                       help = 'Compile sphinxbase' )
  parser.add_argument( '--pocketsphinx', action = 'store_true',
                       help = 'Compile pocketsphinx' )
  parser.add_argument( '--python3', action = 'store_true',
                       help = 'Enable python3 bindings.' )
  parser.add_argument( '--clean', action = 'store_true',
                       help = 'Run make clean in source folders' )
  parser.add_argument( '--render-dry-run', action = 'store_true',
                       help = 'Dump env config file' )
  parser.add_argument( '--brew-bundle', action = 'store_true',
                       help = 'Run brew bundle and install all dependencies' )
  # parser.add_argument( '--cs-completer', action = 'store_true',
  #                      help = 'Enable C# semantic completion engine.' )
  # parser.add_argument( '--go-completer', action = 'store_true',
  #                      help = 'Enable Go semantic completion engine.' )
  # parser.add_argument( '--rust-completer', action = 'store_true',
  #                      help = 'Enable Rust semantic completion engine.' )
  # parser.add_argument( '--java-completer', action = 'store_true',
  #                      help = 'Enable Java semantic completion engine.' ),
  # parser.add_argument( '--system-boost', action = 'store_true',
  #                      help = 'Use the system boost instead of bundled one. '
  #                      'NOT RECOMMENDED OR SUPPORTED!' )
  # parser.add_argument( '--system-libclang', action = 'store_true',
  #                      help = 'Use system libclang instead of downloading one '
  #                      'from llvm.org. NOT RECOMMENDED OR SUPPORTED!' )
  # parser.add_argument( '--msvc', type = int, choices = [ 14, 15 ],
  #                      default = 15, help = 'Choose the Microsoft Visual '
  #                      'Studio version (default: %(default)s).' )
  # parser.add_argument( '--ninja', action = 'store_true',
  #                      help = 'Use Ninja build system.' )
  parser.add_argument( '--all',
                       action = 'store_true',
                       help   = 'Enable all supported completers',
                       dest   = 'all_completers' )
  # parser.add_argument( '--enable-coverage',
  #                      action = 'store_true',
  #                      help   = 'For developers: Enable gcov coverage for the '
  #                               'c++ module' )
  parser.add_argument( '--enable-debug',
                       action = 'store_true',
                       help   = 'For developers: build pocketsphinx/sphinxbase library with '
                                'debug symbols' )
  parser.add_argument( '--build-dir',
                       default=PREFIX,
                       help   = 'For developers: perform the build in the '
                                'specified directory, and do not delete the '
                                'build output. This is useful for incremental '
                                'builds, and required for coverage data' )
  parser.add_argument( '--checkout-dir',
                       help   = 'For developers: location of folder where we download git repos or tar files for cmusphinx and pocketsphinx',
                       default=CHECKOUTROOT
                        )
  parser.add_argument( '--quiet',
                       action = 'store_true',
                       help = 'Quiet installation mode. Just print overall '
                              'progress and errors' )
  parser.add_argument( '--skip-build',
                       action = 'store_true',
                       help = "Don't build ps_build_core lib, just install deps" )
  parser.add_argument( '--build-envrc',
                       action = 'store_true',
                       help = "Create build .envrc file" )
  parser.add_argument( '--run-envrc',
                       action = 'store_true',
                       help = "Create run .envrc file" )
  parser.add_argument( '--clone-all',
                       action = 'store_true',
                       help = "Clone all repos" )

  # parser.add_argument( '--no-regex',
  #                      action = 'store_true',
  #                      help = "Don't build the regex module" )
  # parser.add_argument( '--clang-tidy',
  #                      action = 'store_true',
  #                      help = 'Run clang-tidy static analysis' )
  parser.add_argument( '--core-tests', nargs = '?', const = '*',
                       help = 'Run core tests and optionally filter them.' )


  args = parser.parse_args()

#   # coverage is not supported for c++ on MSVC
#   if not OnWindows() and args.enable_coverage:
#     # We always want a debug build when running with coverage enabled
#     args.enable_debug = True

  if args.core_tests:
    os.environ[ 'PS_BUILD_TESTRUN' ] = '1'
  elif os.environ.get( 'PS_BUILD_TESTRUN' ):
    args.core_tests = '*'
  return args


def FindCmake():
  return FindExecutableOrDie( 'cmake', 'CMake is required to build pocketsphinx-build' )


def FindBrew():
  return FindExecutableOrDie( 'brew', 'brew is required to build pocketsphinx-build' )

def GetCmakeCommonArgs( args ):
  cmake_args = [ '-G', GetGenerator( args ) ]
  cmake_args.extend( CustomPythonCmakeArgs( args ) )
  return cmake_args


def GetCmakeArgs( parsed_args ):
  cmake_args = []
  # if parsed_args.clang_completer or parsed_args.all_completers:
  #   cmake_args.append( '-DUSE_CLANG_COMPLETER=ON' )

  # if parsed_args.clang_tidy:
  #   cmake_args.append( '-DUSE_CLANG_TIDY=ON' )

  # if parsed_args.system_libclang:
  #   cmake_args.append( '-DUSE_SYSTEM_LIBCLANG=ON' )

  # if parsed_args.system_boost:
  #   cmake_args.append( '-DUSE_SYSTEM_BOOST=ON' )

  # if parsed_args.enable_debug:
  #   cmake_args.append( '-DCMAKE_BUILD_TYPE=Debug' )
  #   cmake_args.append( '-DUSE_DEV_FLAGS=ON' )

  # # coverage is not supported for c++ on MSVC
  # if not OnWindows() and parsed_args.enable_coverage:
  #   cmake_args.append( '-DCMAKE_CXX_FLAGS=-coverage' )

  # use_python2 = 'ON' if PY_MAJOR == 2 else 'OFF'
  # cmake_args.append( '-DUSE_PYTHON2=' + use_python2 )

  # extra_cmake_args = os.environ.get( 'EXTRA_CMAKE_ARGS', '' )
  # # We use shlex split to properly parse quoted CMake arguments.
  # cmake_args.extend( shlex.split( extra_cmake_args ) )
  return cmake_args


def RunPsBuildTests( args, build_dir ):
  # tests_dir = p.join( build_dir, 'ycm', 'tests' )
  # os.chdir( tests_dir )
  # new_env = os.environ.copy()

  # if OnWindows():
  #   # We prepend the folder of the ps_build_core_tests executable to the PATH
  #   # instead of overwriting it so that the executable is able to find the
  #   # Python library.
  #   new_env[ 'PATH' ] = DIR_OF_THIS_SCRIPT + ';' + new_env[ 'PATH' ]
  # else:
  #   new_env[ 'LD_LIBRARY_PATH' ] = DIR_OF_THIS_SCRIPT

  # tests_cmd = [ p.join( tests_dir, 'ps_build_core_tests' ) ]
  # if args.core_tests != '*':
  #   tests_cmd.append( '--gtest_filter={}'.format( args.core_tests ) )
  # CheckCall( tests_cmd,
  #            env = new_env,
  #            quiet = args.quiet,
  #            status_message = 'Running pocketsphinx-build tests' )
  pass


def RunPsBuildBenchmarks( build_dir ):
  # benchmarks_dir = p.join( build_dir, 'ycm', 'benchmarks' )
  # new_env = os.environ.copy()

  # if OnWindows():
  #   # We prepend the folder of the ps_build_core_tests executable to the PATH
  #   # instead of overwriting it so that the executable is able to find the
  #   # Python library.
  #   new_env[ 'PATH' ] = DIR_OF_THIS_SCRIPT + ';' + new_env[ 'PATH' ]
  # else:
  #   new_env[ 'LD_LIBRARY_PATH' ] = DIR_OF_THIS_SCRIPT

  # # Note we don't pass the quiet flag here because the output of the benchmark
  # # is the only useful info.
  # CheckCall( p.join( benchmarks_dir, 'ps_build_core_benchmarks' ), env = new_env )
  pass

# On Windows, if the pocketsphinx-build library is in use while building it, a LNK1104
# fatal error will occur during linking. Exit the script early with an
# error message if this is the case.
def ExitIfPsBuildLibInUseOnWindows():
  if not OnWindows():
    return

  # pocketsphinx-build_library = p.join( DIR_OF_THIS_SCRIPT, 'ps_build_core.pyd' )

  # if not p.exists( pocketsphinx-build_library ):
  #   return

  # try:
  #   open( p.join( pocketsphinx-build_library ), 'a' ).close()
  # except IOError as error:
  #   if error.errno == errno.EACCES:
  #     sys.exit( 'ERROR: pocketsphinx-build library is currently in use. '
  #               'Stop all pocketsphinx-build instances before compilation.' )


def GetCMakeBuildConfiguration( args ):
  if OnWindows():
    if args.enable_debug:
      return [ '--config', 'Debug' ]
    return [ '--config', 'Release' ]
  return [ '--', '-j', str( NumCores() ) ]


# def BuildRegexModule( cmake, cmake_common_args, script_args ):
#   build_dir = mkdtemp( prefix = 'regex_build_' )

#   try:
#     os.chdir( build_dir )

#     configure_command = [ cmake ] + cmake_common_args
#     configure_command.append( p.join( DIR_OF_THIS_SCRIPT,
#                                       'third_party', 'cregex' ) )

#     CheckCall( configure_command,
#                exit_message = BUILD_ERROR_MESSAGE,
#                quiet = script_args.quiet,
#                status_message = 'Generating regex build configuration' )

#     build_config = GetCMakeBuildConfiguration( script_args )

#     build_command = ( [ cmake, '--build', '.', '--target', '_regex' ] +
#                       build_config )
#     CheckCall( build_command,
#                exit_message = BUILD_ERROR_MESSAGE,
#                quiet = script_args.quiet,
#                status_message = 'Compiling regex module' )
#   finally:
#     os.chdir( DIR_OF_THIS_SCRIPT )
#     rmtree( build_dir, ignore_errors = OnCiService() )


# def EnableCsCompleter( args ):
#   build_command = PathToFirstExistingExecutable(
#     [ 'msbuild', 'msbuild.exe', 'xbuild' ] )
#   if not build_command:
#     sys.exit( 'ERROR: msbuild or xbuild is required to build Omnisharp.' )

#   os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'OmniSharpServer' ) )
#   CheckCall( [ build_command, '/property:Configuration=Release',
#                               '/property:Platform=Any CPU',
#                               '/property:TargetFrameworkVersion=v4.5' ],
#              quiet = args.quiet,
#              status_message = 'Building OmniSharp for C# completion' )


# def EnableGoCompleter( args ):
#   go = FindExecutableOrDie( 'go', 'go is required to build gocode.' )

#   os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'gocode' ) )
#   CheckCall( [ go, 'build' ],
#              quiet = args.quiet,
#              status_message = 'Building gocode for go completion' )
#   os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'godef' ) )
#   CheckCall( [ go, 'build', 'godef.go' ],
#              quiet = args.quiet,
#              status_message = 'Building godef for go definition' )


# def EnableRustCompleter( args ):
#   """
#   Build racerd. This requires a reasonably new version of rustc/cargo.
#   """
#   cargo = FindExecutableOrDie( 'cargo',
#                                'cargo is required for the Rust completer.' )

#   os.chdir( p.join( DIR_OF_THIRD_PARTY, 'racerd' ) )
#   command_line = [ cargo, 'build' ]
#   # We don't use the --release flag on CI services because it makes building
#   # racerd 2.5x slower and we don't care about the speed of the produced racerd.
#   if not OnCiService():
#     command_line.append( '--release' )
#   CheckCall( command_line,
#              quiet = args.quiet,
#              status_message = 'Building racerd for Rust completion' )


# def EnableJavaScriptCompleter( args ):
#   node = FindExecutableOrDie( 'node', 'node is required to set up Tern.' )
#   npm = FindExecutableOrDie( 'npm', 'npm is required to set up Tern.' )

#   # We install Tern into a runtime directory. This allows us to control
#   # precisely the version (and/or git commit) that is used by pocketsphinx-build.  We use a
#   # separate runtime directory rather than a submodule checkout directory
#   # because we want to allow users to install third party plugins to
#   # node_modules of the Tern runtime.  We also want to be able to install our
#   # own plugins to improve the user experience for all users.
#   #
#   # This is not possible if we use a git submodule for Tern and simply run 'npm
#   # install' within the submodule source directory, as subsequent 'npm install
#   # tern-my-plugin' will (heinously) install another (arbitrary) version of Tern
#   # within the Tern source tree (e.g. third_party/tern/node_modules/tern. The
#   # reason for this is that the plugin that gets installed has "tern" as a
#   # dependency, and npm isn't smart enough to know that you're installing
#   # *within* the Tern distribution. Or it isn't intended to work that way.
#   #
#   # So instead, we have a package.json within our "Tern runtime" directory
#   # (third_party/tern_runtime) that defines the packages that we require,
#   # including Tern and any plugins which we require as standard.
#   os.chdir( p.join( DIR_OF_THIS_SCRIPT, 'third_party', 'tern_runtime' ) )
#   CheckCall( [ npm, 'install', '--production' ],
#              quiet = args.quiet,
#              status_message = 'Setting up Tern for JavaScript completion' )


# def EnableJavaCompleter( switches ):
#   def Print( *args, **kwargs ):
#     if not switches.quiet:
#       print( *args, **kwargs )

#   if switches.quiet:
#     sys.stdout.write( 'Installing jdt.ls for Java support...' )
#     sys.stdout.flush()

#   TARGET = p.join( DIR_OF_THIRD_PARTY, 'eclipse.jdt.ls', 'target', )
#   REPOSITORY = p.join( TARGET, 'repository' )
#   CACHE = p.join( TARGET, 'cache' )

#   JDTLS_SERVER_URL_FORMAT = ( 'http://download.eclipse.org/jdtls/milestones/'
#                               '{jdtls_milestone}/{jdtls_package_name}' )
#   JDTLS_PACKAGE_NAME_FORMAT = ( 'jdt-language-server-{jdtls_milestone}-'
#                                 '{jdtls_build_stamp}.tar.gz' )

#   package_name = JDTLS_PACKAGE_NAME_FORMAT.format(
#       jdtls_milestone = JDTLS_MILESTONE,
#       jdtls_build_stamp = JDTLS_BUILD_STAMP )
#   url = JDTLS_SERVER_URL_FORMAT.format(
#       jdtls_milestone = JDTLS_MILESTONE,
#       jdtls_package_name = package_name )
#   file_name = p.join( CACHE, package_name )

#   if p.exists( REPOSITORY ):
#     shutil.rmtree( REPOSITORY )

#   os.makedirs( REPOSITORY )

#   if not p.exists( CACHE ):
#     os.makedirs( CACHE )
#   elif p.exists( file_name ):
#     with open( file_name, 'rb' ) as existing_file:
#       existing_sha256 = hashlib.sha256( existing_file.read() ).hexdigest()
#     if existing_sha256 != JDTLS_SHA256:
#       Print( 'Cached tar file does not match checksum. Removing...' )
#       os.remove( file_name )


#   if p.exists( file_name ):
#     Print( 'Using cached jdt.ls: {0}'.format( file_name ) )
#   else:
#     Print( "Downloading jdt.ls from {0}...".format( url ) )
#     request = requests.get( url, stream = True )
#     with open( file_name, 'wb' ) as package_file:
#       package_file.write( request.content )
#     request.close()

#   Print( "Extracting jdt.ls to {0}...".format( REPOSITORY ) )
#   with tarfile.open( file_name ) as package_tar:
#     package_tar.extractall( REPOSITORY )

#   Print( "Done installing jdt.ls" )

#   if switches.quiet:
#     print( 'OK' )


def WritePythonUsedDuringBuild():
  path = p.join( DIR_OF_THIS_SCRIPT, 'PYTHON_USED_DURING_BUILDING' )
  with open( path, 'w' ) as f:
    f.write( sys.executable )


def setup_pkg_config_path():
#     # /home/pi/.pyenv/versions/3.5.2/lib/pkgconfig
#     # /home/pi/uninstalled/lib/pkgconfig
#     # /home/pi/uninstalled/share/pkgconfig
#     # /usr/lib/pkgconfig
#     environ_prepend("PKG_CONFIG_PATH", "/usr/lib/pkgconfig", ":")
#     environ_prepend(
#         "PKG_CONFIG_PATH", "{}/uninstalled/share/pkgconfig".format(USERHOME), ":"
#     )
#     environ_prepend("PKG_CONFIG_PATH", "{}/uninstalled/lib/pkgconfig".format(USERHOME), ":")
#     environ_prepend(
#         "PKG_CONFIG_PATH",
#         "{}/.pyenv/versions/{}/lib/pkgconfig".format(USERHOME, PY_VERSION_FULL),
#         ":",
#     )
#     Console.message("AFTER")
    dump_env_var("PKG_CONFIG_PATH")


def setup_all_envs():
    setup_debug()
    setup_path_env()
    setup_python_version()
    setup_ld_library_path()
    setup_pythonpath()
    setup_pkg_config_path()


def Main():
  args = ParseArguments()
  # FIXME: Add FindGCC - 10/30/2018
  # FIXME: Add FindClang - 10/30/2018
  if args.render_dry_run:
      setup_all_envs()
      render_envrc_dry_run()
  if args.brew_bundle:
      brew_bundle()

  # Always run this
  cmake = FindCmake()
  cmake_common_args = GetCmakeCommonArgs( args )
  # if not args.skip_build:
  #   ExitIfPsBuildLibInUseOnWindows()
  #   BuildPsBuildLib( cmake, cmake_common_args, args )
  #   WritePythonUsedDuringBuild()
  # if not args.no_regex:
  #   BuildRegexModule( cmake, cmake_common_args, args )
  # if args.cs_completer or args.omnisharp_completer or args.all_completers:
  #   EnableCsCompleter( args )
  # if args.go_completer or args.gocode_completer or args.all_completers:
  #   EnableGoCompleter( args )
  # if args.js_completer or args.tern_completer or args.all_completers:
  #   EnableJavaScriptCompleter( args )
  # if args.rust_completer or args.racer_completer or args.all_completers:
  #   EnableRustCompleter( args )
  # if args.java_completer or args.all_completers:
  #   EnableJavaCompleter( args )


if __name__ == '__main__':
  Main()
