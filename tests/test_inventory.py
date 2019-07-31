import unittest
from utils import VCRTestBase
import utils

from pyVim import connect

import sys
sys.path.insert(0, '../')
import inventory


class InventoryTests(VCRTestBase):

    @VCRTestBase.my_vcr.use_cassette('test_inventory_run.yaml',
                                     cassette_library_dir=utils.fixtures_path,
                                     record_mode='none')
    def test_inventory_run(self):
        si = connect.SmartConnectNoSSL(host='192.168.1.60',
                                       user='administrator@vsphere.local',
                                       pwd='Abcd123$')
        mor_sync_interval = 300
        vc_name = 'TestVcenter'
        instance_id = 'VCenterInstance'
        inventory_mgr = inventory.InventoryManager(si, mor_sync_interval, vc_name, instance_id)
        inventory_mgr.start()
        inventory_mgr.block_until_inventory(timeout=5)
        current_inventory = inventory_mgr.current_inventory()
        self.assertIsNotNone(current_inventory)
        self.assertEqual(2, len(current_inventory['datacenter']))
        self.assertEqual(1, len(current_inventory['cluster']))
        self.assertEqual(2, len(current_inventory['host']))
        self.assertEqual(2, len(current_inventory['vm']))
        inventory_mgr.stop()

    @VCRTestBase.my_vcr.use_cassette('test_inventory_sync.yaml',
                                     cassette_library_dir=utils.fixtures_path,
                                     record_mode='none')
    def test_inventory_sync(self):
        si = connect.SmartConnectNoSSL(host='192.168.1.60',
                                       user='administrator@vsphere.local',
                                       pwd='Abcd123$')

        mor_sync_interval = 300
        vc_name = 'TestVcenter'
        instance_id = 'VCenterInstance'
        inventory_mgr = inventory.InventoryManager(si, mor_sync_interval, vc_name, instance_id)
        inventory_mgr.sync_inventory()
        current_inventory = inventory_mgr.current_inventory()
        self.assertIsNotNone(current_inventory)
        self.assertEqual(2, len(current_inventory['datacenter']))
        self.assertEqual(1, len(current_inventory['cluster']))
        self.assertEqual(2, len(current_inventory['host']))
        self.assertEqual(2, len(current_inventory['vm']))
