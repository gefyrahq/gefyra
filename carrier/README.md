# Gefyra Carrier
The Gefyra _Carrier_ is installed to any Kubernetes Pod that is requested to be intercepted. Gefyra's 
[Operator](../operator) overrides the requested Pod's container in the associated namespace with Carrier and configures 
it according to the specification.  
Carrier itself provides a way for Operator to dynamically set the listening port to allow any port to be forwarded by
Carrier to Stowaway.

## Basics
Carrier is implemented with Nginx. The default configuration is shipped with the container image. A simple addition
script rewrites Nginx's configuration and triggers the reload signal `nginx -s reload` at the end in order for Nginx
so serve the required port.

