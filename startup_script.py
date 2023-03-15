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

logging.info('Getting UDF User Tags')
r =requests.get('http://metadata.udf/userTags')
r.raise_for_status()
tags = r.json()
ACCOUNT_ID = jq.compile(".userTags.name.ACCOUNT.value | keys[]").input(tags).first()
USER_ID = jq.compile(".userTags.name.USER.value | keys[]").input(tags).first()
ORGANIZATION_ID = jq.compile(".userTags.name.ORG.value | keys[]").input(tags).first()
TS_DEPLOY_KEY = jq.compile(".userTags.name.DEPLOYMENT_KEY.value | keys[]").input(tags).first()
API_KEY = jq.compile(".userTags.name.API_KEY.value | keys[]").input(tags).first()
# Add additionalSetupConfig: ""

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
sender1 = Sender(credentials, URL, "POST", always_hash_content=True, ext=ORGANIZATION_ID, content=json.dumps(payload1), content_type="application/json")
response1 = requests.post(URL, headers={'Authorization': sender1.request_header, 'content-type': 'application/json'}, data=json.dumps(payload1))

ID = response1.json().get("id")
with open('/var/tmp/int_id', 'w') as f:
    f.write(ID)
    f.close()
EXT_ID = response1.json().get("externalId")
if response1.status_code != 201:
        logging.info('Something went wrong...Aborting startup script. Response:' + response1.status_code.str())
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
sender2 = Sender(credentials, URL_CLOUDTRAIL, "PUT", always_hash_content=True, ext=ORGANIZATION_ID, content=json.dumps(payload2), content_type="application/json" )
response2 = requests.put(URL_CLOUDTRAIL, headers={'Authorization': sender2.request_header, 'content-type': 'application/json'}, data=json.dumps(payload2))
if response2.status_code != 204:
        logging.info('Something went wrong...Aborting startup script. Status code:' + response2.status_code.str())
        exit(1)
else:
        logging.info('Successfully populated all params')

#
# Add rule enable API calls HERE
#
"""
RULES_URI = BASE_PATH + '/v2/rulesets'
sender = Sender(credentials, RULES_URI, "GET", always_hash_content=True, ext=ORGANIZATION_ID )
response = requests.put(RULES_URI, headers={'Authorization': sender.request_header})
if response.status_code != 200:
        logging.info('Something went wrong...Aborting startup script. Status code:' + response2.status_code.str())
        exit(1)
else:
         for i in response['rulesets']:
            if i['name'] == 'Base Rule Set':
                base_ruleset = i['id']
                base_rules = i['rules']
                for r in base_rules:
                    RULE_URI = BASE_PATH + '/v2/rulesets' + '/' + base_ruleset + '/rules/' + r


            if i['name'] == 'Docker Rule Set':
                docker_ruleset = i['id']
                docker_rules = i['rules']
            if i['name'] == 'Kubernetes Rule Set':
                k8s_ruleset = i['id']
                k8s_rules = i['rules']


base, docker and k8s rulesets
    
"""


logging.info('------------Startup script complete--------------')
os.remove('/home/ubuntu/ts/values.yaml')
exit(0)
