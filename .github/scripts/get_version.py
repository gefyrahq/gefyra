import os

env_file = os.getenv("GITHUB_ENV")

with open("pyproject.toml") as f:
    for line in f.readlines():
        if "version" in line:
            version = line.split("=")[1]
            version = version.strip()
            version = version.strip('"')

            with open(env_file, "a") as myfile:
                myfile.write("PYAPP_PROJECT_VERSION=" + version)
                myfile.write(f"PYAPP_PROJECT_PATH=./dist/gefyra-{version}.tar.gz")
            exit(0)
