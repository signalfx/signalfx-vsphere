#!/usr/bin/env python
"""
Unit tests for the plugin, meant to be executed by pytest.
"""
import collections
import logging
import mock
import pytest
import sys

import vsphere

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format='%(asctime)s %(message)s')


@pytest.fixture(scope="session")
def mock_config():
    mock_config = mock.Mock()
    ConfigOption = collections.namedtuple('ConfigOption', ['key', 'values'])
    mock_config.children = [
        ConfigOption('Username', ('Administrator@vcenter.local',)),
        ConfigOption('Password', ('VMware1!',)),
        ConfigOption('Host', ('192.168.135.128',)),
        ConfigOption('Name', ('mike_vc',)),
        ConfigOption('VerbosityLevel', (1,)),
        ConfigOption('MORSyncInterval', (60,)),
        ConfigOption('MetricSyncInterval', (60,)),
    ]
    return mock_config


def test_start_plugin(mock_config):
    vsphere.collectd.INSTANCE.init_logging()
    vsphere.collectd.INSTANCE.engine_run_config(mock_config)
    vsphere.collectd.INSTANCE.engine_run_init()
    vsphere.collectd.INSTANCE.engine_read_metrics()
    vsphere.collectd.INSTANCE.engine_run_shutdowns()
