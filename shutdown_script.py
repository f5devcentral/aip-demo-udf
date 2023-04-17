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
import requests, os, logging, jq


logging.basicConfig(
    filename='/home/ubuntu/log/shutdown.log',
    filemode='a',
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info('-----------Initializing shutdown script-----------')

def getTagsUrl(url):
    r =requests.get(url)
    r.raise_for_status()
    tagsUrl = r.json()
    return tagsUrl

def getTags(tagName, tags):
    value = tags.get(tagName)
    if value != None:
        if tagName == 'ENABLE_RULES':
            return True
        else:
            return value
    else:
        if tagName != 'RULESET' and tagName != 'ENABLE_RULES':
            logging.info('Mandatory Deployment Tag %s is not defined. Exiting', tagName)
            exit(1)
        else:
            logging.info('Optional %s Deployment Tag is not defined', tagName)
            return False

# Accommodating old UserTags
def getUserTags(tagName, tags):
    try:
        for key, value in tags.get('userTags').get('name').get(tagName).get('value').items():
            if tagName == 'ENABLE_RULES' and value != None:
                return True
            else:
                return key
    except AttributeError:
        if tagName != 'RULESET' and tagName != 'ENABLE_RULES':
            logging.info('Mandatory User Tag %s is not defined. Exiting', tagName)
            exit(1)
        else:
            logging.info('Optional %s User Tag is not defined', tagName)
            return False

# See which tags are defined by the user (compatibility with older BP versions)
oldUrl = 'http://metadata.udf/userTags'
newUrl = 'http://metadata.udf/deploymentTags'

logging.info('Getting UDF Deployment/User Tags')
tags = getTagsUrl(newUrl)
USER_ID = tags.get('USER')
if USER_ID != None:
    logging.info('Found USER_ID tag in Deployment tags. Using new URL')
    url = newUrl
    proc = getTags
else:
    tags = getTagsUrl(oldUrl)
    try:
        for key, value in tags.get('userTags').get('name').get('USER').get('value').items():
            if value != None:
                url = oldUrl
                proc = getUserTags
            else:
                logging.info('User Tags seem to be missing a value. Exiting')
                exit(1)
    except AttributeError:
        logging.info('Could not find User Tags. Exiting')
        exit(1)

tags = getTagsUrl(url)
USER_ID = proc('USER', tags)
ORGANIZATION_ID = proc('ORG', tags)
API_KEY = proc('API_KEY', tags)

try:
    with open('/var/tmp/int_id', 'r') as f:
        id = f.read()
        f.close()
except OSError:
    logging.info("Integration ID file doesn't exist. Exiting")
    exit(1)
    
HOST = "api.threatstack.com"
BASE_PATH = 'https://' + HOST
URI_PATH = '/v2/integrations/aws'

credentials = {
    'id': USER_ID,
    'key': API_KEY,
    'algorithm': 'sha256'
}
URL = BASE_PATH + URI_PATH + '/' + id
payload = ""
logging.info('Removing AWS Integration ID: ' + id)
sender = Sender(credentials, URL, "DELETE", content=payload, always_hash_content=False, ext=ORGANIZATION_ID)
response = requests.delete(URL, data=payload, headers={'Authorization': sender.request_header})

if response.status_code != 204:
        logging.info('Something went wrong...Aborting shutdown script. Response:' + str(response.status_code))
        exit(1)
else:
        logging.info('Successfully removed AWS integration')


logging.info('------------Shutdown script complete--------------')
os.remove('/var/tmp/int_id')
exit(0)
