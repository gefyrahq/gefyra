# Gefyra Operator
The Gefyra Operator is installed in any Kubernetes development cluster to set up all required Gefyra cluster-side 
components. The operator runs as a Kubernetes deployment by its own.

## Tasks
Operator is responsible for the following tasks within the cluster:
- install the Kubernetes service of type `nodeport` (protocol `UDP`) for the local environment to connect to the cluster
- install Gefyra's Stowaway (Kubernetes deployment) in the matching version
- extract connection details and secrets from Stowaway
- process container intercept requests (a Kubernetes custom resource definition) using Carrier
  - watch intercept requests (InterceptRequest)
  - create a Kubernetes service for each intercept that translates to the local app container 
  - create a reverse proxy route in Stowaway 
  - edit the target Pod, install Carrier with matching configuration reading the Pod definition
  - reset everything once the intercept request was deleted
- monitor all tasks and communicate errors and warnings
- heartbeat Cargo
- reset the cluster to original state if requested or upon connection disruption; removes everything and itself  

<p align="center">
  <img src="docs/static/img/gefyra-operator.png" alt="Operator runs the cluster-side components"/>
</p>

