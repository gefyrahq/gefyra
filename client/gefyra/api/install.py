import dataclasses

from gefyra.misc.install import synthesize_config_as_yaml
from gefyra.types import GefyraInstallOptions


LB_PRESETS = {
    "aws": GefyraInstallOptions(
        service_type="LoadBalancer",
        service_annotations={
            "service.beta.kubernetes.io/aws-load-balancer-type": "external",
            "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-port": "80",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-protocol": "TCP",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-healthy-threshold": "3",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-unhealthy-threshold": "3",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-timeout": "10",
            "service.beta.kubernetes.io/aws-load-balancer-healthcheck-interval": "10",
            "service.beta.kubernetes.io/aws-load-balancer-scheme": "internet-facing",
        },
    ),
}


def install(component, preset, **kwargs):
    if preset:
        presetoptions = LB_PRESETS.get(preset)
        if not presetoptions:
            raise RuntimeError(f"Preset {preset} not available. ")
        presetoptions = dataclasses.asdict(presetoptions)
        presetoptions.update({k: v for k, v in kwargs.items() if v is not None})
        options = GefyraInstallOptions(**presetoptions)
    else:
        options = GefyraInstallOptions(
            **{k: v for k, v in kwargs.items() if v is not None}
        )
    synthesize_config_as_yaml(options=options, components=component)
