#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import time
import inspect
import types
import getpass
import logging
import tempfile
import shutil
from functools import wraps
from mock import _get_target
from mock import patch

from celery import Celery
from cloudify.utils import LocalCommandRunner
from cloudify.utils import setup_logger

from cloudify_agent.api import utils
from cloudify_agent.api import factory

from cloudify_agent.tests import BaseTest


BUILT_IN_TASKS = [
    'script_runner.tasks.execute_workflow',
    'script_runner.tasks.run',
    'diamond_agent.tasks.install',
    'diamond_agent.tasks.uninstall',
    'diamond_agent.tasks.start',
    'diamond_agent.tasks.stop',
    'diamond_agent.tasks.add_collectors',
    'diamond_agent.tasks.del_collectors',
    'cloudify_agent.operations.install_plugins',
    'cloudify_agent.operations.restart',
    'cloudify_agent.operations.stop'
]


def ci():
    return 'TRAVIS_BUILD_DIR' in os.environ or 'APPVEYOR' in os.environ


def patch_unless_ci(target, new):

    if not ci():
        return patch(target, new)
    else:
        getter, attribute = _get_target(target)
        return patch(target, getattr(getter(), attribute))


def only_ci(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not ci():
            raise RuntimeError('Error! This test cannot be executed '
                               'outside of the travis CI '
                               'system since it may corrupt '
                               'your local system files')
        func(*args, **kwargs)

    return wrapper


def only_os(os_type):

    def decorator(test):

        if isinstance(test, (types.MethodType, types.FunctionType)):
            if os.name != os_type:
                return lambda: None
            else:
                return test

        if isinstance(test, type):
            for name, fn in inspect.getmembers(test):
                if isinstance(fn, types.UnboundMethodType):
                    if name.startswith('test') or name.endswith('test'):
                        setattr(test, name, decorator(fn))
            return test

        raise ValueError("'test' argument is of an unsupported type: {0}. "
                         "supported types are: 'type', 'FunctionType',"
                         " 'MethodType'".format(type(test)))
    return decorator


class BaseDaemonLiveTestCase(BaseTest):

    def setUp(self):
        super(BaseDaemonLiveTestCase, self).setUp()
        self.celery = Celery(broker='amqp://',
                             backend='amqp://')
        self.logger = setup_logger(
            'cloudify-agent.tests.api.pm',
            logger_level=logging.DEBUG)

        utils.logger.setLevel(logging.DEBUG)
        factory.logger.setLevel(logging.DEBUG)

        self.runner = LocalCommandRunner(self.logger)
        self.temp_folder = tempfile.mkdtemp(prefix='cfy-agent-tests-')
        self.currdir = os.getcwd()
        self.username = getpass.getuser()
        self.logger.info('Working directory: {0}'.format(self.temp_folder))
        os.chdir(self.temp_folder)

    def tearDown(self):
        super(BaseDaemonLiveTestCase, self).tearDown()
        os.chdir(self.currdir)
        if os.name == 'nt':
            self.runner.run('taskkill /IM celery.exe', exit_on_failure=False)
        else:
            self.runner.run("pkill -9 -f 'celery'", exit_on_failure=False)

    def _smakedirs(self, dirs):
        if not os.path.exists(dirs):
            os.makedirs(dirs)

    def _srmtree(self, tree):
        if os.path.exists(tree):
            shutil.rmtree(tree)

    def assert_registered_tasks(self, name, additional_tasks=None):
        if not additional_tasks:
            additional_tasks = set()
        destination = 'celery@{0}'.format(name)
        inspect = self.celery.control.inspect(destination=[destination])
        registered = inspect.registered() or {}

        def include(task):
            return 'celery' not in task

        daemon_tasks = set(filter(include, set(registered[destination])))
        expected_tasks = set(BUILT_IN_TASKS)
        expected_tasks.update(additional_tasks)
        self.assertEqual(expected_tasks, daemon_tasks)

    def assert_daemon_alive(self, name):
        destination = 'celery@{0}'.format(name)
        inspect = self.celery.control.inspect(destination=[destination])
        stats = (inspect.stats() or {}).get(destination)
        self.assertTrue(stats is not None)

    def assert_daemon_dead(self, name):
        destination = 'celery@{0}'.format(name)
        inspect = self.celery.control.inspect(destination=[destination])
        stats = (inspect.stats() or {}).get(destination)
        self.assertTrue(stats is None)

    def wait_for_daemon_alive(self, name, timeout=10):
        deadline = time.time() + timeout

        while time.time() < deadline:
            stats = self._get_worker_stats(name)
            if stats:
                return
            self.logger.info('Waiting for daemon {0} to start...'
                             .format(name))
            time.sleep(1)
        raise RuntimeError('Failed waiting for daemon {0} to start. Waited '
                           'for {1} seconds'.format(name, timeout))

    def wait_for_daemon_dead(self, name, timeout=10):
        deadline = time.time() + timeout

        while time.time() < deadline:
            stats = self._get_worker_stats(name)
            if not stats:
                return
            self.logger.info('Waiting for daemon {0} to stop...'
                             .format(name))
            time.sleep(1)
        raise RuntimeError('Failed waiting for daemon {0} to stop. Waited '
                           'for {1} seconds'.format(name, timeout))

    def _get_worker_stats(self, name):
        destination = 'celery@{0}'.format(name)
        inspect = self.celery.control.inspect(destination=[destination])
        stats = (inspect.stats() or {}).get(destination)
        return stats
