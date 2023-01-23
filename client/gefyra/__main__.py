#!/usr/bin/env python3
import argparse
import logging
import traceback

from gefyra.api import get_containers_and_print, get_bridges_and_print, GefyraStatus
from gefyra.configuration import ClientConfiguration
from gefyra.local.utils import (
    PortMappingParser,
    IpPortMappingParser,
    get_connection_from_kubeconfig,
)
from gefyra.local.minikube import detect_minikube_config
from gefyra.local.telemetry import CliTelemetry

logger = logging.getLogger("gefyra")
parser = argparse.ArgumentParser(
    prog="gefyra",
    description="The Gefyra client. For more help please visit: https://gefyra.dev/reference/cli/",
)
action = parser.add_subparsers(dest="action", help="the action to be performed")
parser.add_argument("-d", "--debug", action="store_true", help="add debug output")


up_parser = action.add_parser("up")
up_parser.add_argument(
    "-e",
    "--endpoint",
    dest="cargo_endpoint",
    help="the Wireguard endpoint in the form <IP>:<Port> for Gefyra to connect to",
    required=False,
)
up_parser.add_argument(
    "-H",
    "--host",
    dest="cargo_endpoint_host",
    help="Hostname or IP of a K8s node for Gefyra to connect to."
    "Gefyra tries to extract this from the current kubeconfig and context.",
    required=False,
)
up_parser.add_argument(
    "-p",
    "--port",
    dest="cargo_endpoint_port",
    help="Open UDP port of the K8S node to connect to. Default to 31820.",
    required=False,
    default="31820",
)
up_parser.add_argument(
    "-M",
    "--minikube",
    help="Let Gefyra automatically find out the connection parameters for a "
    "local Minikube cluster for the given profile (default 'minikube').",
    required=False,
    nargs="?",
    const="minikube",
)
up_parser.add_argument(
    "-o",
    "--operator",
    dest="operator_image_url",
    help="Registry url for the operator image.",
    required=False,
)
up_parser.add_argument(
    "-s",
    "--stowaway",
    dest="stowaway_image_url",
    help="Registry url for the stowaway image.",
    required=False,
)
up_parser.add_argument(
    "-c",
    "--carrier",
    dest="carrier_image_url",
    help="Registry url for the carrier image.",
    required=False,
)
up_parser.add_argument(
    "-a",
    "--cargo",
    dest="cargo_image_url",
    help="Registry url for the cargo image.",
    required=False,
)
up_parser.add_argument(
    "-r",
    "--registry",
    dest="registry_url",
    help="Base url for registry to pull images from.",
    required=False,
)
up_parser.add_argument(
    "--wireguard-mtu",
    dest="wireguard_mtu",
    help="The MTU value for the local Wireguard endpoint (default: 1340).",
)
up_parser.add_argument(
    "--kubeconfig",
    dest="kube_config_file",
    required=False,
    help="The path to kubeconfig file",
)
up_parser.add_argument(
    "--context",
    dest="kube_context",
    required=False,
    help="The context name from kubeconfig",
)


run_parser = action.add_parser("run")
run_parser.add_argument(
    "-i", "--image", help="The docker image to run in Gefyra", required=True
)
run_parser.add_argument(
    "-N", "--name", help="The name of the container running in Gefyra", required=True
)
run_parser.add_argument(
    "-c",
    "--command",
    help="The command for this container to in Gefyra",
    nargs="+",
    required=False,
)
run_parser.add_argument(
    "-n",
    "--namespace",
    help="The namespace for this container to run in",
)
run_parser.add_argument(
    "--env",
    action="append",
    help="Set or override environment variables in the form ENV=value, allowed multiple times",
    required=False,
)
run_parser.add_argument(
    "-v",
    "--volume",
    action="append",
    help="Bind mount a volume into the container in notation src:dest, allowed multiple times",
    required=False,
)
run_parser.add_argument(
    "--env-from",
    help="Copy the environment from the container in the notation 'Pod/Container'",
    required=False,
)
run_parser.add_argument(
    "-p",
    "--expose",
    help="Add port mapping in form of <container_port>:<host_port>",
    required=False,
    action=IpPortMappingParser,
)
run_parser.add_argument(
    "--rm",
    help="Automatically remove the container when it exits",
    dest="auto_remove",
    action="store_true",
    default=False,
    required=False,
)
run_parser.add_argument(
    "-d",
    "--detach",
    help="Run container in background and print container ID",
    action="store_true",
    default=False,
    required=False,
)
bridge_parser = action.add_parser("bridge")
bridge_parser.add_argument(
    "-N", "--name", help="The name of the container running in Gefyra", required=True
)
bridge_parser.add_argument(
    "-p",
    "--port",
    help="Add port mapping in form of <container_port>:<host_port>",
    required=True,
    action=PortMappingParser,
)
bridge_parser.add_argument(
    "-n",
    "--namespace",
    help="The namespace for this container to run in",
    default="default",
)
bridge_parser.add_argument(
    "-P",
    "--no-probe-handling",
    action="store_true",
    help="Make Carrier to not handle probes during switch operation",
    default=False,
)
bridge_parser.add_argument(
    "--target",
    help="Intercept the container given in the notation 'resource/name/container'. "
    "Resource can be one of 'deployment', 'statefulset' or 'pod'. "
    "E.g.: --target deployment/hello-nginx/nginx",
    required=False,
)

unbridge_parser = action.add_parser("unbridge")
unbridge_parser.add_argument("-N", "--name", help="The name of the bridge")
unbridge_parser.add_argument(
    "-w",
    "--wait",
    help="Block until deletion is complete",
    action="store_true",
    default=False,
    required=False,
)
unbridge_parser.add_argument(
    "-A", "--all", help="Removes all active bridges", action="store_true"
)
list_parser = action.add_parser("list")
list_parser.add_argument(
    "--containers", help="List all containers running in Gefyra", action="store_true"
)
list_parser.add_argument(
    "--bridges", help="List all active bridges in Gefyra", action="store_true"
)
down_parser = action.add_parser("down")
check_parser = action.add_parser("check")
status_parser = action.add_parser("status")
version_parser = action.add_parser("version")

version_parser.add_argument(
    "-n",
    "--no-check",
    help="Do not check whether there is a new version",
    action="store_true",
    default=False,
)

telemetry_parser = action.add_parser("telemetry")
telemetry_parser.add_argument("--off", help="Turn off telemetry", action="store_true")
telemetry_parser.add_argument("--on", help="Turn on telemetry", action="store_true")

try:
    telemetry = CliTelemetry()
except Exception:  # pragma: no cover
    telemetry = False


def version(config, check: bool):
    import requests

    logger.info(f"Gefyra client version: {config.__VERSION__}")
    if check:
        release = requests.get(
            "https://api.github.com/repos/gefyrahq/gefyra/releases/latest"
        )
        if release.status_code == 403:  # pragma: no cover
            logger.info("Versions cannot be compared, as API rate limit was exceeded")
            return None
        latest_release_version = release.json()["tag_name"].replace("-", ".")
        if config.__VERSION__ != latest_release_version:  # pragma: no cover
            logger.info(
                f"You are using gefyra version {config.__VERSION__}; however, version {latest_release_version} is "
                f"available."
            )
    return True


def telemetry_command(on, off):
    if not telemetry:
        logger.info("Telemetry in not working on your machine. No action taken.")
        return
    if off and not on:
        telemetry.off()
    elif on and not off:
        telemetry.on()
    else:
        logger.info("Invalid flags. Please use either --off or --on.")


def get_client_configuration(args) -> ClientConfiguration:
    configuration_params = {}

    if args.action == "up":
        if args.cargo_endpoint:
            logger.warning(
                "`--endpoint`/`-e` has been removed. Please consider `--host` and `--port` instead."
            )
            exit(1)
        if args.minikube and bool(args.cargo_endpoint_host):
            raise RuntimeError("You cannot use --host together with --minikube.")

        if args.minikube:
            configuration_params.update(detect_minikube_config(args.minikube))
        else:
            if not args.cargo_endpoint_host:
                # #138: Read in the endpoint from kubeconfig
                endpoint = get_connection_from_kubeconfig(args.kube_config_file)
                if endpoint:
                    logger.info(f"Setting host and port from kubeconfig {endpoint}")
                    configuration_params["cargo_endpoint_host"] = endpoint.split(":")[0]
                    configuration_params["cargo_endpoint_port"] = endpoint.split(":")[1]
                else:
                    logger.info(
                        "There was no --host argument provided. Connecting to a local Kubernetes node."
                    )
        for argument in vars(args):
            if argument not in [
                "action",
                "debug",
                "minikube",
                "cargo_endpoint",
            ]:
                # don't overwrite an option which has been determined already
                if argument not in configuration_params:
                    logger.debug(
                        f"Setting remainder option: {argument}:{getattr(args, argument)}"
                    )
                    configuration_params[argument] = getattr(args, argument)

    configuration = ClientConfiguration(**configuration_params)
    logger.debug("ClientConfiguration: " + str(vars(configuration)))

    return configuration


def print_status(status: GefyraStatus):
    import json
    import dataclasses

    class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            # we only accept dataclasses here
            return dataclasses.asdict(o)

    print(json.dumps(status, cls=EnhancedJSONEncoder, indent=2))


def cli_up(configuration):
    from gefyra.api import up

    success = up(config=configuration)
    if not success:
        raise RuntimeError("Failed to start Gefyra")


def main():
    try:
        from gefyra import configuration as configuration_package
        from gefyra.api import bridge, down, run, unbridge, unbridge_all, status
        from gefyra.local.check import probe_kubernetes, probe_docker

        args = parser.parse_args()
        if args.debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        logger.addHandler(configuration_package.console)

        if args.action == "version":
            check = not args.no_check
            version(configuration_package, check)
            exit(0)

        configuration = get_client_configuration(args)

        if args.action == "up":
            cli_up(configuration=configuration)
        elif args.action == "run":
            run(
                image=args.image,
                name=args.name,
                command=" ".join(args.command) if args.command else None,
                namespace=args.namespace,
                env_from=args.env_from,
                env=args.env,
                ports=args.expose,
                auto_remove=args.auto_remove,
                volumes=args.volume,
                config=configuration,
                detach=args.detach,
            )
        elif args.action == "bridge":
            bridge(
                args.name,
                args.port,
                namespace=args.namespace,
                handle_probes=not args.no_probe_handling,
                config=configuration,
                target=args.target,
            )
        elif args.action == "unbridge":
            if args.name:
                unbridge(args.name, wait=args.wait, config=configuration)
            elif args.all:
                unbridge_all(wait=args.wait, config=configuration)
            else:
                logger.warning(
                    "Unbridge failed. Please use command with either -N or -A flag."
                )
                exit(1)
        elif args.action == "list":
            if args.containers:
                get_containers_and_print(config=configuration)
            elif args.bridges:
                get_bridges_and_print(config=configuration)
            else:
                get_containers_and_print(config=configuration)
                get_bridges_and_print(config=configuration)
        elif args.action == "down":
            down(config=configuration)
        elif args.action == "status":
            _status = status(config=configuration)
            print_status(_status)
        elif args.action == "check":
            probe_docker()
            probe_kubernetes(config=configuration)
        elif args.action == "telemetry":
            telemetry_command(on=args.on, off=args.off)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        logger.warning("Program interrupted by user. Exiting...")
        exit(1)
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        logger.fatal(f"There was an error running Gefyra: {e}")
        exit(1)
    exit(0)


if __name__ == "__main__":  # noqa
    main()
