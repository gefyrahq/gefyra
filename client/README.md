<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/logo.png" alt="Gefyra Logo"/>
</p>

# Gefyra
Gefyra gives Kubernetes-("cloud-native")-developers a completely new way of writing and testing their applications. 
Gone are the times of custom Docker-compose setups, Vagrants, custom scripts or other scenarios in order to develop (micro-)services
for Kubernetes.  

# Gefyra Client
The Gefyra client contains a library and a CLI to run Gefyra on a developmer machine. Its main tasks are installation of
the Gefyra Operator and the setup of the Docker network and the Cargo sidecar to prepare Gefyra's development 
infrastructure. For more information please go to: https://gefyra.dev

## Commands
- `up`: setup local development infrastructure
- `run`: deploy a new app container into the cluster
- `bridge`: intercept the traffic to a container that's running in the cluster and send it to the development container
- `unbridge`: remove active traffic intercepts and reset the cluster to its original state
- `down`: remove Gefyra's development infrastructure
- `list`: list running containers and active bridges
- `check`: check local system dependencies 
- `version`: print the current version and exit

## Run new app container in cluster
The Gefyra client can run a new app container in the Kubernetes cluster with `gefyra run ...`. 
A typical use case is a completely new application that doesn't have any deployed containers in the cluster yet.

Requirements:
- running local cluster or available remote cluster
- `kubectl` connection to development cluster is active
- a successful `gefyra up`

## Bridge a container
The Gefyra client can bridge (i.e. intercept) a container that is already running in the Kubernetes cluster with `gefyra bridge`.
The container needs to be specified and can be any deployed container of any pod.

Requirements:
- running local cluster or available remote cluster
- `kubectl` connection to development cluster is active
- successful `gefyra up`
- successful `gefyra run ...`

# More Information
Find more information and issues on Github: https://github.com/gefyrahq/gefyra