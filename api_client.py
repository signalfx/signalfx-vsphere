import requests
import json

_HEADER_API_TOKEN_KEY = 'X-SF-Token'
_INGEST_ENDPOINT_DATAPOINT_SUFFIX = 'v2/datapoint'
DEFAULT_INGEST_ENDPOINT = 'https://ingest.signalfx.com'
DEFAULT_TIMEOUT = 20


class SignalFxIngestClient():
    def __init__(self, token, endpoint=DEFAULT_INGEST_ENDPOINT, timeout=DEFAULT_TIMEOUT):
        self._session = requests.Session()
        self._token = token
        self._endpoint = endpoint
        self._timeout = timeout
        headers = dict()
        headers['Content-Type'] = 'application/json'
        headers['X-SF-Token'] = self._token
        self._session.headers.update(headers)

    def send(self, gauges=None, counters=None, cumulative_counters=None):
        if not gauges and not counters and not cumulative_counters:
            return
        data = {
            'gauge': gauges,
            'counter': counters,
            'cumulative_counter': cumulative_counters
        }

        for metric_type, datapoints in data.items():
            if not datapoints:
                continue
            if not isinstance(datapoints, list):
                raise TypeError('Datapoints not of type list {0}'.format(datapoints))

        data = json.dumps(data)

        ingest_url = "{0}/{1}".format(self._endpoint, _INGEST_ENDPOINT_DATAPOINT_SUFFIX)
        try:
            s = self._session.post(ingest_url, data=data, timeout=self._timeout)
        except Exception as e:
            raise RuntimeError(e)
