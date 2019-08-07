from environment import Environment
import time
import logging
import utils
import constants
import signal
import sys
import yaml
import datetime


logging.setLoggerClass(utils.VSphereLogger)
logger = logging.getLogger('VSphere')
envs = []


def _handle_exit_signal(signum, stack):
    """
    Custom Signal handler to handle exit signal.
    :param signum: Exit Signal
    :param stack:
    :return: null
    """
    if signum == signal.SIGUSR1:
        logger.info("Signal received. Exiting gracefully")
        _stop_envs(envs)
        sys.exit(0)


def _stop_envs(envs):
    """
    Stops all the Environments.
    :param envs: List of environments.
    :return: null

    """
    for env in envs:
        env.stop_managers()


def _get_config():
    """
    Open config file and get configuration for different environments.
    :return: List of plugin configs.

    """
    logger.info("Reading Config")
    plugin_config_list = []
    f = open(constants.CONFIG_FILE)
    data_map = yaml.load(f)
    for conf in data_map['config']:
        try:
            plugin_config = {}
            required_keys = ('host', 'username', 'password', 'Name', 'IngestToken')
            for key in required_keys:
                if key not in conf:
                    logger.error('Missing required config settings : {0}'.format(key))
                    raise ValueError("Missing required config settings : {0}".format(key))
            plugin_config['host'] = conf['host']
            plugin_config['username'] = conf['username']
            plugin_config['password'] = conf['password']
            plugin_config['Name'] = conf['Name']
            plugin_config['IngestToken'] = conf['IngestToken']
            plugin_config['IngestEndpoint'] = conf.get('IngestEndpoint', constants.DEFAULT_INGEST_ENDPOINT)
            plugin_config['IngestTimeout'] = conf.get('IngestTimeout', constants.DEFAULT_INGEST_TIMEOUT)
            if 'MORSyncInterval' in conf:
                plugin_config['MORSyncInterval'] = conf['MORSyncInterval']
            if 'MetricSyncInterval' in conf:
                plugin_config['MetricSyncInterval'] = conf['MetricSyncInterval']
            if 'MORSyncTimeout' in conf:
                plugin_config['MORSyncTimeout'] = conf['MORSyncTimeout']
            if 'MetricSyncTimeout' in conf:
                plugin_config['MetricSyncTimeout'] = conf['MetricSyncTimeout']
            if 'verbosity_level' in conf:
                plugin_config['verbosity_level'] = conf['verbosity_level']
            if 'IncludeMetrics' in conf:
                plugin_config['include_metrics'] = conf['IncludeMetrics']
            if 'ExcludeMetrics' in conf:
                plugin_config['exclude_metrics'] = conf['ExcludeMetrics']
            if 'Dimensions' in conf:
                plugin_config['dimensions'] = conf['Dimensions']
            plugin_config_list.append(plugin_config)
        except ValueError as e:
            logging.error(e)
            continue
    return plugin_config_list


def _run(config_list):
    """
    Creates environments(for each vCenter) from config list and runs the metric collection for all envs
    until exit signal is received.
    :param config_list:  List of plugin configuration for different environments.
    :return: null

    """
    signal.signal(signal.SIGUSR1, _handle_exit_signal)
    if len(config_list) == 0:
        logger.warning("No config to handle. Shutting down the client.")
        return
    for plugin_config in config_list:
        logger.info("Creating environments")
        try:
            env = Environment(plugin_config)
            envs.append(env)
        except Exception as e:
            logger.error("An error occured while setting up an environment: {0}".format(e))

    if len(envs) == 0:
        logger.warning("No environments were created. Shutting down the client")
        return
    while True:
        try:
            start_time = datetime.datetime.now()
            for env in envs:
                try:
                    """ Executes reading and sending of metrics."""
                    env.read_metric_values()
                    logger.info("Sent metrics for env : {0}".format(env.get_instance_id()))
                except Exception:
                    logger.exception("Failed to send metrics for env {0}".format(env.get_instance_id()))
                    continue
            end_time = datetime.datetime.now()
            exec_time = (end_time - start_time).seconds
            wait_time = constants.DEFAULT_COLLECTION_INTERVAL - exec_time
            if wait_time < 0:
                logger.warning("Execution took a lot of time : {0} seconds".format(exec_time))
            else:
                time.sleep(wait_time)
        except KeyboardInterrupt:
            logger.info("Exiting because of KeyBoardInterrupt")
            _stop_envs(envs)
            break
        except Exception as e:
            logger.error("Error occured : {0}".format(e))
            _stop_envs(envs)
            break


def main():
    config_list = _get_config()
    _run(config_list)


if __name__ == '__main__':
    main()
