import os

env_file = os.getenv("GITHUB_ENV")

with open("pyproject.toml") as f:
    for line in f.readlines():
        if "version" in line:
            version = line.split("=")[1]
            version = version.strip()
            version = version.strip('"')

            with open(env_file, "a") as myfile:
                myfile.write("APP_VERSION=" + version)
            exit(0)
