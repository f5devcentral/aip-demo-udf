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
    filename='/home/ubuntu/log/shutdown.log',
    filemode='a',
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info('-----------Initializing shutdown script-----------')
logging.info('Getting UDF User Tags')
r =requests.get('http://metadata.udf/userTags')
r.raise_for_status()
tags = r.json()
USER_ID = jq.compile(".userTags.name.USER.value | keys[]").input(tags).first()
ORGANIZATION_ID = jq.compile(".userTags.name.ORG.value | keys[]").input(tags).first()
API_KEY = jq.compile(".userTags.name.API_KEY.value | keys[]").input(tags).first()

with open('/var/tmp/int_id', 'r') as f:
  id = f.read()
  f.close()

HOST = "api.threatstack.com"
BASE_PATH = 'https://' + HOST
URI_PATH = '/v2/integrations/aws'

credentials = {
    'id': USER_ID,
    'key': API_KEY,
    'algorithm': 'sha256'
}
URL = BASE_PATH + URI_PATH + '/' + id
logging.info('Removing AWS Integration ID: ' + id)
sender = Sender(credentials, URL, "DELETE", always_hash_content=False, ext=ORGANIZATION_ID)
response = requests.post(URL, headers={'Authorization': sender.request_header})

if response.status_code != 204:
        logging.info('Something went wrong...Aborting startup script. Response:' + response.status_code)
        exit(1)
else:
        logging.info('Successfully removed AWS integration')


logging.info('------------Shutdown script complete--------------')
os.remove('var/tmp/int_id')
exit(0)
