import dataclasses
import logging
from pathlib import Path
import time
from typing import List, Optional
from gefyra.cluster.utils import is_operator_running
from gefyra.exceptions import ClusterError


from gefyra.misc.install import synthesize_config_as_dict, synthesize_config_as_yaml
from gefyra.misc.uninstall import (
    remove_all_clients,
    remove_gefyra_crds,
    remove_gefyra_namespace,
    remove_gefyra_rbac,
    remove_remainder_bridges,
)
from gefyra.types import GefyraInstallOptions
from .utils import stopwatch

logger = logging.getLogger("gefyra")

LB_PRESETS = {
    "aws": GefyraInstallOptions(
        service_type="LoadBalancer",
        service_annotations={
            "service.beta.kubernetes.io/aws-load-balancer-type": "nlb",
            "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
            "service.beta.kubernetes.io/aws-load-balancer-scheme": "internet-facing",
        },
    ),
    "gke": GefyraInstallOptions(
        service_type="LoadBalancer",
        service_annotations={},
    ),
}

PRESET_TYPE_MAPPING = {"aws": "remote", "eks": "remote"}


@stopwatch
def install(
    component: Optional[List[str]] = None,
    preset: Optional[str] = None,
    apply: bool = False,
    wait: bool = False,
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
    **kwargs,
) -> str:
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    if preset:
        presetoptions = LB_PRESETS.get(preset)  # type: ignore
        if not presetoptions:
            raise RuntimeError(
                f"Preset {preset} not available. Available presets are: {', '.join(LB_PRESETS.keys())}"
            )
        _presetoptions = dataclasses.asdict(presetoptions)  # type: ignore
        _presetoptions.update({k: v for k, v in kwargs.items() if v is not None})
        options = GefyraInstallOptions(**_presetoptions)
    else:
        options = GefyraInstallOptions(
            **{k: v for k, v in kwargs.items() if v is not None}
        )
    logger.debug(f"Using options: {options}")
    output = synthesize_config_as_yaml(options=options, components=component)
    if apply:
        import kubernetes

        try:
            ns = config.K8S_CORE_API.read_namespaced_namespace(name=config.NAMESPACE)
            if ns.status.phase.lower() != "active":
                raise ClusterError(
                    f"Cannot apply Gefyra: namespace {config.NAMESPACE} is in {ns.status.phase} state"
                )
        except:  # noqa
            pass

        objects = synthesize_config_as_dict(options=options, components=component)
        for objs in objects:
            logger.debug(objs)
            try:
                if (
                    objs["kind"] == "Deployment"
                    and objs["metadata"]["name"] == "gefyra-operator"
                ):
                    # if this is the operator and the operator is already running, skip the waiting below
                    # as the Gefyra-Ready event will never be emitted
                    wait = not is_operator_running(config)
                kubernetes.utils.create_from_dict(
                    config.K8S_CORE_API.api_client, data=objs
                )
            except kubernetes.utils.FailToCreateError as e:
                logger.debug(e)
                if e.api_exceptions[0].status not in [409, 422]:
                    logger.error(e)
                    raise ClusterError(f"Could not install Gefyra: {e}")
    if apply and wait:
        logger.debug("Waiting for Gefyra to become ready")
        tic = time.perf_counter()
        from kubernetes.watch import Watch

        w = Watch()

        # block (forever) until Gefyra cluster side is ready
        for event in w.stream(
            config.K8S_CORE_API.list_namespaced_event, namespace=config.NAMESPACE
        ):
            if event["object"].reason in ["Pulling", "Pulled"]:
                logger.info(event["object"].message)
            if event["object"].reason == "Gefyra-Ready":
                toc = time.perf_counter()
                logger.info(f"Gefyra became ready in {toc - tic:0.4f} seconds")
                break
        # busywait for the operator webhook to become ready
        _i = 0
        while _i < 10:
            webhook_deploy = config.K8S_APP_API.read_namespaced_deployment(
                name="gefyra-operator-webhook", namespace=config.NAMESPACE
            )
            if webhook_deploy.status.ready_replicas == 1:
                break
            else:
                logger.debug("Waiting for the operator webhook to become ready")
                time.sleep(1)
                _i += 1
        else:
            raise ClusterError("Operator webhook did not become ready")
    return output


@stopwatch
def uninstall(
    kubeconfig: Optional[Path] = None, kubecontext: Optional[str] = None, **kwargs
):
    from gefyra.configuration import ClientConfiguration

    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    logger.info("Removing all Gefyra bridges")
    try:
        remove_remainder_bridges(config)
    except Exception as e:
        logger.debug(e)
    logger.info("Removing remainder Gefyra clients")
    try:
        remove_all_clients()
    except Exception as e:
        logger.debug(e)
    logger.info("Removing Gefyra namespace")
    try:
        remove_gefyra_namespace(config)
    except Exception as e:
        logger.debug(e)
    logger.info("Removing Gefyra API extensions")
    try:
        remove_gefyra_crds(config)
    except Exception as e:
        logger.debug(e)
    logger.info("Removing Gefyra RBAC resources")
    try:
        remove_gefyra_rbac(config)
    except Exception as e:
        logger.debug(e)
