#!/usr/bin/env python

import logging
import ssl
import itertools
import signalfx
import time
from pyVim.connect import SmartConnect
from pyVmomi import vim

import constants
import inventory
import metric_metadata


class Environment(object):

    def __init__(self, config):
        """
        Reads from configuration, connects to vCenter and starts inventory manager and metric manager threads.
        :param config: Configuration for the environment.

        """
        self._host = config['host']
        self._username = config['username']
        self._password = config['password']
        self._vc_name = config['Name']
        self._ingest_token = config['IngestToken']
        self._logger = logging.getLogger(self.get_instance_id())
        self._si = None
        self._connect()
        if self._si is None:
            raise ValueError("Unable to connect to host")
        self._ingest = self._create_signalfx_ingest()
        if 'MORSyncInterval' not in config:
            config['MORSyncInterval'] = constants.DEFAULT_MOR_SYNC_INTERVAL
        self._inventory_mgr = inventory.InventoryManager(self._si, config['MORSyncInterval'],
                                                         config['Name'], self.get_instance_id())
        self._inventory_mgr.start()
        if 'MetricSyncInterval' not in config:
            config['MetricSyncInterval'] = constants.DEFAULT_METRIC_SYNC_INTERVAL
        self._metric_conf = self._get_metric_config(config)
        self._metric_mgr = metric_metadata.MetricManager(self._si, config['MetricSyncInterval'],
                                                         self._metric_conf, config['Name'], self.get_instance_id())
        self._metric_mgr.start()
        self._wait_for_sync()

    def _wait_for_sync(self):
        """
        Waits until the inventory and available metrics are synced.
        :return: null

        """

        if not self._inventory_mgr.block_until_inventory(timeout=constants.INVENTORY_SYNC_TIMEOUT):
            raise RuntimeError("Did not sync inventory within {0} seconds".format(constants.INVENTORY_SYNC_TIMEOUT))

        if not self._metric_mgr.block_until_has_metrics(timeout=constants.DEFAULT_METRIC_SYNC_INTERVAL):
            raise RuntimeError("Did not sync metrics within {0} seconds".format(constants.DEFAULT_METRIC_SYNC_INTERVAL))

    def _connect(self):
        """
        Connect to the vCenter.
        :return: null

        """
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
            self._logger.error("Unable to connect to host {0}".format(self._host))
            self._si = None

    def get_instance_id(self):
        """
        Returns the instance id for logging.
        :return: string

        """
        return "{0}-{1}".format(self._vc_name, self._host)

    def _get_metric_config(self, config):
        """
        Gets the required metric preferences from Configuration.
        :param config:
        :return: dict

        """
        metric_config = dict()
        metric_config['include_metrics'] = config.get('include_metrics', {})
        metric_config['exclude_metrics'] = config.get('exclude_metrics', {})
        return metric_config

    def _create_signalfx_ingest(self):
        """
        Creates and returns the SignalFX ingest client.
        :return: Ingest Client

        """
        client = signalfx.SignalFx()
        ingest = client.ingest(self._ingest_token, timeout=5)
        return ingest

    def _get_dimensions(self, inv_obj, metric_value):
        """
        Returns the dimensions of inventory object.
        :param inv_obj: Inventory Object. eg: host, vm etc
        :param metric_value: Value of inventory object metric.
        :return: dict

        """
        dimensions = {}
        dimensions.update(inv_obj.sf_metadata_dims)
        if metric_value.id.instance != '':
            instance = str(metric_value.id.instance).replace(':', '_'). \
                replace('.', '_')
            dimensions['instance'] = instance
        return dimensions

    def _parse_query(self, inv_obj, query_results, monitored_metrics):
        """
        Parses the query results, builds and returns datapoints.
        :param inv_obj: Inventory Object
        :param query_results: Query results from QueryPerf().
        :param monitored_metrics: Metrics which will be monitored by the application for inventory object.
        :return: list

        """
        result = query_results[0]
        timestamp = int(time.time()) * 1000
        datapoints = []
        for metric in result.value:
            key = metric.id.counterId
            metric_name = monitored_metrics[key].name
            metric_type = monitored_metrics[key].metric_type
            dimensions = self._get_dimensions(inv_obj, metric)
            value = metric.value[0]
            if monitored_metrics[key].units == 'percent':
                value /= 100.0
            dp = self.Datapoint(metric_name, metric_type, value, dimensions, timestamp)
            datapoints.append(dp)
        return datapoints

    def _build_payload(self, dps):
        """
        Builds a ingest client payload from the datapoints.
        :param dps: datapoints
        :return: dict

        """
        dp_count = len(dps)
        payload = []
        start = 0
        delta = 100
        end = delta if dp_count > delta else dp_count
        for x in range(0, int(dp_count / delta) + 1):
            gauges = []
            counters = []
            for dp in dps[start: end]:
                dp.dimensions['metric_source'] = constants.METRIC_SOURCE
                payload_obj = {
                    'metric': dp.metric_name,
                    'value': dp.value,
                    'dimensions': dp.dimensions,
                    'timestamp': dp.timestamp
                }
                if dp.metric_type == 'gauge':
                    gauges.append(payload_obj)
                elif dp.metric_type == 'counter':
                    counters.append(payload_obj)
            payload.append({
                'gauges': gauges,
                'counters': counters
            })
            start = end
            end = end + delta
            if end > dp_count:
                end = dp_count
        return payload

    def _dispatch_metrics(self, payload):
        """
        Dispatches metrics to signalfx client.
        :param payload: Ingest client payload(contains the datapoints)
        :return: null

        """
        for item in payload:
            try:
                self._ingest.send(gauges=item['gauges'], counters=item['counters'])
            except Exception as e:
                self._logger.error("Exception while sending payload to ingest : {0}".format(e))

    def read_metric_values(self):
        """
        Collects the required metrics for all inventory objects from vCenter and dispatches them to Ingest client.
        :return: null

        """
        inv_objs = self._inventory_mgr.current_inventory()
        monitored_metrics = self._metric_mgr.get_monitored_metrics()
        perf_manager = self._si.RetrieveServiceContent().perfManager
        for mor in inv_objs.keys():
            for inv_obj in inv_objs[mor]:
                inv_obj_metrics = inv_obj.metric_id_map
                desired_keys = list(set(inv_obj_metrics.keys()) & set(monitored_metrics[mor].keys()))
                if not len(desired_keys) == 0:
                    metric_id_objs = [inv_obj_metrics[key] for key in desired_keys]
                    query_spec = vim.PerformanceManager.QuerySpec(
                        entity=inv_obj.mor, metricId=metric_id_objs,
                        intervalId=inv_obj.INSTANT_INTERVAL,
                        maxSample=1, format='normal'
                    )
                    results = perf_manager.QueryPerf(querySpec=[query_spec])
                    dps = self._parse_query(inv_obj, results, monitored_metrics[mor])
                    payload = self._build_payload(dps)
                    self._dispatch_metrics(payload)

    def send_metadata_metrics(self):
        """
        Sends a dummy metric to Ingest Client for all inventory objects with all the metadata(dimensions)
        so as to keep track of the current architecture of the vCenter
        :return: null

        """
        inv_objs = self._inventory_mgr.current_inventory()
        dps = []
        for inv_obj in itertools.chain(*inv_objs.values()):
            metric_name = constants.METADATA_METRIC_NAME
            metric_type = "gauge"
            value = 1
            timestamp = time.time() * 1000
            dimensions = inv_obj.sf_metadata_dims
            dps.append(self.Datapoint(metric_name, metric_type, value, dimensions, timestamp))
        payload = self._build_payload(dps)
        self._dispatch_metrics(payload)

    def stop_managers(self):
        """
        Stops inventory manager and metric manager threads.
        :return: null

        """
        self._inventory_mgr.stop()
        self._metric_mgr.stop()
        self._inventory_mgr.join(timeout=constants.DEFAULT_TIMEOUT)
        self._metric_mgr.join(timeout=constants.DEFAULT_TIMEOUT)

    class Datapoint(object):
        """

        Plain Object to hold metric as a datapoint.

        """
        def __init__(self, metric_name, metric_type, value, dimensions, timestamp):
            self.metric_name = metric_name
            self.metric_type = metric_type
            self.value = value
            self.dimensions = dimensions
            self.timestamp = timestamp
