# Gefyra
Gefyra gives Kubernetes-("cloud-native")-developers a completely new way of writing and testing their applications. 
Gone are the times of custom Docker-compose setups, Vagrants, custom scrips or other scenarios in order to develop (micro-)services
for Kubernetes.  

# Gefyra Client
The Gefyra client contains the developer machine side. Its main tasks are installation of the Gefyra Operator and
the setup of the docker network and the Cargo sidecar in order to prepare Gefyra's development infrastructure.

## Tasks
- install Operator into cluster
- create Docker network on the developer machine
- deploy app container into local docker network
- deploy Cargo sidecar into local docker network
- create a bridge to intercept cluster traffic and bring it to the local development container

## Commands
- `up`: setup local development infrastructure
- `run`: deploy a new app container into the cluster
- `bridge`: intercept the traffic to a container that's running in the cluster and send it to the development container
- `unbridge`: remove active traffic intercepts and reset the cluster to its original state
- `down`: remove Gefyra's development infrastructure
- `list`: list running containers and active bridges
- `check`: check local system dependencies 

## Run new app container in cluster
The Gefyra client can run a new app container in the Kubernetes cluster with `gefyra run ...`. 
A typical use case is a completely new application that doesn't have any deployed containers in the cluster yet.

Requirements:
- running local cluster or available remote cluster
- `kubectl` connection to development cluster is active
- successful `gefyra up`

## Bridge a container
The Gefyra client can bridge (i.e. intercept) a container that is already running in the Kubernetes cluster with `gefyra bridge`.
The container needs to be specified and can be any deployed container of any pod.

Requirements:
- running local cluster or available remote cluster
- `kubectl` connection to development cluster is active
- successful `gefyra up`
- successful `gefyra run ...`

Tasks:
- fetch wireguard connection secrets from Kubernetes secret
- deploy cargo sidecar into local docker network
- deploy app container into local docker network
- create _InterceptRequest_ 


# More Information
Find more information on Github: https://github.com/Schille/gefyra