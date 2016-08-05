#!/usr/bin/env python
# Copyright (C) 2016 SignalFx, Inc.
import itertools
import pprint
import ssl
import time

# Load the dummy collectd module if running this module outside of collectd
try:
    import collectd
except ImportError:
    import dummy_collectd as collectd

from pyVmomi import vim
from pyVim.connect import SmartConnect

import constants
import inventory
import metric_metadata

# Aliases
POWERED_ON = vim.HostSystem.PowerState.poweredOn

# Globals
plugin_config = {}
environments = []


class Environment(object):
    """
    Maintains state for vSphere instances
    """
    def __init__(self, host, username, password, verbosity_level=None):
        self._host = host
        self._username = username
        self._password = password
        if verbosity_level is None:
            verbosity_level = constants.DEFAULT_VERBOSITY_LEVEL
        self._verbosity_level = verbosity_level
        self._si = None
        self._connect()
        self._inventory_mgr = inventory.InventoryManager(
            self._si, plugin_config['MORSyncInterval'],
            plugin_config['Name'])
        self._inventory_mgr.start()
        self._metric_mgr = metric_metadata.MetricManager(
            self._si, plugin_config['MetricSyncInterval'],
            plugin_config['verbosity_level'], plugin_config['Name'])
        self._metric_mgr.start()
        self._wait_for_sync()

    def _wait_for_sync(self):
        success = self._inventory_mgr.block_until_inventory(
            timeout=constants.INVENTORY_SYNC_TIMEOUT)
        if not success:
            raise RuntimeError("Did not sync inventory within %d seconds" %
                               constants.INVENTORY_SYNC_TIMEOUT)
        success = self._metric_mgr.block_until_has_metrics(
            timeout=constants.DEFAULT_METRIC_SYNC_INTERVAL)
        if not success:
            raise RuntimeError("Did not sync metrics within %d seconds" %
                               constants.DEFAULT_METRIC_SYNC_INTERVAL)

    def _connect(self):
        """
        Establish a connection to vCenter
        """
        # Handle python versions prior to 2.7.9 by checking explicitly for
        # the SSLContext attribute.
        # For more details see
        # https://dellaert.org/2015/12/02/pyvmomi-6-0-0-vsphere-6-0-and-ssl/
        context = None
        if hasattr(ssl, 'SSLContext'):
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            context.verify_mode = ssl.CERT_NONE
        try:
            if context:
                self._si = SmartConnect(host=self._host, user=self._username,
                                        pwd=self._password, sslContext=context)
            else:
                self._si = SmartConnect(host=self._host, user=self._username,
                                        pwd=self._password)
        except Exception:
            collectd.error("Unable to connect to host %s" % self._host)
            self._si = None

    def _format_dimensions(self, dimensions):
        """
        Formats a dictionary of dimensions to a format that enables them to be
        specified as key, value pairs in plugin_instance to signalfx. E.g.

        >>> dimensions = {'a': 'foo', 'b': 'bar'}
        >>> _format_dimensions(dimensions)
        "[a=foo,b=bar]"

        Args:
        dimensions (dict): Mapping of {dimension_name: value, ...}

        Returns:
        str: Comma-separated list of dimensions
        """
        # Collectd limits the plugin_instance field size, so truncate anything
        # longer than that. Account for the 2 brackets at either end.
        trunc_len = constants.COLLECTD_FIELD_LENGTH - 2
        dim_pairs = []
        # Put the name dimension first because it is more likely to be unique
        # and we don't want it to get truncated.
        if 'name' in dimensions:
            dim_pairs.append('name=%s' % dimensions['name'])
        dim_pairs.extend("%s=%s" % (k, v) for k, v in dimensions.iteritems() if
                         k != 'name')
        dim_str = ",".join(dim_pairs)[:trunc_len]
        return "[%s]" % dim_str

    def _get_dimensions(self, inv_obj, metric_value):
        dimensions = {}
        dimensions.update(inv_obj.dimensions)
        if metric_value.id.instance != '':
            instance = str(metric_value.id.instance).replace(
                ':', '_').replace('.', '_')
            dimensions['instance'] = instance
        return dimensions

    def _build_datapoint(self, metric_name, metric_type, value, dimensions,
                         timestamp):
        datapoint = collectd.Values()
        datapoint.type = metric_type
        datapoint.type_instance = metric_name
        datapoint.plugin = constants.PLUGIN_NAME
        datapoint.plugin_instance = self._format_dimensions(dimensions)
        datapoint.values = (value,)
        datapoint.time = timestamp
        return datapoint

    def _parse_query(self, inv_obj, query_results, monitored_metrics):
        """
        Parses metric values from a call to QueryPerf(). An example of
        query_results looks like:

        (vim.PerformanceManager.EntityMetricBase) [
            (vim.PerformanceManager.EntityMetric) {
                dynamicType = <unset>,
                dynamicProperty = (vmodl.DynamicProperty) [],
                entity = 'vim.HostSystem:host-9',
                sampleInfo = (vim.PerformanceManager.SampleInfo) [
                    (vim.PerformanceManager.SampleInfo) {
                        dynamicType = <unset>,
                        dynamicProperty = (vmodl.DynamicProperty) [],
                        timestamp = 2016-08-04T21:16:00Z,
                        interval = 20
                    }
                ],
                value = (vim.PerformanceManager.MetricSeries) [
                    (vim.PerformanceManager.IntSeries) {
                        dynamicType = <unset>,
                        dynamicProperty = (vmodl.DynamicProperty) [],
                        id = (vim.PerformanceManager.MetricId) {
                        dynamicType = <unset>,
                        dynamicProperty = (vmodl.DynamicProperty) [],
                        counterId = 2,
                        instance = '0'
                        },
                        value = (long) [
                        180L
                        ]
                    },
                ...
        """
        result = query_results[0]
        # TODO: Do we need to support non-GMT?
        ts_dt = result.sampleInfo[0].timestamp
        timestamp = int(ts_dt.strftime("%s")) * 1000  # convert to ms

        datapoints = []
        for metric in result.value:
            key = metric.id.counterId
            metric_name = monitored_metrics[key].name
            metric_type = monitored_metrics[key].metric_type
            dimensions = self._get_dimensions(inv_obj, metric)
            value = metric.value[0]
            if monitored_metrics[key].units == 'percent':
                value /= 100.0
            dp = self._build_datapoint(metric_name, metric_type, value,
                                       dimensions, timestamp)
            datapoints.append(dp)
        return datapoints

    def _log_datapoint(self, datapoint):
        """
        Log the contents of a datapoint
        """
        pprint_dict = {
            'plugin': datapoint.plugin,
            'plugin_instance': datapoint.plugin_instance,
            'type': datapoint.type,
            'type_instance': datapoint.type_instance,
            'values': datapoint.values
        }
        collectd.info(pprint.pformat(pprint_dict))

    def read_metric_values(self):
        """
        Iterate over all the objects in the cached inventory and get the
        current values for the metrics we want to monitor.
        """
        inv_objs = self._inventory_mgr.current_inventory()
        monitored_metrics = self._metric_mgr.get_monitored_metrics()
        perf_manager = self._si.RetrieveServiceContent().perfManager
        datapoints = []
        for inv_obj in itertools.chain(*inv_objs.values()):
            inv_obj_metrics = inv_obj.metric_id_map
            desired_keys = (inv_obj_metrics.viewkeys() &
                            monitored_metrics.viewkeys())
            metric_id_objs = [inv_obj_metrics[key] for key in desired_keys]
            query_spec = vim.PerformanceManager.QuerySpec(
                entity=inv_obj.mor, metricId=metric_id_objs,
                intervalId=inv_obj.INSTANT_INTERVAL,
                maxSample=1, format='normal')
            # Batch 10-50 querySpecs into a single QueryPerf call, as per
            # the VC docs
            results = perf_manager.QueryPerf(querySpec=[query_spec])
            dps = self._parse_query(inv_obj, results, monitored_metrics)
            datapoints.extend(dps)

        for dp in datapoints:
            self._log_datapoint(dp)
            dp.dispatch()

    def send_metadata_metrics(self):
        """
        For every object in the inventory, we send a single metric representing
        dimensions of the object that are likely to change frequently. For
        example, the host that a VM is running on could change frequently
        due to vMotions.
        """
        inv_objs = self._inventory_mgr.current_inventory()
        for inv_obj in itertools.chain(*inv_objs.values()):
            metric_name = constants.METADATA_METRIC_NAME
            metric_type = "gauge"
            value = 1  # Ignored
            dimensions = inv_obj.sf_metadata_dims
            timestamp = int(time.time() * 1000)
            dp = self._build_datapoint(metric_name, metric_type, value,
                                       dimensions, timestamp)
            self._log_datapoint(dp)
            dp.dispatch()

    def stop_managers(self):
        """
        Stops the background threads polling for inventory and metric
        metadata changes.
        """
        self._inventory_mgr.stop()
        self._metric_mgr.stop()
        self._inventory_mgr.join(timeout=constants.DEFAULT_TIMEOUT)
        self._metric_mgr.join(timeout=constants.DEFAULT_TIMEOUT)


def config(config_values):
    """
    Loads information from the vSphere collectd plugin config file.

    Args:
    config_values (collectd.Config): Object containing config values
    """
    global plugin_config
    required_keys = set(('Username', 'Password', 'Host', 'Name'))
    for val in config_values.children:
        # Required settings
        if val.key in required_keys:
            plugin_config[val.key] = val.values[0]
        # Optional settings
        elif val.key == 'MORSyncInterval' and val.values[0]:
            plugin_config['mor_sync_interval'] = int(val.values[0])
        elif val.key == 'MetricSyncInterval' and val.values[0]:
            plugin_config['metric_sync_interval'] = int(val.values[0])
        elif val.key == 'VerbosityLevel' and val.values[0]:
            level = int(val.values[0])
            if level not in constants.VERBOSITY_LEVELS:
                raise ValueError("VerbosityLevel must be one of %s" %
                                 constants.VERBOSITY_LEVELS)
            plugin_config['verbosity_level'] = level

    # Set defaults for optional settings not specified
    if 'verbosity_level' not in plugin_config:
        plugin_config['verbosity_level'] = constants.DEFAULT_VERBOSITY_LEVEL
    if 'MORSyncInterval' not in plugin_config:
        mor_sync = constants.DEFAULT_MOR_SYNC_INTERVAL
        plugin_config['MORSyncInterval'] = mor_sync
    if 'MetricSyncInterval' not in plugin_config:
        metric_sync = constants.DEFAULT_METRIC_SYNC_INTERVAL
        plugin_config['MetricSyncInterval'] = metric_sync

    # Make sure all required config settings are present, and log them
    missing_keys = required_keys - set(plugin_config.keys())
    if missing_keys:
        raise ValueError("Missing required config settings: %s" % missing_keys)
    collectd.info("Using config settings:")
    collectd.info(pprint.pformat(plugin_config))


def init():
    """
    Connect to vCenter and cache its counter ID mappings.
    """
    global env
    collectd.info("Initializing the SignalFx vSphere plugin")
    env = Environment(plugin_config['Host'], plugin_config['Username'],
                      plugin_config['Password'],
                      plugin_config.get('VerbosityLevel'))


def read():
    """
    read() is called at every collectd refresh interval. It reads
    metrics for all known hosts and VMs and sends them to SignalFx.
    """
    env.read_metric_values()
    env.send_metadata_metrics()


def shutdown():
    """
    The shutdown callback is a no-op for this plugin.
    """
    collectd.info("Stopping the SignalFx vSphere plugin")
    env.stop_managers()


def setup_collectd():
    """
    Registers callback functions with collectd
    """
    collectd.register_config(config)
    collectd.register_init(init)
    collectd.register_read(read)
    collectd.register_shutdown(shutdown)


setup_collectd()
