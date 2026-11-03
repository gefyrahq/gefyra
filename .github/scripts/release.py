import argparse
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILES = (
    "client/pyproject.toml",
    "client/gefyra/configuration.py",
    "operator/pyproject.toml",
)


def run(*command: str, capture_output: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return result.stdout.strip() if capture_output else ""


def read_version(project: str) -> str:
    with (ROOT / project / "pyproject.toml").open("rb") as pyproject:
        return tomllib.load(pyproject)["tool"]["poetry"]["version"]


def release(part: str) -> None:
    if run("git", "status", "--porcelain", capture_output=True):
        raise RuntimeError("The working tree must be clean before creating a release")

    run("python", "version.py", part)

    client_version = read_version("client")
    operator_version = read_version("operator")
    if client_version != operator_version:
        raise RuntimeError(
            f"Version mismatch: client={client_version}, operator={operator_version}"
        )

    tag = client_version
    if run("git", "tag", "--list", tag, capture_output=True):
        raise RuntimeError(f"Tag {tag} already exists")

    run("git", "add", *VERSION_FILES)
    if not run("git", "diff", "--cached", "--name-only", capture_output=True):
        raise RuntimeError("The version bump did not produce any changes")

    run("git", "commit", "-m", f"chore: bump version to {tag}")
    run("git", "tag", tag)
    run("git", "push", "--atomic", "origin", "HEAD", tag)
    run("gh", "release", "create", tag, "--generate-notes", "--verify-tag")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create and publish a Gefyra release")
    parser.add_argument("part", choices=("major", "minor", "patch"))
    args = parser.parse_args()
    release(args.part)
