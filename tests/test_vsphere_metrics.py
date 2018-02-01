import unittest

import sys
sys.path.insert(0, '../')
import vsphere_metrics


class VSPhereMetricsTests(unittest.TestCase):

    def test_basic_vsphere_metrics(self):
        conf = {}
        metrics = vsphere_metrics.get_metrics(conf)
        self.assertIsNotNone(metrics)
        self.assertIsNotNone(metrics['host'])

    def test_include_vsphere_metrics(self):
        conf = {
            'include_metrics': {

                'host': [
                    'host.test.metric',
                ],
                'cluster': [
                    'cluster.test.metric',
                ]
            }
        }
        metrics = vsphere_metrics.get_metrics(conf)
        self.assertIsNotNone(metrics)
        self.assertIn('host.test.metric', metrics['host'])
        self.assertIn('cluster.test.metric', metrics['cluster'])

    def test_exclude_vsphere_metrics(self):
        conf = {
            'exclude_metrics': {
                'host': [
                    'cpu.utilization.average',
                ],
                'vm': [
                    'cpu.usage.average'
                ]
            }
        }
        metrics = vsphere_metrics.get_metrics(conf)
        self.assertIsNotNone(metrics)
        self.assertNotIn('cpu.utilization.average', metrics['host'])
        self.assertNotIn('cpu.usage.average', metrics['vm'])
