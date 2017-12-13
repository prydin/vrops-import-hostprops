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

import argparse
import client
import urllib
import yaml
import json
import fnmatch
import time

from pyVmomi import vim

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
client = client.Client()
vrops_url_base = config["vropsUrl"] + "/suite-api/api"
token = client.authenticate_vrops(vrops_url_base, config["vropsUser"], config["vropsPassword"])
vc_host = config["vcHost"]

vc = client.authenticate_vc(vc_host, config["vcUser"], config["vcPassword"])
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
    result = client.get("/resources?" + query)

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
    result = client.post("/resources/" + vrops_host_id + "/properties",
                           data=json.dumps(payload))
    print "Processed " + host.name + ". Result=" + str(result.status_code)


