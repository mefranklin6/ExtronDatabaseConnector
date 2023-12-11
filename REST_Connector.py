import json
from datetime import datetime
from extronlib.system import Wait
import urllib.request
import urllib.error

"""
https://github.com/mefranklin6/ExtronDatabaseConnector

Communicates with a proxy server via REST-like API
The proxy server then interacts with a SQL database

This is a module that is ran by the Extron control processor.

Requires FastAPI_Server.py to be running on an external x86 server
"""


class REST_Connector:
    def __init__(self, processor_name: str, proxy_server_ip: str):
        self.ProcessorName = processor_name
        self.proxy_server = proxy_server_ip
        self.current_input = (
            None  # mutually exclusive, set by group="Inputs" in start_metric()
        )
        self.EnableAPI_Metrics = (
            False  # call get_global_api_metrics_enable() after initialize to set this
        )

    def get_global_api_metrics_enable(self):
        """IMPORTANT: this calls rest_read() which is blocking!
        Please see the doc string for rest_read()
        and call this function with the @Wait(0.1) decorator

        This is a health check of the proxy server and the database.

        Example:
        def FunctionInMain():
            @Wait(0.1)
            def CheckMetricServer():
                API.EnableAPI_Metrics = API.get_global_api_metrics_enable()

            <syncronous code here>

        """

        url = "{}/global/enable".format(self.proxy_server)
        result = self.rest_read(url, timeout=15)

        if result == "True":
            print("Found Global Trigger set to True: Enabling API Metrics")
            self.EnableAPI_Metrics = True
            return True

        elif result == "False":
            print("Global API Metrics Trigger found, but it is set to False")
        else:
            print(
                "API Metrics not enabled.  Could not connect to proxy server at {}".format(
                    url
                )
            )
        self.EnableAPI_Metrics = False
        return False

    def _rest_send_metric(self, action, metric_name):
        if self.EnableAPI_Metrics != True:
            return None

        time = datetime.now()
        time_str = time.strftime("%Y-%m-%dT%H:%M:%S")

        def _rest_send_metric_inner(action, metric_name):
            data = {
                "Processor": self.ProcessorName,
                "Time": time_str,
                "Metric": metric_name,
                "Action": action,
            }

            data = json.dumps(data).encode()
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(self.proxy_server, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    print(json.loads(response.read().decode()))
            except:
                print("Proxy Server Timeout")

        @Wait(0.1)  # wait decorator multi-thread hack
        def _multi_thread_rest_metric_send():
            _rest_send_metric_inner(action, metric_name)

    # Called from main
    def start_metric(self, metric_name, group=None):
        if group:
            return self._handle_group(metric_name, group)

        self._rest_send_metric("Started", metric_name)

    # Called from main
    def stop_metric(self, metric_name, group=None):
        self._rest_send_metric("Stopped", metric_name)

    def _handle_group(self, metric_name, group):
        # Mutually exclusive per group

        # ignores users pressing the same button as current input
        if self.current_input == metric_name:
            return

        if group == "Inputs":
            if self.current_input != None:
                self.stop_metric(self.current_input)
                self.current_input = metric_name
            else:  # handles fresh boot state
                self.current_input = metric_name

            self.start_metric(self.current_input)

    def rest_read(self, url: str, timeout=4):
        """
        IMPORTANT: This function is blocking!
        If the proxy server is not reachable, the main thread is blocked
        until the timeout period.
        Always use @Wait(0.1) decorator when calling this function
        """

        try:
            with urllib.request.urlopen(url, timeout=timeout) as result:
                return json.loads(result.read().decode())
        except urllib.error.HTTPError as e:
            print("HTTPError: {} for {}".format(e.code, url))
        except urllib.error.URLError as e:
            print("URLError: {} for {}".format(e.reason, url))
