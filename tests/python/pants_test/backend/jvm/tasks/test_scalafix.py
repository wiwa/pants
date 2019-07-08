# coding=utf-8
# Copyright 2017 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

import re
from builtins import open

from pants_test.pants_run_integration_test import PantsRunIntegrationTest
from pants.java.jar.jar_dependency import JarDependency
from pants.util.dirutil import read_file


TEST_DIR = 'testprojects/src/scala/org/pantsbuild/testproject'


class ScalaFixIntegrationTest(PantsRunIntegrationTest):

  _rules = {'rules': 'ProcedureSyntax'}
  _options = {
      'lint.scalafix': _rules,
      'fmt.scalafix': _rules,
      'lint.scalastyle': {'skip': True}
    }

  @classmethod
  def hermetic(cls):
    return True

  @classmethod
  def register_options(cls, register):
    cls.register_jvm_tool(register,
                          'rscCompat',
                          classpath=[
                            JarDependency(org='com.twitter', name='rsc-rules_2.11', rev = "0.0.0-758-7ae5dd31"),
                          ])

  # def test_scalafix_fail(self):
  #   target = '{}/procedure_syntax'.format(TEST_DIR)
  #   # lint should fail because the rule has an impact.
  #   failing_test = self.run_pants(['lint', target], self._options)
  #   self.assert_failure(failing_test)

  # def test_scalafix_disabled(self):
  #   # take a snapshot of the file which we can write out
  #   # after the test finishes executing.
  #   test_file_name = '{}/procedure_syntax/ProcedureSyntax.scala'.format(TEST_DIR)
  #   with open(test_file_name, 'r') as f:
  #     contents = f.read()

  #   try:
  #     # format an incorrectly formatted file.
  #     target = '{}/procedure_syntax'.format(TEST_DIR)
  #     fmt_result = self.run_pants(['fmt', target], self._options)
  #     self.assert_success(fmt_result)

  #     # verify that the lint check passes.
  #     test_fix = self.run_pants(['lint', target], self._options)
  #     self.assert_success(test_fix)
  #   finally:
  #     # restore the file to its original state.
  #     f = open(test_file_name, 'w')
  #     f.write(contents)
  #     f.close()

  def test_rsccompat_fmt(self):
    options =  {
      'scala': {
        'scalac_plugin_dep': f'{TEST_DIR}/rsc_compat:semanticdb-scalac',
        'scalac_plugins': '+["semanticdb"]'
      },
      'lint.scalafix': {'skip': True},
      'fmt.scalafix': {
        'rules': 'scala:rsc.rules.RscCompat',
        'semantic': True,
        'transitive': True,
        'scalafix_tool_classpath': f'{TEST_DIR}/rsc_compat:rsc-compat',
      },
      'lint.scalastyle': {'skip': True},
    }
    
    test_file_name = '{}/rsc_compat/RscCompat.scala'.format(TEST_DIR)
    fixed_file_name = '{}/rsc_compat/RscCompatFixed.scala'.format(TEST_DIR)
    with open(test_file_name, 'r') as f:
      contents = f.read()

    try:
      # format an incorrectly formatted file.
      target = '{}/rsc_compat'.format(TEST_DIR)
      fmt_result = self.run_pants(['--no-verify-config', 'compile', 'fmt', target], options)
      self.assert_success(fmt_result)

      result = read_file(test_file_name)
      result = re.sub(re.escape('object RscCompat {'), 'object RscCompatFixed {', result)
      expected = read_file(fixed_file_name)
      assert(result == expected)
    finally:
      # restore the file to its original state.
      f = open(test_file_name, 'w')
      f.write(contents)
      f.close()
