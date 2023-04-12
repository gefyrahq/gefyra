import kubernetes as k8s

from gefyra.configuration import OperatorConfiguration
from gefyra.connection.stowaway.resources import (
    create_stowaway_proxyroute_configmap,
    create_stowaway_configmap,
    create_stowaway_statefulset,
    create_stowaway_serviceaccount,
    create_stowaway_nodeport_service,
    create_stowaway_rsync_service,
)

core_v1_api = k8s.client.CoreV1Api()
app = k8s.client.AppsV1Api()


def handle_serviceaccount(logger, configuration: OperatorConfiguration):
    serviceaccount = create_stowaway_serviceaccount()
    try:
        core_v1_api.create_namespaced_service_account(
            body=serviceaccount, namespace=configuration.NAMESPACE
        )
        logger.info("Gefyra Stowaway Serviceaccount created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            pass
        else:
            raise e


def check_serviceaccount(logger, configuration: OperatorConfiguration):
    serviceaccount = create_stowaway_serviceaccount()
    try:
        core_v1_api.read_namespaced_service_account(
            serviceaccount.metadata.name, serviceaccount.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning("Gefyra Stowaway Serviceaccount does not exist")
            return False
        else:
            raise e


def handle_proxyroute_configmap(
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1ConfigMap:
    # Todo recover from restart; read in all <InterceptRequests>
    configmap_proxyroute = create_stowaway_proxyroute_configmap()

    try:
        core_v1_api.create_namespaced_config_map(
            body=configmap_proxyroute, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway proxy route configmap created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway proxy route configmap exist
            logger.warning(
                "Stowaway proxy route configmap already available, now patching it with current configuration"
            )
            core_v1_api.replace_namespaced_config_map(
                name=configmap_proxyroute.metadata.name,
                body=configmap_proxyroute,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway proxy route configmap patched")
        else:
            raise e
    return configmap_proxyroute


def check_proxyroute_configmap(
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1ConfigMap:
    configmap_proxyroute = create_stowaway_proxyroute_configmap()
    try:
        core_v1_api.read_namespaced_config_map(
            configmap_proxyroute.metadata.name, configmap_proxyroute.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning("Stowaway proxy route configmap does not exist")
            return False
        else:
            raise e


def handle_config_configmap(
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1ConfigMap:
    configmap = create_stowaway_configmap()

    try:
        core_v1_api.create_namespaced_config_map(
            body=configmap, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway config configmap created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            logger.warning(
                "Stowaway config configmap already available, now patching it with current configuration"
            )
            core_v1_api.replace_namespaced_config_map(
                name=configmap.metadata.name,
                body=configmap,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway config configmap patched")
        else:
            raise e
    return configmap


def check_config_configmap(
    logger, configuration: OperatorConfiguration
) -> k8s.client.V1ConfigMap:
    configmap = create_stowaway_configmap()
    try:
        core_v1_api.read_namespaced_config_map(
            configmap.metadata.name, configmap.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning("Stowaway config configmap does not exist")
            return False
        else:
            raise e


def handle_stowaway_statefulset(
    logger, configuration: OperatorConfiguration, labels: dict[str, str]
) -> k8s.client.V1StatefulSet:
    stowaway_sts = create_stowaway_statefulset(labels, configuration)

    try:
        app.create_namespaced_stateful_set(
            body=stowaway_sts, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway deployment created")
    except k8s.client.exceptions.ApiException as e:
        if e.status == 409:
            # the Stowaway deployment already exist
            logger.warning(
                "Stowaway deployment already available, now patching it with current configuration"
            )
            app.patch_namespaced_stateful_set(
                name=stowaway_sts.metadata.name,
                body=stowaway_sts,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway deployment patched")
        else:
            raise e
    return stowaway_sts


def check_stowaway_statefulset(
    logger, configuration: OperatorConfiguration, labels: dict[str, str]
) -> bool:
    stowaway_sts = create_stowaway_statefulset(labels, configuration)
    try:
        app.read_namespaced_stateful_set(
            stowaway_sts.metadata.name, stowaway_sts.metadata.namespace
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning("Stowaway deployment does not exist")
            return False
        else:
            raise e


def handle_stowaway_nodeport_service(
    logger,
    configuration: OperatorConfiguration,
    stowaway_sts: k8s.client.V1StatefulSet,
):
    nodeport_service_stowaway = create_stowaway_nodeport_service(stowaway_sts)
    try:
        core_v1_api.create_namespaced_service(
            body=nodeport_service_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway nodeport service created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is nodeport already allocated
            logger.warning(
                "Stowaway nodeport service already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=nodeport_service_stowaway.metadata.name,
                body=nodeport_service_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway nodeport service patched")
        else:
            raise e


def check_stowaway_nodeport_service(
    logger,
    configuration: OperatorConfiguration,
    stowaway_sts: k8s.client.V1StatefulSet,
):
    nodeport_service_stowaway = create_stowaway_nodeport_service(stowaway_sts)
    try:
        core_v1_api.read_namespaced_service(
            nodeport_service_stowaway.metadata.name,
            nodeport_service_stowaway.metadata.namespace,
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning("Stowaway nodeport service does not exist")
            return False
        else:
            raise e


def handle_stowaway_rsync_service(
    logger,
    configuration: OperatorConfiguration,
    stowaway_sts: k8s.client.V1StatefulSet,
):
    rsync_service_stowaway = create_stowaway_rsync_service(stowaway_sts)
    try:
        core_v1_api.create_namespaced_service(
            body=rsync_service_stowaway, namespace=configuration.NAMESPACE
        )
        logger.info("Stowaway rsync service created")
    except k8s.client.exceptions.ApiException as e:
        if e.status in [409, 422]:
            # the Stowaway service already exist
            # status == 422 is rsync already allocated
            logger.warning(
                "Stowaway rsync service already available, now patching it with current configuration"
            )
            core_v1_api.patch_namespaced_service(
                name=rsync_service_stowaway.metadata.name,
                body=rsync_service_stowaway,
                namespace=configuration.NAMESPACE,
            )
            logger.info("Stowaway rsync service patched")
        else:
            raise e


def check_stowaway_rsync_service(
    logger,
    configuration: OperatorConfiguration,
    stowaway_sts: k8s.client.V1StatefulSet,
):
    rsync_service_stowaway = create_stowaway_rsync_service(stowaway_sts)
    try:
        core_v1_api.read_namespaced_service(
            rsync_service_stowaway.metadata.name,
            rsync_service_stowaway.metadata.namespace,
        )
        return True
    except k8s.client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning("Stowaway rsync service does not exist")
            return False
        else:
            raise e


def remove_stowaway_services(logger, configuration: OperatorConfiguration):
    logger.info("Removing Stowaway services")
    try:
        svc_list = core_v1_api.list_namespaced_service(
            namespace=configuration.NAMESPACE, label_selector="gefyra.dev/app=stowaway"
        )
        for svc in svc_list.items:
            core_v1_api.delete_namespaced_service(
                name=svc.metadata.name, namespace=configuration.NAMESPACE
            )
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing Stowaway services: " + str(e))


def remove_stowaway_statefulset(logger, stowaway_sts: k8s.client.V1StatefulSet):
    logger.info("Removing Stowaway StatefulSet")
    try:
        app.delete_namespaced_stateful_set(
            name=stowaway_sts.metadata.name,
            namespace=stowaway_sts.metadata.namespace,
        )
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error Stowaway StatefulSet: " + str(e))


def remove_stowaway_configmaps(logger, configuration: OperatorConfiguration):
    logger.info("Removing Stowaway configmaps")
    try:
        configmaps = core_v1_api.list_namespaced_config_map(
            namespace=configuration.NAMESPACE, label_selector="gefyra.dev/app=stowaway"
        )
        for cm in configmaps.items:
            core_v1_api.delete_namespaced_config_map(
                name=cm.metadata.name,
                namespace=cm.metadata.namespace,
            )
    except k8s.client.exceptions.ApiException as e:
        logger.error("Error removing Stowaway configmap: " + str(e))
