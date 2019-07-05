# coding=utf-8
# Copyright 2017 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from abc import abstractproperty

from pants.backend.jvm.tasks.rewrite_base import RewriteBase
from pants.backend.jvm.tasks.jvm_task import JvmTask
from pants.base.exceptions import TaskError
from pants.java.jar.jar_dependency import JarDependency
from pants.option.custom_types import file_option
from pants.task.fmt_task_mixin import FmtTaskMixin
from pants.task.lint_task_mixin import LintTaskMixin


class ScalaFix(RewriteBase):
  """Executes the scalafix tool."""

  _SCALAFIX_MAIN = 'scalafix.cli.Cli'

  @classmethod
  def register_options(cls, register):
    super(ScalaFix, cls).register_options(register)
    register('--configuration', type=file_option, default=None, fingerprint=True,
             help='The config file to use (in HOCON format).')
    register('--rules', default='ProcedureSyntax', type=str, fingerprint=True,
             help='The `rules` arg to scalafix: generally a name like `ProcedureSyntax`.')
    register('--semantic', type=bool, default=False, fingerprint=True,
             help='True to enable `semantic` scalafix rules by requesting compilation and '
                  'providing the target classpath to scalafix. To enable this option, you '
                  'will need to install the `semanticdb-scalac` compiler plugin. See '
                  'https://www.pantsbuild.org/scalac_plugins.html for more information.')
    cls.register_jvm_tool(register,
                          'scalafix',
                          classpath=[
                            JarDependency(org='ch.epfl.scala', name='scalafix-cli_2.11.12', rev='0.6.0-M16'),
                          ])
    cls.register_jvm_tool(register, 'scalafix-tool-classpath', classpath=[])

  @classmethod
  def target_types(cls):
    return ['scala_library', 'junit_tests', 'java_tests']

  @classmethod
  def source_extension(cls):
    return '.scala'

  @classmethod
  def prepare(cls, options, round_manager):
    super(ScalaFix, cls).prepare(options, round_manager)
    # Only request a classpath if semantic checks are enabled.
    if options.semantic:
      round_manager.require_data('runtime_classpath')

  def invoke_tool(self, absolute_root, target_sources):
    args = []
    tool_classpath = self.tool_classpath('scalafix-tool-classpath')
    if tool_classpath:
      args.append('--tool-classpath={}'.format(os.pathsep.join(tool_classpath)))
    if self.get_options().semantic:
      # If semantic checks are enabled, we need the full classpath for these targets.
      classpath = self.classpath({target for target, _ in target_sources})
      args.append('--sourceroot={}'.format(absolute_root))
      args.append('--classpath={}'.format(os.pathsep.join(classpath)))
    if self.get_options().configuration:
      args.append('--config={}'.format(self.get_options().configuration))
    if self.get_options().rules:
      args.append('--rules={}'.format(self.get_options().rules))
    if self.get_options().level == 'debug':
      args.append('--verbose')
    args.extend(self.additional_args or [])

    args.extend(source for _, source in target_sources)

    # Execute.
    return self.runjava(classpath=self.tool_classpath('scalafix'),
                        main=self._SCALAFIX_MAIN,
                        jvm_options=self.get_options().jvm_options,
                        args=args,
                        workunit_name='scalafix')

  @abstractproperty
  def additional_args(self):
    """Additional arguments to the Scalafix command."""


class ScalaFixFix(FmtTaskMixin, ScalaFix):
  """Applies fixes generated by scalafix."""

  sideeffecting = True
  additional_args = []

  def process_result(self, result):
    if result != 0:
      raise TaskError(
          '{main} ... failed to fix ({result}) targets.'.format(
            main=self._SCALAFIX_MAIN,
            result=result))


class ScalaFixCheck(LintTaskMixin, ScalaFix):
  """Checks whether any fixes were generated by scalafix."""

  sideeffecting = False
  additional_args = ['--test']

  def process_result(self, result):
    if result != 0:
      raise TaskError('Targets failed scalafix checks.'.format())
