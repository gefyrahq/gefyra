<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/logo.png" alt="Gefyra Logo"/>
</p>

# Gefyra
Gefyra gives Kubernetes-("cloud-native")-developers a completely new way of writing and testing their applications. 
Gone are the times of custom `docker-compose` setups, Vagrants, custom scripts or other scenarios in order to develop (micro-)services
for Kubernetes.  

Gefyra offers you to:
- run services locally on a developer machine
- operate feature-branches in a production-like Kubernetes environment with all adjacent services
- write code in the IDE you already love, be fast, be confident
- leverage all the neat development features, such as debugger, code-hot-reloading, overriding environment variables
- run high-level integration tests against all dependent services
- keep peace-of-mind when pushing new code to the integration environment 
  
Compared to [Telepresence2](https://www.telepresence.io/docs/latest/reference/architecture/), Gefyra uses a Wireguard-based
VPN to connect with the Kubernetes cluster. Telepresence2 provides a broad connectivity with the cluster ("your development
machine becomes part of the cluster"), Gefyra instead establishes a very scoped connectivity based on a dedicated Docker-network on the
developer machine. In addition, Gefyra supports a couple of important use-cases such as the sidecar pattern 
(see: https://medium.com/bb-tutorials-and-thoughts/kubernetes-learn-sidecar-container-pattern-6d8c21f873d) and does not require
"sudo"-privileges during the development process.  
Anyway, if you feel you need other features that Telepresence2 provides and Gefyra misses, please give it a go. Gefyra was heavily 
inspired by Telepresence2.

Gefyra was designed to be fast and robust on an average developer machine and supports most platforms.

## Table of contents
- [What is Gefyra?](#what-is-gefyra)
- [Did I hear developer convenience?](#did-i-hear-developer-convenience)
- [Installation](#installation)
- [Try it yourself](#try-it-yourself)
- [How does it work?](#how-does-it-work)
  - [Docker](#docker)
  - [Wireguard](#wireguard)
  - [CoreDNS](#coredns)
  - [Nginx](#nginx)
  - [Rsync](#rsync)
- [Architecture of the entire development system](#architecture-of-the-entire-development-system)
  - [Local development setup](#local-development-setup)
  - [The _bridge_ operation in action](#the-_bridge_-operation-in-action)
- [Why "Gefyra"](#why-gefyra)
- [Credits](#credits)

## What is Gefyra?
Gefyra is a toolkit written in Python to organize a local development infrastructure in order to produce software for and with 
Kubernetes while having fun. It is installed on any development computer and starts its work when it is asked. Gefyra runs
as a user-space application and controls the local Docker host and Kubernetes via _Kubernetes Python Client_. 

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/gefyra-intro.png" alt="Gefyra controls docker and kubeapi"/>
</p>

(_Kubectl_ is not really required but kinda makes sense to be in this picture)

In order for this to work, a few requirements have to be satisfied:
- a Docker host must be available for the user on the development machine (it is convenient if [docker can be run without sudo-privileges](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user))
- there are a few container capabilities required on both sides, within the Kubernetes cluster and on the local computer
- a node port must be opened on the development cluster for the duration of the development work 

Gefyra makes sure your development container runs as part of the cluster while you still have full access to it. In addition,
Gefyra is able to intercept the target application running within the cluster, i.e. a container in a Pod, and tunnels all traffic hitting said container to the one running 
locally. Now, developers can add new code or fix bugs and run it right away in the Kubernetes cluster, or simply introspect the traffic. 
Gefyra provides the entire infrastructure to do so and provides a high level of developer convenience. 


## Did I hear developer convenience?
The idea is to relieve developers from the hassle to go back and forth to the integration system with containers. Instead, take
the integration system closer to the developer and make the development cycles as short as possible. No more waiting for the CI to complete
just to see the service failing on the first request. Cloud-native (or Kubernetes-native) technologies have completely changed the 
developer experience: infrastructure is increasingly becoming part of developer's business with all the barriers and obstacles, but also chances
to turn the software for the better.  
Gefyra is here to provide a development workflow with the highest convenience possible. It brings low setup times, rapid development, 
high release cadence and super-satisfied managers.

## Installation
Currently, you can install Gefyra only with `pip`:  
`pip install gefyra --upgrade`  
https://pypi.org/project/gefyra/

## Gotchas & Current Limitations
- Gefyra's VPN needs a reachable `NodePort`. In most non-local Kubernetes scenarios this requires to set a firewall rule
in order to **allow port 31820 for UDP traffic**. It's simple for most Cloud-providers ("Hyperscaler") and 
doable for custom installations, too.  
- Kubernetes-probes can be faked by Gefyra's Pod component ("Carrier") in order to keep Kubernetes from removing _bridged_ Pods.
However, this is currently only supported for `httpGet` probes. Otherwise, you need to turn off probes during development.
- You will experience issues if you want to _bridge_ containers in Pods which specify a specific `command` (other than common shells).
- This project is in a quite early stage. I assume there are still a few bugs around.




## Try it yourself
You can easily try Gefyra yourself following this small example:   
1) Follow the installation  
2) Create a a local Kubernetes cluster with `k3d` like so:    
**< v5** `k3d cluster create mycluster --agents 1 -p 8080:80@agent[0] -p 31820:31820/UDP@agent[0]`  
**>= v5** `k3d cluster create mycluster --agents 1 -p 8080:80@agent:0 -p 31820:31820/UDP@agent:0`  
This creates a Kubernetes cluster that binds port 8080 and 31820 to localhost. `Kubectl` context is immediately set to this cluster.
3) Apply some workload, for example from the testing directory:  
`kubectl apply -f testing/workloads/hello.yaml`
Check out this workload running under: http://hello.127.0.0.1.nip.io:8080/    
4) Set up Gefyra with `gefyra up`
5) Run a local Docker image with Gefyra in order to  make it part of the cluster.  
  a) Build your Docker image with a local tag, for example from the testing directory:  
   `cd testing/images/ && docker build -f Dockerfile.local . -t pyserver`  
  b) Execute Gefyra's run command:    
   `gefyra run -i pyserver -N mypyserver -n default`  
  c) _Exec_ into the running container and look around. You will find the container to run within your Kubernetes cluster.  
   `docker exec -it mypyserver bash`  
   `wget -O- hello-nginx` will print out the website of the cluster service _hello-nginx_ from within the cluster.
6) Create a bridge in order to intercept the traffic to the cluster application with the one running locally:    
`gefyra bridge -N mypyserver -n default --deployment hello-nginxdemo --port 80:8000 --container-name hello-nginx -I mypybridge`    
Check out the locally running server comes up under: http://hello.127.0.0.1.nip.io:8080/  
7) List all running _bridges_:  
`gefyra list --bridges`
8) _Unbridge_ the local container and reset the cluster to its original state: 
`gefyra unbridge -N mypybridge`
Check out the initial response from: http://hello.127.0.0.1.nip.io:8080/  
9) Remove Gefyra's components from the cluster with `gefyra down`
10) Remove the locally running Kubernetes cluster with `k3d cluster delete mycluster`

## How does it work?
In order to write software for and with Kubernetes, obviously a Kubernetes cluster is required. There are already a number of Kubernetes 
distributions available to run everything locally. A cloud-based Kubernetes cluster can be connected as well in order to spare the development
computer from blasting off.
A working _KUBECONFIG_ connection is required with appropriate permissions which should always be the case for local clusters. Gefyra installs the required 
cluster-side components by itself once a development setup is about to be established.

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/gefyra-overview.png" alt="Gefyra connects to a Kubernetes cluster"/>
</p>

With these components, Gefyra is able to control a local development machine, and the development cluster, too. Both sides are now in the hand of 
Gefyra.  
Once the developer's work is done, Gefyra well and truly removes all components from the cluster without leaving a trace.  

A few things are required in order to achieve this:
- a _tunnel_ between the local development machine and the Kubernetes cluster
- a local end of that tunnel to steer the traffic, DNS, and encrypt everything passing over the line
- a cluster end of the tunnel, forwarding traffic, taking care of the encryption
- a local DNS resolver that behaves like the cluster DNS
- sophisticated IP routing mechanisms
- a traffic interceptor for containers already running withing the Kubernetes cluster

Gefyra builds on top of the following popular open-source technologies:

### Docker
[*Docker*](https://docker.io) is currently used in order to manage the local container-based development setup, including the
host, networking and container management procedures.

### Wireguard
[*Wireguard*](https://wireguard.com) is used to establish the connection tunnel between the two ends. It securely encrypts the UDP-based traffic
and allows to create a _site-to-site_ network for Gefyra. That way, the development setup becomes part of the cluster and containers running locally 
are actually able to reach cluster-based resources, such as databases, other (micro)services and so on.

### CoreDNS
[*CoreDNS*](https://coredns.io) provides local DNS functionality. It allows resolving resources running within the Kubernetes cluster.

### Nginx
[*Nginx*](https://www.nginx.com/) is used for all kinds of proxying and reverse-proxying traffic, including the interceptions of already running containers
in the cluster.

### Rsync
[*Rsync*](https://rsync.samba.org/) is used to synchronize directories from containers running in the cluster to local
instances. This is particularly important for Kubernetes service account tokens during a bridge operation.

## Architecture of the entire development system

### Local development setup
The local development happens with a running container instance of the application in question on the developer machine.
Gefyra takes care of the local Docker host setup, and hence needs access to it. It creates a dedicated Docker network 
which the container is deployed to. Next to the developed application, Gefyra places a _sidecar_ container. This container,
as a component of Gefyra, is called _Cargo_.  
Cargo acts as a network gateway for the app container and, as such, takes care of the IP routing into and from the cluster.
In addition, Cargo provides a CoreDNS server which forwards all requests to the cluster. That way, the app container will be
able to resolve cluster resources and may not resolve domain names that are not supposed to be resolved (think of 
isolated application scenarios).
Cargo encrypts all the passing traffic with _Wireguard_ using ad-hoc connection secrets. 

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/gefyra-development.png" alt="Gefyra local development"/>
</p>

This local setup allows developers to use their existing tooling, including their favorite code editor and debuggers. The
application, when it is supported, can perform code-hot-reloading upon changes and pipe logging output to a local shell 
(or other systems).  
Of course, developers are able to mount local storage volumes into the container, override environment variables and modify
everything as they'd like to.  
Replacing a container in the cluster with a local instance is called _bridge_: from an architectural perspective the local
application is _bridged_ into the cluster.
If the container is already running within a Kubernetes Pod, it gets replaced and all traffic to the originally running 
container is proxied to the one on the developer machine.  
During the container startup of the application, Gefyra modifies the container's networking from the outside and sets the 
_default gateway_ to Cargo. That way, all container's traffic is passed to the cluster via Cargo's encrypted tunnel. The
same procedure can be applied for multiple app containers at the same time.  

The neat part is that with a debugger and two or more _bridged_ containers, developers can introspect requests from the source
to the target and back around while being attached to both ends.

### The _bridge_ operation in action 
This chapter covers the important _bridge_ operation by following an example.

#### Before the bridge operation
Think of a provisioned Kubernetes cluster running some workload. There is an Ingress, Kubernetes Services and Pods running
containers. Some of them use the _sidecar_ (https://medium.com/nerd-for-tech/microservice-design-pattern-sidecar-sidekick-pattern-dbcea9bed783) pattern.

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/gefyra-process-step-1.png" alt="Gefyra development workflow_step1"/>
</p>

#### Preparing the bridge operation
Before the _brigde_ can happen, Gefyra installs all required components to the cluster. A valid and privileged connection
must be available on the developer machine to do so.  
The main component is the cluster agent called _Stowaway_. The Stowaway controls the cluster side of the tunnel connection.
It is operated by [Gefyra's Operator application](operator).

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/gefyra-process-step-2.png" alt="Gefyra development workflow step 2"/>
</p>

Stowaway boots up and dynamically creates Wireguard connection secrets (private/public key-pair) for itself and Cargo.
Gefyra copies these secrets to Cargo for it to establish a connection. This is a UDP connection. It requires a Kubernetes
Service of kind _nodeport_ to allow the traffic to pass through *for the time of an active development session*. Gefyra's 
operator installs these components with the requested parameters and removes it after the session terminates.  
By the way: Gefyra's operator removes all components and itself from the cluster in case the connection was disrupted 
for some time, too.  
Once a connection could be establised from Cargo to Stowaway (after running `gefyra up`), Gefyra can spin up the app container on the local side for the
developer to start working (by running `gefyra run ...`).   
Another job of Gefyra's operator is to rewrite the target pods, i.e. exchange the running container through Gefyras proxy,
called _Carrier_ (upon running `gefyra bridge ...`).  
For that, it creates a temporary Kubernetes Service that channels the Ingress traffic (or any other kind of cluster internal
traffic) to the container through Stowaway and Cargo to the locally running app container. 


#### During the bridge operation
A bridge can robustly run as long as it is required to (given the connection does not drop in the meanwhile).
Looking at the example, Carrier was installed in pod &lt;C&gt; on port _XY_. That port was previously occupied by the container
running there originally. In most cases, the local app container represents the development version of that originally
provisioned container. Traffic coming from the Ingress, passing on to the Service &lt;C&gt; hits Carrier (the proxy). Carrier
bends the request to flow through Gefyras Service to the local app container via Stowaway and Cargo's tunnel. This works
since the app container's IP is routable from within the cluster.  
The local app container does not simply return a response, but fires up another subsequent request by itself to 
Service &lt;A&gt;. The request roams from the local app container back into the cluster and hits Pod &lt;A&gt;'s container via 
Service &lt;A&gt;. The response is awaited.  
Once the local app container is done with constructing its initial answer the response gets back to Carrier and afterwards
to the Ingress and back to the client.

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/gefyra-process-step-3.png" alt="Gefyra development workflow step 3"/>
</p>

With that, the local development container is reachable exactly the same way another container from within the cluster 
would be. That fact is a major advantage, especially for frontend applications or domain-sensitive services.  
Developers now can run local integration tests with new software while having access to all interdependent services.  
Once the development job is done, Gefyra properly removes everything, resets Pod &lt;C&gt; to its original configuration,
and tears the local environment down (just like nothing ever happened).

Doge is excited about that.

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/doge.jpg" alt="Doge is excited"/>
</p>

## Why "Gefyra"
"Gefyra" is the Greek word for "Bridge" and fits nicely with kubernetes' nautical theme.

## Credits
Gefyra is based on well-crafted open source software. Special credits go to the teams of 
[https://www.linuxserver.io/](linxuserver.io) and [https://git.zx2c4.com/wireguard-go/about/](Wireguard(-go)). Please
be sure to check out their awesome work.  
Gefyra was heavily inspired by the free part of Telepresence2.





