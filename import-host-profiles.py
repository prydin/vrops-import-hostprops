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
import time

from pyVmomi import vim

# Parse arguments
#
parser = argparse.ArgumentParser(description='Import host profile settings to vRealize Operations')
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
hpm = content.hostProfileManager
root = content.rootFolder
hosts = content.viewManager.CreateContainerView(root, [vim.HostSystem], True)

profiles = hpm.profile
for profile in profiles:
    task = profile.CheckProfileCompliance_Task()
    while task.info.state != "error" and task.info.state != "success":
        time.sleep(1)
    if task.info.result == "error":
        print("Error checking profile: " + profile.name)
        continue

    for resourceResult in task.info.result:
        print(resourceResult.entity.summary.config.name)

        # Look up host in vR Ops
        #
        host_name = resourceResult.entity.summary.config.name
        query = urllib.urlencode({ "resourceKind": "HostSystem", "name": host_name})
        result = client.get("/resources?" + query)
        if result.status_code != 200:
            print "Error: " + str(result.status_code) + ". Skipping " + host_name
            continue
        vrops_host = json.loads(result.content)
        if len(vrops_host["resourceList"]) == 0:
            print "Skipping " + host_name
            continue
        host_id = vrops_host["resourceList"][0]["identifier"]

        # Load current symptoms. We may need to clear some of them if we are back in compliance
        #
        result = client.get("/symptoms?resourceId=" + host_id + "&activeOnly=true&pageSize=10000")
        if result.status_code != 200:
            print "Error fetching symptoms: " + str(result.status_code) + ". Skipping " + host_name
            continue
        current_evt = {}
        for symptom in json.loads(result.content)["symptom"]:
            message = symptom["message"]
            if "Host profile violation" in message:
                current_evt[message] = True

        # Post events for all new violations
        #
        for failure in resourceResult.failure:
            evt_message = "Host profile violation: " + failure.message.message
            event = {
                "eventType": "NOTIFICATION",
                "resourceId": host_id,
                "message": evt_message,
                "managedExternally": True,
                "startTimeUTC": long(time.time() * 1000)
            }
            result = client.post("/events", json.dumps(event))
            if result.status_code != 200:
                print "Error posting event: " + str(result.status_code)
            if evt_message in current_evt:
                del current_evt[evt_message]
            print "Sent event " + evt_message

        # Delete all events corresponding to rules no longer violated
        #
        print "Deleting " + str(len(current_evt)) + " old events"
        for key in current_evt:
            event = {
                "eventType": "NOTIFICATION",
                "resourceId": host_id,
                "message": key,
                "managedExternally": True,
                "cancelTimeUTC": long(time.time() * 1000)
            }
            result = client.post("/events", json.dumps(event))
            if result.status_code != 200:
                print "Error posting event: " + str(result.status_code)