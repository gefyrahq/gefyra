import logging
import os
import datetime
from os import path
from time import sleep

import kopf
import kubernetes as k8s
from decouple import config

from resources.deployments import create_stowaway_deployment
from resources.services import create_stowaway_nodeport_service

logger = logging.getLogger("gefyra")
logger.info("Gefyra Operator startup")

try:
    k8s.config.load_incluster_config()
    logger.info("Loaded in-cluster config")
except k8s.config.ConfigException:
    # if the operator is executed locally load the current KUBECONFIG
    k8s.config.load_kube_config()
    logger.info("Loaded KUBECONFIG config")


@kopf.on.startup()
async def check_gefyra_components(logger, **kwargs) -> None:
    """
    Checks all required components of Gefyra in the current version. This handler installs components if they are
    not already available with the matching configuration.
    """
    from gefyra.configuration import configuration
    logger.info(f"Ensuring Gefyra components with the following configuration: {configuration}")

    app = k8s.client.AppsV1Api()
    core_v1_api = k8s.client.CoreV1Api()

    # handle Stowaway deployment
    deployment_stowaway = create_stowaway_deployment()

    try:
        app.create_namespaced_deployment(
            body=deployment_stowaway, namespace=configuration.NAMESPACE)
        logger.info(f"Stowaway deployment created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway deployment already exist
            logger.warn(f"Stowaway deployment already available, now patching it with current configuration")
            app.patch_namespaced_deployment(
                name=deployment_stowaway.metadata.name, body=deployment_stowaway,
                namespace=configuration.NAMESPACE
            )
            logger.info(f"Stowaway deployment patched")
        else:
            raise e

    # handle Stowaway nodeport service
    nodeport_service_stowaway = create_stowaway_nodeport_service(deployment_stowaway)
    try:
        core_v1_api.create_namespaced_service(
            body=nodeport_service_stowaway, namespace=configuration.NAMESPACE)
        logger.info(f"Stowaway nodeport service created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is nodeport already allocated
            logger.warn(f"Stowaway nodeport service already available, now patching it with current configuration")
            core_v1_api.patch_namespaced_service(
                name=nodeport_service_stowaway.metadata.name, body=nodeport_service_stowaway,
                namespace=configuration.NAMESPACE
            )
            logger.info(f"Stowaway nodeport service patched")
        else:
            raise e



