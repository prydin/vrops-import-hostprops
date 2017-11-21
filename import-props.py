'''
Copyright 2017 Pontus Rydin

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import requests
import json

import atexit

from pyVim import connect
from pyVmomi import vim

import fnmatch
import time
import urllib
import argparse
import yaml

# import tools.cli as cli

headers = { "Accept": "application/json", "Content-Type": "application/json"}

def authenticate_vrops(url_base, username, password):

    # Get security token
    #
    credentials = json.dumps({ "username": username, "password": password })
    result = requests.post(url=url_base + "/auth/token/acquire",
                           data=credentials,
                           verify=False, headers=headers)
    if result.status_code != 200:
        print str(result.status_code) + " " + result.content
        exit(1)
    json_data = json.loads(result.content)
    return json_data["token"]


def authenticate_vc(host, username, password, port = 443):
    vc = connect.SmartConnectNoSSL(host=host,
                                     user=username,
                                     pwd=password,
                                     port=port)
    atexit.register(connect.Disconnect, vc)
    return vc


# Parse arguments
#
parser = argparse.ArgumentParser(description='Import advanced host settings to vRealize Operations')
parser.add_argument('--config', dest='config', type=str,
                    help='Path to the config file')
args = parser.parse_args()

# Load config file
#
stream = file(args.config)
config = yaml.load(stream)
stream.close()

# Get current adapters
#
vrops_url_base = config["vropsUrl"] + "/suite-api/api"
token = authenticate_vrops(vrops_url_base, config["vropsUser"], config["vropsPassword"])
vc_host = config["vcHost"]
headers["Authorization"] = "vRealizeOpsToken " + token

vc = authenticate_vc(vc_host, config["vcUser"], config["vcPassword"])
content = vc.RetrieveContent()
root = content.rootFolder

# Collect properties to update
#
pattern = config["pattern"]
hosts = content.viewManager.CreateContainerView(root, [vim.HostSystem], True)
for host in hosts.view:

    # Look up host in vR Ops
    #
    query = urllib.urlencode({ "resourceKind": "HostSystem", "name": host.name})
    result = requests.get(url=vrops_url_base + "/resources?" + query,
                          headers=headers,
                          verify=False)
    vrops_host = json.loads(result.content)
    if len(vrops_host["resourceList"]) == 0:
        print "Skipping " + host.name
        continue

    props = []
    for c in host.config.option:
        if fnmatch.fnmatch(c.key, pattern):
            props.append({
                "statKey": "Advanced Settings|" + c.key,
                "timestamps": [int(time.time() * 1000)],
                "values": [c.value]
            })

    vrops_host_id = vrops_host["resourceList"][0]["identifier"]

    # Add properties
    #
    payload = {
        "property-content": props
    }
    result = requests.post(url=vrops_url_base + "/resources/" + vrops_host_id + "/properties",
                           data=json.dumps(payload),
                           verify=False,
                           headers=headers)
    print "Processed " + host.name + ". Result=" + str(result.status_code)


