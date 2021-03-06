#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from cloudify_agent.installer.runners.winrm_runner import WinRMRunner
from cloudify_agent.installer import WindowsInstallerMixin
from cloudify_agent.installer import LocalInstallerMixin
from cloudify_agent.installer import RemoteInstallerMixin


class RemoteWindowsAgentInstaller(WindowsInstallerMixin, RemoteInstallerMixin):

    def __init__(self, cloudify_agent, logger=None):
        super(RemoteWindowsAgentInstaller, self).__init__(
            cloudify_agent, logger)
        self._runner = WinRMRunner(
            host=cloudify_agent['ip'],
            user=cloudify_agent['user'],
            password=cloudify_agent['password'],
            port=cloudify_agent.get('port'),
            protocol=cloudify_agent.get('protocol'),
            uri=cloudify_agent.get('uri'),
            logger=self.logger)

    def extract(self, archive, destination):
        return self.runner.unzip(archive, destination)

    @property
    def runner(self):
        return self._runner


class LocalWindowsAgentInstaller(WindowsInstallerMixin, LocalInstallerMixin):

    def __init__(self, cloudify_agent, logger=None):
        super(LocalWindowsAgentInstaller, self).__init__(
            cloudify_agent, logger
        )

    def extract(self, archive, destination):
        destination = '{0}\\env'.format(destination.rstrip('\\ '))
        self.logger.debug('Extracting {0} to {1}'
                          .format(archive, destination))
        cmd = '{0} /SILENT /VERYSILENT' \
              ' /SUPPRESSMSGBOXES /DIR={1}'.format(archive, destination)
        self.runner.run(cmd)
        return destination
