# Copyright (c) 2018-2022 F5, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from mohawk import Sender
import requests
import os
import sys
import logging
import time
import subprocess
import uuid
import json
import boto3
import jq

logging.basicConfig(
    filename='/home/ubuntu/log/startup.log',
    filemode='a',
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info('-----------Initializing startup script-----------')
time.sleep(60)

def getApi(uri):
    URI = uri
    sender = Sender(credentials, URI, "GET", always_hash_content=False, ext=ORGANIZATION_ID )
    response = requests.get(URI, headers={'Authorization': sender.request_header})
    return response

def putApi(uri,payload):
    URI = uri
    sender = Sender(credentials, URI, "PUT", always_hash_content=True, ext=ORGANIZATION_ID, content=json.dumps(payload), content_type="application/json" )
    response = requests.put(URI, headers={'Authorization': sender.request_header, 'content-type': 'application/json'}, data=json.dumps(payload))
    return response

def postApi(uri,payload):
    URI = uri
    sender = Sender(credentials, URI, "POST", always_hash_content=True, ext=ORGANIZATION_ID, content=json.dumps(payload), content_type="application/json" )
    response = requests.post(URI, headers={'Authorization': sender.request_header, 'content-type': 'application/json'}, data=json.dumps(payload))
    return response

logging.info('Getting UDF User Tags')
r =requests.get('http://metadata.udf/userTags')
r.raise_for_status()
tags = r.json()
def getTags(tagName):
    try:
        for key, value in tags.get('userTags').get('name').get(tagName).get('value').items():
            if tagName == 'ENABLE_RULES' and value != None:
                return True
            else:
                return key
    except AttributeError:
        if tagName != 'RULESET' and tagName != 'ENABLE_RULES':
            logging.info('Tag %s is not defined. Exiting', tagName)
            exit(1)
        else:
            if tagName == 'RULESET':
                logging.info('No rulesets defined. Will enable rules in base, docker and k8s rulesets if "ENABLE_RULES" flag is set')
                return None
            else:
                logging.info('Not enabling any rules')
                return False
                

ACCOUNT_ID = getTags('ACCOUNT')
USER_ID = getTags('USER')
ORGANIZATION_ID = getTags('ORG')
TS_DEPLOY_KEY = getTags('DEPLOYMENT_KEY')
API_KEY = getTags('API_KEY')
ENABLE = getTags('ENABLE_RULES')
RULESET = getTags('RULESET')


logging.info('AIP Deployment key: ' + TS_DEPLOY_KEY)
values = requests.get('https://raw.githubusercontent.com/threatstack/threatstack-helm/master/values.yaml')
with open('/home/ubuntu/ts/values.yaml', 'wb') as f:
    f.write(values.content)
    f.close()
with open('/home/ubuntu/ts/values.yaml', 'r+') as f:
    data = ''.join([i for i in f if not i.lower().startswith('agentDeployKey')])
    f.seek(0)
    f.write(data)
    f.truncate()
    f.close()
with open('/home/ubuntu/ts/values.yaml', 'r') as f:
  filedata = f.read()
  filedata = filedata.replace('  # enableDocker: false', '  enableDocker: true')
  filedata = filedata.replace('  # enableContainerd: false', '  enableContainerd: true')
  f.close()
with open('/home/ubuntu/ts/values.yaml', 'w') as f:
  f.write(filedata)
  f.close()
with open('/home/ubuntu/ts/values.yaml', 'a') as v:
    v.write("agentDeployKey: " + TS_DEPLOY_KEY)
    v.close()
time.sleep(60)
subprocess.run("/snap/bin/helm delete threatstack-agents >> /home/ubuntu/log/startup.log", shell=True)
time.sleep(15)
subprocess.run("/snap/bin/helm install threatstack-agents --values /home/ubuntu/ts/values.yaml threatstack/threatstack-agent >> /home/ubuntu/log/startup.log", shell=True)

UUID = uuid.uuid4().hex
logging.info('Deploying Threatstack CFT. Stack Name: ' +'ts0-'+UUID)

template = requests.get('https://raw.githubusercontent.com/threatstack/threatstack-cloudformation/master/threatstack.json').text

cloudformation = boto3.resource('cloudformation')
stack = cloudformation.create_stack(
    StackName='ts0-'+UUID,
    TemplateBody=template,
    Parameters=[
        {
            'ParameterKey': 'TSAccountID',
            'ParameterValue': ACCOUNT_ID
        },
        {
            'ParameterKey': 'TSBucketName',
            'ParameterValue': 's3ts0-'+UUID
        },
        {
            'ParameterKey': 'TSExternalID',
            'ParameterValue': 'ext123'
        },
        {
            'ParameterKey': 'TSTopicName',
            'ParameterValue': 'sqsts0-'+UUID
        }
    ],
    Capabilities=['CAPABILITY_IAM']
    )
client = boto3.client('cloudformation')
def stack_exists(name, required_status = 'CREATE_COMPLETE'):
    try:
        data = client.describe_stacks(StackName = name)
    except ClientError:
        return False
    return data['Stacks'][0]['StackStatus'] == required_status

while not stack_exists('ts0-'+UUID):
    logging.info('Still deploying CFT...')
    time.sleep(30)

out = client.describe_stacks(StackName='ts0-'+UUID)
outp = json.dumps(out, indent=4, sort_keys=True, default=str)
outputs = json.loads(outp)

logging.info('Populating AWS outputs')

ARN = jq.compile('.Stacks[].Outputs[] | select(.OutputKey=="RoleARN").OutputValue').input(outputs).first()
SQS = jq.compile('.Stacks[].Outputs[] | select(.OutputKey=="SQSSource").OutputValue').input(outputs).first()
S3 = jq.compile('.Stacks[].Outputs[] | select(.OutputKey=="S3Bucket").OutputValue').input(outputs).first()
REGION = jq.compile('.Stacks[].Outputs[] | select(.OutputKey=="CloudTrailRegion").OutputValue').input(outputs).first()

HOST = "api.threatstack.com"
BASE_PATH = 'https://' + HOST
URI_PATH = '/v2/integrations/aws'

credentials = {
    'id': USER_ID,
    'key': API_KEY,
    'algorithm': 'sha256'
}
URL = BASE_PATH + URI_PATH
logging.info('Creating AWS Integration')
payload1 = {'arn': ARN, 'description': 'UDF AWS CloudTrail integration'}
response1 = postApi(URL,payload1)
ID = response1.json().get("id")
with open('/var/tmp/int_id', 'w') as f:
    f.write(ID)
    f.close()
EXT_ID = response1.json().get("externalId")
if response1.status_code != 201:
        logging.info('Something went wrong...Aborting startup script. Response:' + str(response1.status_code))
        exit(1)
else:
        logging.info('Successfully created integration ID:' + ID)

logging.info('Updating Threatstack CFT: Changing TSExternalID in User Role ')

upd_stack = client.update_stack(
    StackName='ts0-'+UUID,
    UsePreviousTemplate=True,
    Parameters=[
        {
            'ParameterKey': 'TSExternalID',
            'ParameterValue': EXT_ID
        },
        {
            'ParameterKey': 'TSBucketName',
            'UsePreviousValue': True
        },
        {
            'ParameterKey': 'TSAccountID',
            'UsePreviousValue': True
        },
    ],
    Capabilities=[
        'CAPABILITY_IAM']
        )

logging.info('Populating CloudTrail Params in AWS AIP Integration')

URL_CLOUDTRAIL = URL + '/' + ID + '/cloudtrail'
payload2 = {'source': SQS, 'region': REGION, 's3Bucket': S3}
response2 = putApi(URL_CLOUDTRAIL,payload2)
if response2.status_code != 204:
        logging.info('Something went wrong...Aborting startup script. Status code:' + str(response2.status_code))
        exit(1)
else:
        logging.info('Successfully populated all params')

#
# Enable rules defined in User Tag
#

if ENABLE:
    if RULESET != None:
        rulesets = RULESET
    else:
        rulesets = ['Base Rule Set','Docker Rule Set','Kubernetes Rule Set', 'CloudTrail Rule Set']
    RULES_URI = BASE_PATH + '/v2/rulesets'
    response = getApi(RULES_URI)
    resp_json = response.json()
    if response.status_code != 200:
            logging.info('Something went wrong...Aborting startup script. Status code:' + str(response.status_code))
            exit(1)
    else:
            for i in resp_json.get("rulesets"):
                if rulesets.count(i.get("name")) == 1:
                    base_ruleset = i.get("id")
                    base_rules = i.get("rules")
                    for r in base_rules:
                        RULE_URI = BASE_PATH + '/v2/rulesets' + '/' + base_ruleset + '/rules/' + r
                        response = getApi(RULE_URI)
                        json_data = response.json()
                        for item in json_data:
                            for key, value in json_data.items():
                                    if json_data["enabled"] == False:
                                            json_data["enabled"] = True
                    #    logging.info('JSON data: ' + str(json.dumps(json_data)))
                        if response.status_code != 200:
                            logging.info('Error retrieving the rule ' + r +'. Status code:' + str(response.status_code))
                        else:
                            payload = json_data
                            response = putApi(RULE_URI,payload)
                            if response.status_code != 200:
                                logging.info('Error enabling the rule ' + r +'. Status code:' + str(response.status_code))
                            else:
                                logging.info('Successfully enabled the rule ' + r )


logging.info('------------Startup script complete--------------')
os.remove('/home/ubuntu/ts/values.yaml')
exit(0)
