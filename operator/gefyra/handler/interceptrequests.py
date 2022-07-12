import asyncio

import kopf
import kubernetes as k8s

from gefyra.configuration import configuration
from gefyra.resources.services import create_stowaway_proxy_service
from gefyra.utils import (
    notify_stowaway_pod,
    exec_command_pod,
    get_deployment_of_pod,
    get_all_probes,
)
from gefyra.resources.configmaps import remove_route, add_route
from gefyra.carrier import (
    patch_pod_with_carrier,
    check_carrier_ready,
    configure_carrier,
    patch_pod_with_original_config,
    configure_carrier_probe,
)

core_v1_api = k8s.client.CoreV1Api()
app_v1_api = k8s.client.AppsV1Api()
events_v1_api = k8s.client.EventsV1Api()

PROXY_RELOAD_COMMAND = [
    "/bin/bash",
    "generate-proxyroutes.sh",
    "/stowaway/proxyroutes/",
]
RSYNC_MKDIR_COMMAND = ["mkdir", "-p"]
RSYNC_RM_COMMAND = ["rm", "-rf"]


def handle_stowaway_proxy_service(
    logger, deployment_stowaway: k8s.client.V1Deployment, port: int
) -> k8s.client.V1Service:
    proxy_service_stowaway = create_stowaway_proxy_service(deployment_stowaway, port)
    try:
        core_v1_api.create_namespaced_service(
            body=proxy_service_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info(f"Stowaway proxy service for port {port} created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is nodeport already allocated
            logger.warn(
                f"Stowaway proxy service for port {port} already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=proxy_service_stowaway.metadata.name,
                body=proxy_service_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info(f"Stowaway proxy service for port {port} patched")
        else:
            raise e
    return proxy_service_stowaway


@kopf.on.create("interceptrequest")
async def interceptrequest_created(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    # destination host and port
    destination_ip = body.get("destinationIP")
    # the target Pod information
    target_pod = body.get("targetPod")
    target_namespace = body.get("targetNamespace")
    target_container = body.get("targetContainer")
    port_mappings = body.get("portMappings")
    #
    #   app:PORT <---> Stowaway:PORT <---> Carrier:PORT
    #
    stowaway_port_mappings = [[None, int(_p.split(":")[1])] for _p in port_mappings]
    carrier_port_mappings = [
        [int(_p.split(":")[0]), None, None] for _p in port_mappings
    ]
    sync_down_dirs = body.get("syncDownDirectories")
    handle_probes = body.get("handleProbes")

    #
    # handle target Pod
    #
    success, pod = patch_pod_with_carrier(
        core_v1_api,
        pod_name=target_pod,
        namespace=target_namespace,
        container_name=target_container,
        ports=[p[0] for p in carrier_port_mappings],
        ireq_object=body,
        handle_probes=handle_probes,
    )
    if not success:
        logger.error(
            "Could not create intercept route because target pod could not be patched with Carrier. "
            "See errors above."
        )
        # instantly remove this InterceptRequest since it's not satisfiable
        k8s.client.CustomObjectsApi().delete_namespaced_custom_object(
            name=body.metadata.name,
            namespace=body.metadata.namespace,
            group="gefyra.dev",
            plural="interceptrequests",
            version="v1",
        )
        logger.error(f"Deleted InterceptRequest {body.metadata.name}")
        return

    stowaway_deployment = get_deployment_of_pod(
        app_v1_api, STOWAWAY_POD, configuration.NAMESPACE
    )

    for port_mapping in stowaway_port_mappings:
        destination_port = port_mapping[1]
        configmap_update, _port = add_route(destination_ip, destination_port)
        core_v1_api.replace_namespaced_config_map(
            name=configmap_update.metadata.name,
            body=configmap_update,
            namespace=configuration.NAMESPACE,
        )
        port_mapping[0] = _port
        # this logger instance logs directly onto the InterceptRequest object instance as an event
        logger.info(
            f"Added intercept route: Stowaway proxy route configmap patched with port {_port}"
        )
        proxy_service = handle_stowaway_proxy_service(
            logger, stowaway_deployment, _port
        )
        for carrier_mapping in carrier_port_mappings:
            if f"{carrier_mapping[0]}:{destination_port}" in port_mappings:
                carrier_mapping[1] = _port
                carrier_mapping[2] = proxy_service.metadata.name

    if STOWAWAY_POD:
        notify_stowaway_pod(core_v1_api, STOWAWAY_POD, configuration)
        exec_command_pod(
            core_v1_api,
            STOWAWAY_POD,
            configuration.NAMESPACE,
            "stowaway",
            PROXY_RELOAD_COMMAND,
        )
        exec_command_pod(
            core_v1_api,
            STOWAWAY_POD,
            configuration.NAMESPACE,
            "stowaway",
            RSYNC_MKDIR_COMMAND + [f"/rsync/{target_pod}/{target_container}"],
        )
        logger.info(f"Created route for InterceptRequest {body.metadata.name}")
    else:
        logger.error(
            "Could not modify Stowaway with new intercept request. Removing this InterceptRequest."
        )
        # instantly remove this InterceptRequest since it's not satisfiable
        k8s.client.CustomObjectsApi().delete_namespaced_custom_object(
            name=body.metadata.name,
            namespace=body.metadata.namespace,
            group="gefyra.dev",
            plural="interceptrequests",
            version="v1",
        )
        return
    logger.info(f"Traffic interception for {body.metadata.name} has been established")

    #
    # configure Carrier
    #
    aw_carrier_ready = asyncio.create_task(
        check_carrier_ready(core_v1_api, target_pod, target_namespace)
    )

    configure_tasks = []
    # handle probes
    if handle_probes:
        probe_ports = set()
        for container in pod.spec.containers:
            if container.name == target_container:
                for probe in get_all_probes(container):
                    if probe.http_get and probe.http_get.port:
                        probe_ports.add(probe.http_get.port)
                break
        for _port in list(probe_ports):
            _task = asyncio.create_task(
                configure_carrier_probe(
                    aw_carrier_ready,
                    core_v1_api,
                    str(_port),
                    target_pod,
                    target_namespace,
                    target_container,
                )
            )
            configure_tasks.append(_task)

    # handle forwarded ports
    for carrier_mapping in carrier_port_mappings:
        _task = asyncio.create_task(
            configure_carrier(
                aw_carrier_ready,
                core_v1_api,
                target_pod,
                target_namespace,
                target_container,
                carrier_mapping[0],
                carrier_mapping[2],
                carrier_mapping[1],
                sync_down_dirs,
            )
        )
        configure_tasks.append(_task)
    # wait for all configurations to happen
    await asyncio.wait(configure_tasks)
    k8s.client.CustomObjectsApi().patch_namespaced_custom_object(
        name=body.metadata.name,
        namespace=body.metadata.namespace,
        group="gefyra.dev",
        plural="interceptrequests",
        version="v1",
        body={"established": True},
    )
    kopf.info(
        body,
        reason="Established",
        message=f"This InterceptRequest route on Pod {target_pod} container "
        f"{target_container}:{port_mappings} has been established",
    )


@kopf.on.delete("interceptrequest")
async def interceptrequest_deleted(body, logger, **kwargs):
    from gefyra.stowaway import STOWAWAY_POD

    name = body.metadata.name
    # is this connection already established
    # destination host and port
    destination_ip = body.get("destinationIP")
    # the target Pod information
    target_pod = body.get("targetPod")
    target_namespace = body.get("targetNamespace")
    target_container = body.get("targetContainer")
    port_mappings = body.get("portMappings")
    destination_ports = [int(_p.split(":")[1]) for _p in port_mappings]

    for destination_port in destination_ports:
        configmap_update, port = remove_route(destination_ip, destination_port)
        core_v1_api.replace_namespaced_config_map(
            name=configmap_update.metadata.name,
            body=configmap_update,
            namespace=configuration.NAMESPACE,
        )

        if STOWAWAY_POD:
            if port is None:
                logger.warning(
                    f"Could not delete service for intercept route {name}: no proxy port found"
                )
            else:
                core_v1_api.delete_namespaced_service(
                    name=f"gefyra-stowaway-proxy-{port}",
                    namespace=configuration.NAMESPACE,
                )
    if STOWAWAY_POD:
        notify_stowaway_pod(core_v1_api, STOWAWAY_POD, configuration)
        exec_command_pod(
            core_v1_api,
            STOWAWAY_POD,
            configuration.NAMESPACE,
            "stowaway",
            PROXY_RELOAD_COMMAND,
        )
        exec_command_pod(
            core_v1_api,
            STOWAWAY_POD,
            configuration.NAMESPACE,
            "stowaway",
            RSYNC_RM_COMMAND + [f"/rsync/{target_pod}/{target_container}"],
        )
        logger.info(f"Removed route for InterceptRequest {name}")
    else:
        logger.error("Could not notify Stowaway about the new intercept request")

    #
    # handle target Pod
    #
    success = patch_pod_with_original_config(
        core_v1_api,
        pod_name=target_pod,
        namespace=target_namespace,
        container_name=target_container,
        ireq_object=body,
    )
    if not success:
        logger.error(
            "Could not restore Pod with original container configuration. See errors above."
        )
    kopf.info(
        body,
        reason="Removed",
        message=f"The InterceptRequest route on Pod {target_pod} container "
        f"{target_container} has been removed",
    )
