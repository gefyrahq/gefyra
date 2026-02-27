from multiprocessing import Pool
import os
import subprocess
import pathlib
import random
import string
import tempfile
import time

CLIENTS = {}


def gefyra_client(cmd: str):
    subprocess.run((f"poetry run g {cmd}"), shell=True)


def kubectl(cmd):
    subprocess.run((f"kubectl {cmd}"), shell=True)


def setup():
    cwd = pathlib.Path().resolve()
    subprocess.run(("docker pull quay.io/gefyra/gefyra-tesocket:0.1.0"), shell=True)
    subprocess.run(
        (
            f"k3d cluster create gefyra-loadtesting --kubeconfig-switch-context --kubeconfig-update-default --config {cwd}/tests/k3d_cluster.yaml"
        ),
        shell=True,
    )
    gefyra_client("install --version pr-807 --apply")


def teardown():
    subprocess.run(("k3d cluster rm gefyra-loadtesting"), shell=True)
    print(f"Deleting {len(CLIENTS.keys())} GefyraClient config files")
    for client in CLIENTS.keys():
        delete_client_config(client)
        subprocess.run((f"docker rm -f gefyra-cargo-{client}"), shell=True)


def create_client(name: str):
    gefyra_client(f"clients create --name {name}")


def create_client_config(name: str):
    cl = tempfile.NamedTemporaryFile(delete_on_close=False, delete=False)
    print(f"Creating GefyraClient config file for {name} at {cl.name}")
    gefyra_client(f"clients write {name} --local > {cl.name}")
    CLIENTS[name] = {"config": cl.name}


def delete_client_config(name: str):
    try:
        os.remove(CLIENTS[name]["config"])
        CLIENTS[name]["config"] = ""
    except (OSError, KeyError):
        pass


def activate_client_connection(name: str):
    file = CLIENTS[name]["config"]
    time.sleep(random.randint(0, 5))
    gefyra_client(f"connection connect -f {file} --connection-name {name}")


def deactivate_client_connection(name: str):
    gefyra_client(f"connection rm {name}")


def activate_clients_test(amount: int = 50, processes: int = 10):
    print(
        f"[Test] Creating and activating GefyraClients={amount} with Pool={processes}"
    )

    start_time = time.time()
    for _ in range(0, amount):
        name = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        CLIENTS[name] = {}

    print("[Test] Creating clients")
    with Pool(processes=processes) as pool:
        pool.map(create_client, CLIENTS.keys())

    for client in CLIENTS.keys():
        create_client_config(client)

    print("[Test] Activating clients")
    with Pool(processes=processes) as pool2:
        pool2.map(activate_client_connection, CLIENTS.keys())

    print("[Test] Deactivating clients")
    with Pool(processes=processes) as pool3:
        pool3.map(deactivate_client_connection, CLIENTS.keys())

    print("--- %s seconds ---" % (time.time() - start_time))


def main():
    setup()
    # load testing
    try:
        print("Running tests!")
        activate_clients_test()
    except Exception as e:
        print(e)
    teardown()


if __name__ == "__main__":
    main()
