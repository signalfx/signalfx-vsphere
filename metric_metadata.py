"""
Module containing a class for periodically syncing vCenter's latest metric
metadata with a local cache.
"""

import logging
import threading
import time
import vsphere_metrics


class MetricManager(threading.Thread):
    def __init__(self, si, refresh_interval, metric_conf, vc_name, instance_id, *args, **kwargs):
        self._si = si
        self._refresh_interval = refresh_interval
        self._required_metrics = vsphere_metrics.get_metrics(metric_conf)
        self._vc_name = vc_name
        self._logger = logging.getLogger("{0}-MM".format(instance_id))
        self._perf_manager = self._si.RetrieveServiceContent().perfManager
        threading.Thread.__init__(self, *args, **kwargs)
        self.daemon = True
        self.update_lock = threading.Lock()
        self._stop_signal = threading.Event()
        self._has_metrics = threading.Event()
        self._monitored_metrics = {}

    def _sync_metrics(self):
        """
        Syncs all the available required metrics.
        :return: null

        """
        monitored_metrics = {}
        available_metrics = {}
        for counter in self._perf_manager.perfCounter:
            metric_full_name = self._format_metric_full_name(counter)
            available_metrics[metric_full_name] = counter
        for mor in self._required_metrics.keys():
            mor_metrics = {}
            for metric in self._required_metrics[mor]:
                if metric in available_metrics.keys():
                    counter = available_metrics[metric]
                    if counter.key not in mor_metrics.keys():
                        mor_metrics[counter.key] = self._get_metric_info(counter, metric)
            monitored_metrics[mor] = mor_metrics
        with self.update_lock:
            self._monitored_metrics = monitored_metrics
        self._has_metrics.set()

    def _get_metric_info(self, counter, metric_name):
        units = self._determine_units(counter)
        metric_type = self._determine_metric_type(counter)
        metric = MetricInfo(metric_name, counter.level, metric_type, units)
        return metric

    def _determine_metric_type(self, perf_counter):
        """
        Determines the metric type (gauge, counter, or cumulative counter) of the passed-in
         performance counter object.
        :param perf_counter: Performance counter
        :return: string

        """
        if perf_counter.statsType in ['absolute', 'rate']:
            return "gauge"
        else:
            return "gauge"

    def _determine_units(self, perf_counter):
        """
        Determines the units of the metric
        :param perf_counter: Performance Counter
        :return: string

        """
        return perf_counter.unitInfo.key

    def _format_metric_name(self, perf_counter):
        group = perf_counter.groupInfo.key
        name = perf_counter.nameInfo.key
        return "{0}.{1}".format(group, name)

    def _format_metric_full_name(self, perf_counter):
        """
        Determines the metric name to send to SignalFx based on the performance counter's group and name keys.
        :param perf_counter: Performance Counter
        :return: string

        """
        group = perf_counter.groupInfo.key
        name = perf_counter.nameInfo.key
        rollup_type = perf_counter.rollupType
        return "{0}.{1}.{2}".format(group, name, rollup_type)

    def _is_metric_allowed(self, metric_full_name):
        """
        Determines if a metric should be reported based on configuration and available metrics.
        :param metric_full_name: Fully qualified metric name
        :return: Boolean
        """
        if metric_full_name not in self._required_metrics:
            return False
        else:
            return True

    def block_until_has_metrics(self, timeout=None):
        """
        Wait until the metric metadata cache is populated. Useful for right after the thread starts.
        :param timeout: The maximum time to wait before returning an exception
        :return: Boolean

        """
        return self._has_metrics.wait(timeout=timeout)

    def get_monitored_metrics(self):
        with self.update_lock:
            return self._monitored_metrics

    def run(self):
        while not self._stop_signal.is_set():
            next_interval = time.time() + self._refresh_interval
            try:
                self._sync_metrics()
            except Exception as e:
                self._logger.warning(
                    "Exception when syncing available vCenter metrics continuing anyway: {0}".format(e))
            except KeyboardInterrupt:
                break

            sleep_time = next_interval - time.time()
            self._logger.info("vCenter metric metadata sync complete. Next sync in {0} seconds".format(sleep_time))

            if sleep_time < 0:
                self._logger.warning("Vcenter metric metadata sync time exceeded the refresh interval")
            while (not self._stop_signal.is_set() and time.time() < next_interval):
                time.sleep(1)

    def stop(self):
        self._stop_signal.set()


class MetricInfo(object):
    def __init__(self, name, level, metric_type, units):
        self.name = name
        self.level = level
        self.metric_type = metric_type
        self.units = units

    def __str__(self):
        return ("MetricInfo(name={0},level={1},metric_type={2},units={3}"
                .format(self.name, self.level, self.metric_type, self.units))

    __repr__ = __str__
