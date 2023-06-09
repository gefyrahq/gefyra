import dataclasses
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional
from gefyra.configuration import ClientConfiguration

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

logger = logging.getLogger(__name__)

LB_PRESETS = {
    "aws": GefyraInstallOptions(
        service_type="LoadBalancer",
        service_annotations={
            "service.beta.kubernetes.io/aws-load-balancer-type": "external",
            "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-port": "80",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-protocol": "TCP",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-healthy-threshold": (
                "3"
            ),
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-unhealthy-threshold": (
                "3"
            ),
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-timeout": "10",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-interval": "10",
            "service.beta.kubernetes.io/aws-load-balancer-scheme": "internet-facing",
        },
    ),
}


@stopwatch
def install(
    component: List[str],
    preset: Dict,
    apply: bool = False,
    wait: bool = False,
    kubeconfig: Optional[Path] = None,
    kubecontext: Optional[str] = None,
    **kwargs,
) -> str:
    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    if preset:
        presetoptions = LB_PRESETS.get(preset)  # type: ignore
        if not presetoptions:
            raise RuntimeError(f"Preset {preset} not available.")
        presetoptions = dataclasses.asdict(presetoptions)
        presetoptions.update({k: v for k, v in kwargs.items() if v is not None})
        options = GefyraInstallOptions(**presetoptions)
    else:
        options = GefyraInstallOptions(
            **{k: v for k, v in kwargs.items() if v is not None}
        )
    ouput = synthesize_config_as_yaml(options=options, components=component)
    if apply:
        import kubernetes

        objects = synthesize_config_as_dict(options=options, components=component)
        for objs in objects:
            try:
                kubernetes.utils.create_from_dict(
                    config.K8S_CORE_API.api_client, data=objs
                )
            except kubernetes.utils.FailToCreateError as e:
                if e.api_exceptions[0].status != 409:
                    logger.error(e)
    if apply and wait:
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
    return ouput


@stopwatch
def uninstall(
    kubeconfig: Optional[Path] = None, kubecontext: Optional[str] = None, **kwargs
):
    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    logger.info("Removing all Gefyra bridges")
    try:
        remove_remainder_bridges(config)
    except Exception:
        pass
    logger.info("Removing remainder Gefyra clients")
    try:
        remove_all_clients(config)
    except Exception:
        pass
    logger.info("Removing Gefyra namespace")
    try:
        remove_gefyra_namespace(config)
    except Exception:
        pass
    logger.info("Removing Gefyra API extensions")
    try:
        remove_gefyra_crds(config)
    except Exception:
        pass
    logger.info("Removing Gefyra RBAC resources")
    try:
        remove_gefyra_rbac(config)
    except Exception:
        pass
