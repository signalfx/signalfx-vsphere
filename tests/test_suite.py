import unittest
from test_inventory import InventoryTests
from test_metric_metadata import MetricMetadataTests
from test_vsphere_metrics import VSPhereMetricsTests


def suite():
    suite = unittest.TestSuite()
    suite.addTests([InventoryTests(), MetricMetadataTests(), VSPhereMetricsTests()])
    return suite


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())