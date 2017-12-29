#!/usr/bin/env python

import itertools
import time
import ssl
import signalfx
import logging

from pyVmomi import vim
from pyVim.connect import SmartConnect

import inventory
import metric_metadata
import constants


class Environment(object):

    def __init__(self, config):
        self._host = config['host']
        self._username = config['username']
        self._password = config['password']
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
        success = self._inventory_mgr.block_until_inventory(timeout=constants.INVENTORY_SYNC_TIMEOUT)
        if not success:
            raise RuntimeError("Did not sync inventory within {0} seconds".format(constants.INVENTORY_SYNC_TIMEOUT))
        success = self._metric_mgr.block_until_has_metrics(timeout=constants.DEFAULT_METRIC_SYNC_INTERVAL)
        if not success:
            raise RuntimeError("Did not sync metrics within {0} seconds".format(constants.DEFAULT_METRIC_SYNC_INTERVAL))

    def _connect(self):
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
        return "{0}".format(self._host)

    def _get_metric_config(self, config):
        metric_config = {}
        if 'enhanced_metrics' in config:
            metric_config['enhanced_metrics'] = True
        if 'include_metrics' in config:
            metric_config['include_metrics'] = config['include_metrics']
        if 'exclude_metrics' in config:
            metric_config['exclude_metrics'] = config['exclude_metrics']
        return metric_config

    def _create_signalfx_ingest(self):
        client = signalfx.SignalFx()
        ingest = client.ingest(constants.SIGNALFX_INGEST_TOKEN, timeout=5)
        return ingest

    def _get_dimensions(self, inv_obj, metric_value):
        dimensions = {}
        dimensions.update(inv_obj.sf_metadata_dims)
        if metric_value.id.instance != '':
            instance = str(metric_value.id.instance).replace(':', '_').\
                replace('.','_')
            dimensions['instance'] = instance
        return dimensions

    def _parse_query(self, inv_obj, query_results, monitored_metrics):
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
        dp_count = len(dps)
        payload = []
        start = 0
        delta = 100
        end = delta if dp_count > delta else dp_count
        for x in range(0, int(dp_count/delta)+1):
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
        try:
            for item in payload:
                self._ingest.send(gauges=item['gauges'], counters=item['counters'])
        except Exception as e:
            self._logger.error("Exception while sending payload to ingest : {0}".format(e))

    def read_metric_values(self):
        inv_objs = self._inventory_mgr.current_inventory()
        monitored_metrics = self._metric_mgr.get_monitored_metrics()
        perf_manager = self._si.RetrieveServiceContent().perfManager
        for inv_obj in itertools.chain(*inv_objs.values()):
            inv_obj_metrics = inv_obj.metric_id_map
            desired_keys = (inv_obj_metrics.keys() & monitored_metrics.keys())
            metric_id_objs = [inv_obj_metrics[key] for key in desired_keys]
            query_spec = vim.PerformanceManager.QuerySpec(
                entity=inv_obj.mor, metricId=metric_id_objs,
                intervalId=inv_obj.INSTANT_INTERVAL,
                maxSample=1, format='normal'
            )
            results = perf_manager.QueryPerf(querySpec=[query_spec])
            dps = self._parse_query(inv_obj, results, monitored_metrics)
            payload = self._build_payload(dps)
            self._dispatch_metrics(payload)

    def send_metadata_metrics(self):
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
        self._inventory_mgr.stop()
        self._metric_mgr.stop()
        self._inventory_mgr.join(timeout=constants.DEFAULT_TIMEOUT)
        self._metric_mgr.join(timeout=constants.DEFAULT_TIMEOUT)

    class Datapoint(object):
        def __init__(self, metric_name, metric_type, value, dimensions, timestamp):
            self.metric_name = metric_name
            self.metric_type = metric_type
            self.value = value
            self.dimensions = dimensions
            self.timestamp = timestamp


