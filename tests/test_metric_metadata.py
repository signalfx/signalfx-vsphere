import unittest
from utils import VCRTestBase
import utils

from pyVim import connect

import sys
sys.path.insert(0, '../')
import metric_metadata


class MetricMetadataTests(VCRTestBase):

    @VCRTestBase.my_vcr.use_cassette('test_metric_metadata_run.yaml',
                                     cassette_library_dir=utils.fixtures_path,
                                     record_mode='none')
    def test_metric_metadata_run(self):
        si = connect.SmartConnectNoSSL(host='192.168.1.60',
                                       user='administrator@vsphere.local',
                                       pwd='Abcd123$')
        mor_sync_interval = 300
        vc_name = 'TestVcenter'
        instance_id = 'VCenterInstance'
        metric_conf = {}
        metric_manager = metric_metadata.MetricManager(si, mor_sync_interval, metric_conf, vc_name, instance_id)
        metric_manager.start()
        metric_manager.block_until_has_metrics(timeout=5)
        current_metrics = metric_manager.get_monitored_metrics()
        self.assertIsNotNone(current_metrics)
        self.assertIsNotNone(current_metrics['host'])
        self.assertIsNotNone(current_metrics['vm'])
        metric_manager.stop()

    @VCRTestBase.my_vcr.use_cassette('test_metric_metadata_sync.yaml',
                                     cassette_library_dir=utils.fixtures_path,
                                     record_mode='none')
    def test_metric_metadata_sync(self):
        si = connect.SmartConnectNoSSL(host='192.168.1.60',
                                       user='administrator@vsphere.local',
                                       pwd='Abcd123$')

        mor_sync_interval = 300
        vc_name = 'TestVcenter'
        instance_id = 'VCenterInstance'
        metric_conf = {}
        metric_manager = metric_metadata.MetricManager(si, mor_sync_interval, metric_conf, vc_name, instance_id)
        metric_manager._sync_metrics()
        current_metrics = metric_manager.get_monitored_metrics()
        self.assertIsNotNone(current_metrics)
        self.assertIsNotNone(current_metrics['host'])
        self.assertIsNotNone(current_metrics['vm'])
