AIP AGENTS DEPLOYMENT AND AWS CLOUDTRAIL INTEGRATION
====================================================

For AWS CloudTrail integration to work **you MUST specify 5 User Tags below BEFORE STARTING THIS DEPLOYMENT**:

 - DEPLOYMENT_KEY
 - API_KEY
 -  ORG
 -  USER
 -  ACCOUNT

Optionally you can specify **ENABLE_RULES** tag and the system will automatically enable all rules in the following Rulesets:
 - Base Rule Set
 - Docker Rule Set
 - Kubernetes Rule Set
 - CloudTrail Rule Set

Values of Deployment Key (DEPLOYMENT_KEY), REST API Key (API_KEY), Organization ID (ORG) and UserID (USER) can be found in AIP Console : Settings -> Keys
Value of AccountID (ACCOUNT) can be found in AIP Console : Settings -> Integrations -> *Click on **ADD AWS INTEGRATION** and copy the value of **AccountID** *
**Example** of tags :

![tags](https://github.com/f5devcentral/aip-demo-udf/blob/main/user_tags.jpg?raw=true)

Click *ADD* after populating every tag
