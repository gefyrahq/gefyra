from typing import Optional
import click

import logging
from alive_progress import alive_bar
from click import pass_context
from gefyra import api
from gefyra.cli.utils import standard_error_handler
from gefyra.configuration import ClientConfiguration, get_gefyra_config_location
from gefyra.types import StatusSummary

logger = logging.getLogger("gefyra")


def _check_and_install(
    config: ClientConfiguration, connection_name: str = "", bar=None
) -> bool:
    status = api.status(connection_name=connection_name)

    if status.summary == StatusSummary.UP:
        bar()
        bar.title = "Gefyra is already installed"
        return True
    elif status.summary == StatusSummary.INCOMPLETE:
        logger.warning("Gefyra is not installed, but operating properly. Aborting.")
        return False
    else:  # status.summary == StatusSummary.DOWN:
        api.install(
            kubeconfig=config.KUBE_CONFIG_FILE,
            kubecontext=config.KUBE_CONTEXT,
            apply=True,
            wait=True,
        )
        return True


@click.command("up", help="Install Gefyra on a cluster and directly connect to it")
@click.option(
    "--minikube",
    help="Connect Gefyra to a Minikube cluster (accepts minikube profile name, default is 'minikube'))",
    type=str,
    is_flag=False,
    flag_value="minikube",  # if --minikube is used as flag, we default to profile 'minikube'
    required=False,
)
@pass_context
@standard_error_handler
def cluster_up(ctx, minikube: Optional[str] = None):
    from gefyra.exceptions import GefyraClientAlreadyExists, ClientConfigurationError
    from time import sleep
    import os

    client_id = "default"
    connection_name = "default"
    kubeconfig = ctx.obj["kubeconfig"]
    kubecontext = ctx.obj["context"]

    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)
    with alive_bar(4, title="Installing Gefyra to the cluster") as bar:
        # run a default install
        install_success = _check_and_install(
            config=config, connection_name=connection_name, bar=bar
        )
        if install_success:
            bar()
            bar.title = f"Creating a Gefyra client: {client_id}"
            # create a client
            try:
                client = api.add_clients(
                    client_id,
                    kubeconfig=config.KUBE_CONFIG_FILE,
                    kubecontext=config.KUBE_CONTEXT,
                )[0]
            except GefyraClientAlreadyExists:
                client = api.get_client(
                    client_id,
                    kubeconfig=config.KUBE_CONFIG_FILE,
                    kubecontext=config.KUBE_CONTEXT,
                )
        else:
            client = api.get_client(
                client_id,
                kubeconfig=config.KUBE_CONFIG_FILE,
                kubecontext=config.KUBE_CONTEXT,
            )
            bar()
        # write config with specific connection data (for minikube)
        host = config.CARGO_ENDPOINT.split(":")[0]
        bar()
        bar.title = "Waiting for the Gefyra client to enter 'waiting' state"
        # busy wait for the client to enter the waiting state
        _i = 0
        while _i < 5:
            try:
                json_str = api.write_client_file(
                    client_id=client.client_id,
                    kubeconfig=config.KUBE_CONFIG_FILE,
                    kubecontext=config.KUBE_CONTEXT,
                    host=host,
                )
                break
            except ClientConfigurationError as e:
                logger.warning(e)
                sleep(1)
                _i += 1

        else:
            raise ClientConfigurationError(
                "Could not set up the client '{client_id}'. This is most probably a problem of Gefyra operator."
            )

        # create a temporary file with the client config
        loc = os.path.join(
            get_gefyra_config_location(),
            f"{connection_name}_client.json",
        )
        fh = open(loc, "w+")
        fh.write(json_str)
        fh.seek(0)
        bar()
        bar.title = (
            f"Connecting local container network '{config.NETWORK_NAME}' to the cluster"
        )
        logger.debug(f"Minikube profile {minikube}")
        api.connect(connection_name, client_config=fh, minikube_profile=minikube)
        fh.close()
        os.remove(loc)
        bar()
        bar.title = "Gefyra is ready"


@click.command("down", help="Remove Gefyra locally and on the cluster")
@pass_context
@standard_error_handler
def cluster_down(ctx):
    from gefyra import api

    connection_name = "default"
    kubeconfig = ctx.obj["kubeconfig"]
    kubecontext = ctx.obj["context"]
    config = ClientConfiguration(kube_config_file=kubeconfig, kube_context=kubecontext)

    with alive_bar(2, title="Removing Gefyra from the cluster") as bar:
        api.uninstall(
            kubeconfig=config.KUBE_CONFIG_FILE,
            kubecontext=config.KUBE_CONTEXT,
        )
        bar()
        bar.title = "Removing Gefyra from the local machine"
        api.remove_connection(connection_name=connection_name)
        bar()
        bar.title = "Gefyra successfully removed"
