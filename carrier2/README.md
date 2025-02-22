# Carrier2 - the next generation of HTTP(s) dispatcher for Gefyra (written in Rust)

## Gefyra Bridge Object
The Gefyra bridge object describes the dispatching configuration for Carrier2.
We always want a default upstream: the shaddow deployment created for a GefyraMount object.
Every Gefyra user bridge is subsequently added to Carrier2 to match certain HTTP attributes, for example
a header value or a path prefix, and directed to the local Gefyra client.


### Example Config and Structure
```yaml
version: 1
port: 8080
clusterUpstream: 
    - "podname.target-ns.pod.cluster.local:8000"
    - "10.28.100.46:8000"
    - "10.28.100.66:8000"  # the pods serving the cluster traffic, replication 3
httpGetProbes: 
    - 8001
    - 8002
bridges:
    user-1:
        endpoint: "stowaway-port-10001.gefyra.svc.cluster.local:10001"
        rules:
            # and
            - matchHeader:
                name: "x-gefyra"
                value: "user-1"
              matchPath: 
                path: "/my-svc"
                type: "prefix"
            # or
            - matchPath:
                path: "/always"
                type: "prefix"
```

## Run a dev version with debug ouput
`RUST_LOG=debug cargo run -- -c conf.yaml`
