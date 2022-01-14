# Gefyra client
The Gefyra client contains the developer machine side. Its main tasks are installation of the Gefyra Operator and
the setup of the docker network and the Cargo sidecar.

## Tasks
- install operator into cluster
- create docker network on the developer machine
- deploy app container into local docker network
- deploy Cargo sidecar into local docker network
- create _InterceptRequest_

## Commands
- `init`: setup local machine
- `run`: deploy a new app container into the cluster
- `bridge`: switch a new app container with a container that's running in the cluster
- `reset`: close down `run`/`bridge`
- `shutdown`: undo setup of local machine

## Run new app container in cluster
The Gefyra client can run a new app container in the Kubernetes cluster with `gefyra run`. 
A typical use case is a completely new application that doesn't has any deployed containers in the cluster yet.

Requirements:
- running local cluster or available remote cluster
- successful `gefyra init`

Tasks:
- fetch wireguard connection secrets from Kubernetes secret
- deploy cargo sidecar into local docker network
- deploy app container into local docker network
- TODO: can we use _InterceptRequest_ as it is here?

## Bridge a container
The Gefyra client can bridge (i.e. switch/intercept) a container that is already running in the Kubernetes cluster with `gefyra bridge`.
The container needs to be specified and can be any deployed container of any pod.

Requirements:
- running local cluster or available remote cluster
- successful `gefyra init`

Tasks:
- fetch wireguard connection secrets from Kubernetes secret
- deploy cargo sidecar into local docker network
- deploy app container into local docker network
- create _InterceptRequest_ 


## Create a cluster with `k3d`
### k3d version v4.4.x  
`k3d cluster create mycluster --agents 1 -p 8080:80@agent[0] -p 31820:31820/UDP@agent[0]`