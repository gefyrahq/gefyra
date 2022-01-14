from gefyra.configuration import default_configuration
from gefyra.local.bridge import deploy_app_container

from .utils import stopwatch


@stopwatch
def bridge(config=default_configuration) -> bool:
    # todo check preconditions
    pass


@stopwatch
def run(
    image: str,
    name: str = None,
    command: str = None,
    volumes: dict = None,
    ports: dict = None,
    detach: bool = False,
    auto_remove: bool = True,
    config=default_configuration,
) -> bool:
    deploy_app_container(config, image, name, command, volumes, ports, auto_remove)
    if detach:
        return True
    else:
        print("Now printing out logs")
        # for logline in container.logs(stream=True):
        #     print(logline)


if __name__ == "__main__":
    print("now running 'run'")
    run(
        image="pyserver",
        name="mypyserver",
    )
