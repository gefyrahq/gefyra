import os
import subprocess
import sys


def set_client_version(part: str):
    os.chdir("./client")
    subprocess.run(["poetry", "version", part])
    version = subprocess.run(
        ["poetry", "version", "-s"],
        capture_output=True,
        text=True,
    ).stdout.rstrip()
    if sys.platform == "darwin":
        subprocess.run(
            [
                "sed",
                "-i",
                "",
                f's/__VERSION__ = "[^"]*"/__VERSION__ = "{version}"/g',
                "gefyra/configuration.py",
            ]
        )
    else:
        subprocess.run(
            [
                "sed",
                "-i",
                f's/__VERSION__ = "[^"]*"/__VERSION__ = "{version}"/g',
                "gefyra/configuration.py",
            ]
        )


def set_operator_version(part: str):
    os.chdir("./operator")
    subprocess.run(["poetry", "version", part])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["major", "minor", "patch"]:
        print("Only major, minor, patch is allowed as argument")
        exit(1)
    else:
        wd = os.getcwd()
        set_client_version(sys.argv[1])
        os.chdir(wd)
        set_operator_version(sys.argv[1])
