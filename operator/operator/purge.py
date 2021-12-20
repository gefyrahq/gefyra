import asyncio
import logging
from operator.configuration import configuration
from operator.resources.configmaps import create_stowaway_proxyroute_configmap
from operator.resources.crds import create_interceptrequest_definition
from operator.resources.deployments import create_stowaway_deployment
from operator.resources.secrets import create_wireguard_connection_secret

import kubernetes as k8s

logger = logging.getLogger("gefyra")

app = k8s.client.AppsV1Api()
core_v1_api = k8s.client.CoreV1Api()
rbac_api = k8s.client.RbacAuthorizationV1Api()
extension_api = k8s.client.ApiextensionsV1Api()
custom_api = k8s.client.CustomObjectsApi()


def purge_operator():
    """
    Purge Operator and all related components from the cluster; let Operate handle deletion of InterceptRequests
    :return:
    """
    deployment_stowaway = create_stowaway_deployment()
    configmap_proxyroute = create_stowaway_proxyroute_configmap()
    ireqs = create_interceptrequest_definition()
    peer_secret = create_wireguard_connection_secret({})

    remove_interceptrequest_remainder(ireqs)
    remove_crd(ireqs)
    remove_stowaway_services()
    remove_stowaway_deployment(deployment_stowaway)
    remove_stowaway_configmap(configmap_proxyroute)
    remove_stowaway_peer_secret(peer_secret)
    #
    # Remove components created by Gefyra client
    #
    try:
        rbac_api.delete_cluster_role_binding(name="gefyra-operator-rolebinding")
    except k8s.client.exceptions.ApiException:
        pass
    try:
        core_v1_api.delete_namespaced_service_account(name="gefyra-operator", namespace=configuration.NAMESPACE)
    except k8s.client.exceptions.ApiException:
        pass
    try:
        rbac_api.delete_cluster_role(name="gefyra-operator-role")
    except k8s.client.exceptions.ApiException:
        pass
    try:
        core_v1_api.delete_namespace(name=configuration.NAMESPACE)
    except k8s.client.exceptions.ApiException:
        pass


def remove_interceptrequest_remainder(ireqs: k8s.client.V1CustomResourceDefinition):
    from operator.handler import interceptrequest_deleted

    try:
        ireq_list = custom_api.list_namespaced_custom_object(
            namespace=configuration.NAMESPACE,
            group=ireqs.spec.group,
            version=ireqs.spec.versions[0].name,
            plural=ireqs.spec.names.plural,
        )
        if ireq_list.get("items"):
            logger.info("Removing InterceptRequests remainder")
            # if there are running intercept requests clean them up
            delete_jobs = []
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            for ireq in ireq_list.get("items"):
                delete_jobs.append(loop.create_task(interceptrequest_deleted(ireq, logger)))
                # this does not call Operator as it is already shutting down
                custom_api.delete_namespaced_custom_object(
                    group=ireqs.spec.group,
                    version=ireqs.spec.versions[0].name,
                    namespace=ireq["metadata"]["namespace"],
                    plural=ireqs.spec.names.plural,
                    name=ireq["metadata"]["name"],
                )
            loop.run_until_complete(asyncio.wait(delete_jobs, return_when=asyncio.ALL_COMPLETED))
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing remainder InterceptRequests: " + str(e))


def remove_crd(ireqs: k8s.client.V1CustomResourceDefinition):
    logger.info("Removing CRD InterceptRequests")
    try:
        extension_api.delete_custom_resource_definition(name=ireqs.metadata.name)
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing CRD InterceptRequests: " + str(e))


def remove_stowaway_services():
    logger.info("Removing Stowaway services")
    try:
        svc_list = core_v1_api.list_namespaced_service(namespace=configuration.NAMESPACE)
        for svc in svc_list.items:
            core_v1_api.delete_namespaced_service(name=svc.metadata.name, namespace=configuration.NAMESPACE)
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing Stowaway services: " + str(e))


def remove_stowaway_deployment(deployment_stowaway: k8s.client.V1Deployment):
    logger.info("Removing Stowaway deployment")
    try:
        app.delete_namespaced_deployment(
            name=deployment_stowaway.metadata.name,
            namespace=deployment_stowaway.metadata.namespace,
        )
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error Stowaway deployment: " + str(e))


def remove_stowaway_configmap(configmap_proxyroute: k8s.client.V1ConfigMap):
    logger.info("Removing Stowaway proxyroute configmap")
    try:
        core_v1_api.delete_namespaced_config_map(
            name=configmap_proxyroute.metadata.name,
            namespace=configmap_proxyroute.metadata.namespace,
        )
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error Stowaway proxyroute configmap: " + str(e))


def remove_stowaway_peer_secret(peer_secret: k8s.client.V1Secret):
    logger.info("Removing Stowaway peer connection secret")
    try:
        core_v1_api.delete_namespaced_secret(name=peer_secret.metadata.name, namespace=peer_secret.metadata.namespace)
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error Stowaway peer connection secret: " + str(e))


if __name__ == "__main__":
    try:
        k8s.config.load_incluster_config()
        logger.info("Loaded in-cluster config")
    except k8s.config.ConfigException:
        # if the operator is executed locally load the current KUBECONFIG
        k8s.config.load_kube_config()
        logger.info("Loaded KUBECONFIG config")
    purge_operator()
