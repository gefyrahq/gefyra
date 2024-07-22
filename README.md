<div id="top"></div>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![Coverage Information][coveralls-shield]][coveralls-url]
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/8NTPMVPaKy)


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/gefyrahq/gefyra">
    <img src="https://github.com/gefyrahq/gefyra/raw/main/docs/static/img/logo.png" alt="Gefyra Logo"/>
  </a>

  <h3 align="center">Gefyra</h3>

  <p align="center">
    Blazingly-fast, rock-solid, local application development with Kubernetes!
    <br />
    <a href="https://gefyra.dev"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://gefyra.dev/try-it-out/">Try it yourself</a>
    ·
    <a href="https://github.com/gefyrahq/gefyra/issues">Report Bug</a>
    ·
    <a href="https://github.com/gefyrahq/gefyra/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#quick-start">Quick Start</a>
      <ul>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#your-first-bridge">Your First Bridge</a></li>
      </ul>
    </li>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#running-gefyra">Running Gefyra</a></li>
        <li><a href="#cleaning-up">Cleaning up</a></li>
      </ul>
    </li>
    <li><a href="#why-gefyra">Why "Gefyra"</a></li>    
    <li><a href="#license">License</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- QUICK START -->
## Quick Start
Short manual on where and how to start. You can find detailed information
[here (installation)](https://gefyra.dev/installation/) and [here (usage)](https://gefyra.dev/getting-started/).

### Installation

#### CLI

We offer platform specific installations:
<details>
  <summary>Linux/MacOS via script/cURL</summary>

```shell
curl -sSL https://raw.githubusercontent.com/gefyrahq/gefyra/main/install.sh | sh -
```
</details>
<details>
  <summary>MacOS via Homebrew</summary>

```shell
brew tap gefyrahq/gefyra
brew install gefyra
```
</details>
<details>
  <summary>Windows (Manual)</summary>

Download the latest binary for Windows under [here](https://github.com/gefyrahq/gefyra/releases/). 
</details>

#### Docker Desktop Extension

Working with Docker Desktop? We offer an [extension](https://open.docker.com/extensions/marketplace?extensionId=gefyra/docker-desktop-extension) to operate Gefyra through a UI on Docker Desktop.


### Your First Bridge
Make sure Gefyra is installed on your cluster (`gefyra up`). Some details of the installation depend on your Kubernetes' platform.
Check out our [docs](https://gefyra.dev) for more details.

Bridge a local container into an existing cluster. For a detailed guide please
check out this [article](https://gefyra.dev/getting-started/k3d/#running-gefyra).
1. Run a local available image with Gefyra:
```shell
gefyra run -i <image_name> -N <container_name> -n default
```
2. Create a bridge:
```shell
gefyra bridge -N <container_name> -n <k8s_namespace> --target deployment/<k8s_deployment>/<k8s_deployment_container>
```
Explanation for placeholders:
- `container_name` the name of the container you created in the previous step
- `k8s_namespace` the namespace your target workload runs in
- `k8s_deployment` the name of your target deployment
- `k8s_deployment_container` the name of the container within `k8s_deployment`
- `bridge_name` the name for the bridge being created

All available `bridge` flags are listed [here](https://gefyra.dev/reference/cli/#bridge).

<!-- ABOUT THE PROJECT -->
## About the project
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

<p align="right">(<a href="#top">back to top</a>)</p>

### Built with
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


<p align="right">(<a href="#top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started
You can easily try Gefyra yourself following this small example.

### Prerequisites
1) Follow the [installation](https://gefyra.dev/installation) for your preferred platform.

2) Create a local Kubernetes cluster with `k3d` like so:    
**< v5** `k3d cluster create mycluster --agents 1 -p 8080:80@agent[0] -p 31820:31820/UDP@agent[0]`  
**>= v5** `k3d cluster create mycluster --agents 1 -p 8080:80@agent:0 -p 31820:31820/UDP@agent:0`  
This creates a Kubernetes cluster that binds port 8080 and 31820 to localhost. `kubectl` context is immediately set to this cluster.
3) Apply some workload, for example from the testing directory of this repo:  
`kubectl apply -f testing/workloads/hello.yaml`
Check out this workload running under: http://hello.127.0.0.1.nip.io:8080/    

### Running Gefyra
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
`gefyra bridge -N mypyserver -n default --target deployment/hello-nginxdemo/hello-nginx --port 80:8000`    
Check out the locally running server comes up under: http://hello.127.0.0.1.nip.io:8080/  
7) List all running _bridges_:  
`gefyra list --bridges`
8) _Unbridge_ the local container and reset the cluster to its original state: 
`gefyra unbridge -N mypybridge`
Check out the initial response from: http://hello.127.0.0.1.nip.io:8080/  

### Cleaning up
9) Remove Gefyra's components from the cluster with `gefyra down`
10) Remove the locally running Kubernetes cluster with `k3d cluster delete mycluster`

<p align="right">(<a href="#top">back to top</a>)</p>

## Usage
Checkout [Gefyra's CLI](https://gefyra.dev/docs/cli) or [Guides](https://gefyra.dev/docs/getting-started-with-gefyra).

<p align="right">(<a href="#top">back to top</a>)</p>

## Why "Gefyra"
"Gefyra" is the Greek word for "Bridge" and fits nicely with Kubernetes' nautical theme.

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- LICENSE -->
## License
Distributed under the Apache License 2.0. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>

## Reporting Bugs
If you encounter issues, please create a new issue on GitHub or talk to us on the
[Unikube Slack channel](https://unikubeworkspace.slack.com/). 
When reporting a bug please include the following information:

Gefyra version or Git commit that you're running (gefyra version),
description of the bug and logs from the relevant `gefyra` command (if applicable),
steps to reproduce the issue, expected behavior.
If you're reporting a security vulnerability, please follow the process for reporting security issues.

## Acknowledgments
Gefyra is based on well-crafted open source software. Special credits go to the teams of 
[https://www.linuxserver.io/](https://www.linuxserver.io/) and [https://git.zx2c4.com/wireguard-go/about/](Wireguard(-go)). Please
be sure to check out their awesome work.  
Gefyra was heavily inspired by the free part of Telepresence2.  

Doge is excited about that.

<p align="center">
  <img src="https://github.com/Schille/gefyra/raw/main/docs/static/img/doge.jpg" alt="Doge is excited"/>
</p>
<p align="right">(<a href="#top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/gefyrahq/gefyra.svg?style=for-the-badge
[contributors-url]: https://github.com/gefyrahq/gefyra/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/gefyrahq/gefyra.svg?style=for-the-badge
[forks-url]: https://github.com/gefyrahq/gefyra/network/members
[stars-shield]: https://img.shields.io/github/stars/gefyrahq/gefyra.svg?style=for-the-badge
[stars-url]: https://github.com/gefyrahq/gefyra/stargazers
[issues-shield]: https://img.shields.io/github/issues/gefyrahq/gefyra.svg?style=for-the-badge
[issues-url]: https://github.com/gefyrahq/gefyra/issues
[license-shield]: https://img.shields.io/github/license/gefyrahq/gefyra.svg?style=for-the-badge
[license-url]: https://github.com/gefyrahq/gefyra/blob/master/LICENSE.txt
[coveralls-shield]: https://img.shields.io/coveralls/github/gefyrahq/gefyra/main?style=for-the-badge
[coveralls-url]: https://coveralls.io/github/gefyrahq/gefyra


