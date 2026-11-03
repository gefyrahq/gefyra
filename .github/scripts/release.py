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


def prepare(part: str) -> None:
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
    branch = f"automated-release/{tag}"
    run("git", "push", "origin", f"HEAD:refs/heads/{branch}")
    pull_request = run(
        "gh",
        "pr",
        "create",
        "--base",
        "main",
        "--head",
        branch,
        "--title",
        f"chore: bump version to {tag}",
        "--body",
        f"Automated version bump for release {tag}.",
        capture_output=True,
    )
    run("gh", "pr", "merge", "--auto", "--merge", pull_request)


def publish() -> None:
    client_version = read_version("client")
    operator_version = read_version("operator")
    if client_version != operator_version:
        raise RuntimeError(
            f"Version mismatch: client={client_version}, operator={operator_version}"
        )

    tag = client_version
    if run("git", "tag", "--list", tag, capture_output=True):
        raise RuntimeError(f"Tag {tag} already exists")

    run("git", "tag", tag)
    run("git", "push", "origin", tag)
    run("gh", "release", "create", tag, "--generate-notes", "--verify-tag")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare or publish a Gefyra release")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("part", choices=("major", "minor", "patch"))
    subparsers.add_parser("publish")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.part)
    else:
        publish()
