import requests
import json

import atexit

from pyVim import connect

# import tools.cli as cli

class Client:

    headers = { "Accept": "application/json", "Content-Type": "application/json"}

    url_base = ""

    token = ""

    def authenticate_vrops(self, url_base, username, password):

        # Get security token
        #
        self.url_base = url_base
        credentials = json.dumps({ "username": username, "password": password })
        result = requests.post(url=url_base + "/auth/token/acquire",
                               data=credentials,
                               verify=False, headers=self.headers)
        if result.status_code != 200:
            print str(result.status_code) + " " + result.content
            exit(1)
        json_data = json.loads(result.content)
        token = json_data["token"]
        self.headers["Authorization"] = "vRealizeOpsToken " + token

    def get(self, url):
        print(self.url_base + url)
        result = requests.get(url=self.url_base + url,
                              headers=self.headers,
                              verify=False)
        return result

    def post(self, url, data):
        result = requests.post(url=self.url_base + url,
                              headers=self.headers,
                              verify=False,
                                data=data)
        return result

    def authenticate_vc(self, host, username, password, port=443):
        vc = connect.SmartConnectNoSSL(host=host,
                                       user=username,
                                       pwd=password,
                                       port=port)
        atexit.register(connect.Disconnect, vc)
        return vc