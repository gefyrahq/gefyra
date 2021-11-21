# Gefyra Operator
The Gefyra _Operator_ (name of the component) is installed in any Kubernetes development cluster to set up 
all required Gefyra cluster-side components. The operator runs as a Kubernetes deployment by its own.

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
  <img src="../docs/static/img/gefyra-operator.old.png" alt="Operator runs the cluster-side components"/>
</p>

## Basics
The Operator is written with the [Kopf framework](https://kopf.readthedocs.io/en/stable/). This framework utilizes
Python's _asyncio_ features.  
It will be _applied_ to the Kubernetes development cluster as a deployment by Gefyra's local client in a dedicated K8s 
namespace. Once running as container within the cluster, Operator will organize the cluster-side infrastructure using 
the Kubernetes API and wait for the Gefyra client to request intercepts. For that, Operator creates a custom resource 
definition (CRD): the _InterceptRequest_. Objects of that type are created by Gefyra to request container traffic 
interception.

## Boot up (init phase)
During the startup, Operator runs the following:
1) install the Stowaway as Kubernetes deployment (running _Wireguard_)
2) create and attach Stowaway's proxy routes configmap
3) install the `NodePort` Kubernetes service, reads the requested node port from its own environment (set by Gefyra 
   client)
4) create a headless service for Carriers to connect   
6) wait for Stowaway to become ready
7) extract ad-hoc generated connection details (secrets, IP range, ect.) from Stowaway and create a well-known secret 
   (for Gefyra to process)
8) register _InterceptionRequest_ custom resource definition, clusterroles and bindings
   
The following problems must be handled during the startup phase:
- another Gefyra (already, not yet terminated) running in that namespace
- the requested node port is busy already
- insufficient privileges granted for Stowaway, Stowaway not able to start successfully
- timeouts pulling container images (Operator, Stowaway)
- K8s service already present
- \[to be continued]

## Standby (standby phase)
Once the init phase is successfully complete, Operator enters the standby phase and reconciles the _InterceptionRequest_
custom resource definition.

## Creation of an interception route (interception phase)
Gefyra creates a InterceptionRequest object. Upon creation, Operator reads in the object's details. That is:
- namespace of Pod
- source Pod
- source container in Pod
- target IP address and port of the local container (the intercepted traffic's destination)

Gefyra pulls the environment of the target container in order to provide a copy to the local container instance. #Todo check permissions for different namespaces

Operator performs the following steps:
1) select a free reverse proxy route in Stowaway
2) add the route to Stowaway's proxy routes configmap
   - resolve target Pod's ip address
   - read the local container ip address and port
   - add proxy route to Stowaway: (source Pod's ip) -- proxy_pass --> (target ip and port)
3) create a service for Carrier in the target namespace (#todo check if required)
4) store target's container image and tag on the InterceptionRequest to restore in afterwards 
4) rewrite target Pod's container to use Carrier instead
5) configure Carrier to listen on the originally defined serving port (in order to forward traffic from that port)
6) set the InterceptionRequest object to `active` 

Once the route has been established, Operator gets back to the standby phase. 

   








