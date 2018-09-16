# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import faulthandler
import logging
import os
import signal
import sys
import traceback
from builtins import object, str

from future.utils import PY2

from pants.util.dirutil import safe_open


logger = logging.getLogger(__name__)


class Exiter(object):
  """A class that provides standard runtime exit and global exception handling behavior.

  The expected method call order of this class is as follows:

   1) Call Exiter.set_except_hook() to set sys.excepthook to the internal exception hook. This
      should happen as early as possible to ensure any/all exceptions are handled by the hook.
   2) Call Exiter.apply_options() to set traceback printing behavior via an Options object.
   3) Perform other operations as normal.
   4) Call Exiter.exit(), Exiter.exit_and_fail() or exiter_inst() when you wish to exit the runtime.
  """

  def __init__(self, exiter=sys.exit, formatter=traceback.format_tb, print_backtraces=True):
    """
    :param func exiter: A function to be called to conduct the final exit of the runtime. (Optional)
    :param func formatter: A function to be called to format any encountered tracebacks. (Optional)
    :param bool print_backtraces: Whether or not to print backtraces by default. Can be
                                  overridden by Exiter.apply_options(). (Optional)
    """
    # Since we have some exit paths that run via the sys.excepthook,
    # symbols we use can become garbage collected before we use them; ie:
    # we can find `sys` and `traceback` are `None`.  As a result we capture
    # all symbols we need here to ensure we function in excepthook context.
    # See: http://stackoverflow.com/questions/2572172/referencing-other-modules-in-atexit
    self._exit = exiter
    self._format_tb = formatter
    self._should_print_backtrace = print_backtraces
    self._workdir = None

  def __call__(self, *args, **kwargs):
    """Map class calls to self.exit() to support sys.exit() fungibility."""
    return self.exit(*args, **kwargs)

  def apply_options(self, options):
    """Applies global configuration options to internal behavior.

    :param Options options: An instance of an Options object to fetch global options from.
    """
    self._should_print_backtrace = options.for_global_scope().print_exception_stacktrace
    self._workdir = options.for_global_scope().pants_workdir

  def exit(self, result=0, msg=None, out=None):
    """Exits the runtime.

    :param result: The exit status. Typically a 0 indicating success or a 1 indicating failure, but
                   can be a string as well. (Optional)
    :param msg: A string message to print to stderr or another custom file desciptor before exiting.
                (Optional)
    :param out: The file descriptor to emit `msg` to. (Optional)
    """
    if msg:
      if PY2:
        msg = msg.encode('utf-8')  # sys.stderr expects bytes in Py2, unicode in Py3
      print(msg, file=out or sys.stderr)
    self._exit(result)

  def exit_and_fail(self, msg=None):
    """Exits the runtime with an exit code of 1, indicating failure.

    :param str msg: A string message to print to stderr before exiting. (Optional)
    """
    self.exit(result=1, msg=msg)

  def format_unhandled_exception(self, exc=None, exc_class=None, tb=None, add_newline=False):
    exc_class = exc_class or sys.exc_info()[0]
    exc = exc or sys.exc_info()[1]
    tb = tb or sys.exc_info()[2]

    return """Exception caught: ({exc_class})
{traceback}
Exception message: {exc_msg}
{newline}""".format(exc_class=(exc_class or type(exc)),
                    traceback=(self._format_tb(tb) if tb else ''),
                    exc_msg=(str(exc) if exc else 'none'),
                    newline=('\n' if add_newline else ''))

  def handle_unhandled_exception(self, exc_class=None, exc=None, tb=None, add_newline=False):
    """Default sys.excepthook implementation for unhandled exceptions."""

    exception_message = self.format_unhandled_exception(
      exc=exc, exc_class=exc_class,
      tb=(tb if self._should_print_backtrace else None),
      add_newline=self._should_print_backtrace)

    # Always output the unhandled exception details into a log file.
    self.log_exception(exception_message)
    # Print to stderr, and exit with a nonzero return code.
    self.exit_and_fail(exception_message)

  def log_exception(self, msg, workdir=None):
    workdir = workdir or self._workdir

    try:
      if not workdir:
        raise Exception('no workdir or self._workdir was set to log exceptions to. message was: {}'
                        .format(msg))
      output_path = os.path.join(workdir, 'logs', 'exceptions.log')
      with safe_open(output_path, 'a') as exception_log:
        exception_log.write('timestamp: {}\n'.format(datetime.datetime.now().isoformat()))
        exception_log.write('args: {}\n'.format(sys.argv))
        exception_log.write('pid: {}\n'.format(os.getpid()))
        exception_log.write(msg)
        exception_log.write('\n')
    except Exception as e:
      # This is all error recovery logic so we catch all exceptions from the logic above because
      # we don't want to hide the original error.
      logger.error('Problem logging original exception: {}'.format(e))

  def _setup_faulthandler(self, trace_stream):
    faulthandler.enable(trace_stream)
    # This permits a non-fatal `kill -31 <pants pid>` for stacktrace retrieval.
    faulthandler.register(signal.SIGUSR2, trace_stream, chain=True)

  def set_except_hook(self, trace_stream=None, workdir=None):
    """Sets the global exception hook."""
    self._setup_faulthandler(trace_stream or sys.stderr)
    self._workdir = workdir or self._workdir
    sys.excepthook = self.handle_unhandled_exception
