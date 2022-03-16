import subprocess


def set_version():
    version = subprocess.run(
        ["poetry", "version", "-s"], capture_output=True, text=True
    ).stdout.rstrip()
    subprocess.run(
        [
            "sed",
            "-i",
            f's/__VERSION__ = "[^"]*"/__VERSION__ = "{version}"/g',
            "gefyra/configuration.py",
        ]
    )
