"""
Module containing a class for perodically syncing vCenter's latest metric
metadata with a local cache.
"""
import threading
import time

# Load the dummy collectd module if running this module outside of collectd
try:
    import collectd
except ImportError:
    import dummy_collectd as collectd


class MetricManager(threading.Thread):
    def __init__(self, si, refresh_interval, verbosity_level, vc_name,
                 *args, **kwargs):
        self._si = si
        self._refresh_interval = refresh_interval
        self._verbosity_level = verbosity_level
        self._vc_name = vc_name
        self._perf_manager = self._si.RetrieveServiceContent().perfManager
        threading.Thread.__init__(self, *args, **kwargs)
        self.daemon = True
        self.update_lock = threading.Lock()
        self._stop_signal = threading.Event()
        self._has_metrics = threading.Event()
        # Map of counter ID key to MetricInfo object
        self._monitored_metrics = {}

    def _sync_metrics(self):
        monitored_metrics = {}
        for counter in self._perf_manager.perfCounter:
            metric_name = self._format_metric_name(counter)
            if self._is_metric_allowed(metric_name, counter):
                units = self._determine_units(counter)
                metric_type = self._determine_metric_type(counter)
                metric = MetricInfo(
                    metric_name, counter.level, metric_type, units)
                monitored_metrics[counter.key] = metric
        with self.update_lock:
            self._monitored_metrics = monitored_metrics
        self._has_metrics.set()

    def _determine_metric_type(self, perf_counter):
        """
        Determines the metric type (gauge, counter, or cumulative
        counter) of the passed-in performance counter object.
        """
        # TODO: Add support for counters and cumulative counters
        return "gauge"

    def _determine_units(self, perf_counter):
        """
        Determines the units of the metric
        """
        return perf_counter.unitInfo.key

    def _format_metric_name(self, perf_counter):
        """
        Determines the metric name to send to SignalFx based on the
        performance counter's group and name keys
        """
        group = perf_counter.groupInfo.key
        name = perf_counter.nameInfo.key
        return "%s.%s" % (group, name)

    def _is_metric_allowed(self, metric_name, perf_counter):
        """
        Determine if a metric should be reported based on its verbosity
        level and the desired verbosity level.
        """
        if perf_counter.level > self._verbosity_level:
            return False
        else:
            return True

    def block_until_has_metrics(self, timeout=None):
        """
        Wait until the metric metadata cache is populated. Useful for right
        after the thread starts.

        Args:
            timeout (int): The maximum time to wait before returning a
                an exception

        Returns:
            True if metric metadata was retrieved within the timeout.
            False if the timeout was exceeded.
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
                collectd.error("Exception when syncing available vCenter "
                               "metrics, continuing anyway: %s" % e)
                raise  # *************TEMPORARY FOR TESTING************
            except KeyboardInterrupt:
                break
            # Wait until next time
            sleep_time = next_interval - time.time()
            collectd.info("vCenter metric metadata sync complete. Next sync "
                          "in %d seconds" % sleep_time)
            if sleep_time < 0:
                collectd.warning("vCenter metric metadata sync time exceeded "
                                 "the refresh interval")
            while (not self._stop_signal.is_set() and
                   time.time() < next_interval):
                time.sleep(1)

    def stop(self):
        self._stop_signal.set()


class MetricInfo(object):
    """
    Stores metadata for a single metric a.k.a. performance counter
    """
    def __init__(self, name, level, metric_type, units):
        self.name = name
        self.level = level
        self.metric_type = metric_type
        self.units = units

    def __str__(self):
        return ("MetricInfo(name=%s,level=%s,metric_type=%s,units=%s)" %
                (self.name, self.level, self.metric_type, self.units))

    __repr__ = __str__
