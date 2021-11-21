# Gefyra Cargo
Gefyra _Cargo_ is installed in the local development environment and acts as a gateway for all _bridged_ development
containers.  
It allows completely new services to be part of the cluster (i.e. new applications) or, in addition, intercept a running
instance of that service and receive all traffic from within the cluster.  
Cargo provides the local end of the _Wireguard_ connection tunnel in the cluster and also operates a _CoreDNS_. Hence,
Cargo services all tasks that actually make the _bridge_ possible on Gefyra's local side.

## Basics
Cargo is based on [linuxserver/wireguard](https://docs.linuxserver.io/images/docker-wireguard) with a few 
extensions, such as DNS configurations. Cargo's image is created on-the-fly since Wireguard's server part 
[Stowaway](stowaway) generates the connection secrets dynamically. Gefyra retrieves the secrets and puts them into 
Cargo. A `docker build ...` creates the ephemeral container image which then will be able to connect to Stowaway. 
