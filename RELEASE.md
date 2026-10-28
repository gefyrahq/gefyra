# How to release a new version

## Automated release

1. Create a `RELEASE_TOKEN` repository secret containing a fine-grained personal
access token with read and write access to repository contents. The token is
required so that publishing the release triggers the package, binary, and
notification workflows.
2. Run the **Create release** workflow from the default branch and select the
semantic version part to increment.

The workflow also runs every Monday at 08:00 UTC, using a patch version bump.
The workflow does nothing when there are no commits after the latest published
release. It aborts when an unreleased commit subject starts with `feat:` so that
the pending feature can be reviewed before choosing a release version.
Otherwise it runs `.github/scripts/release.py`, which performs the steps below.

## Manual release

1. Run in the root directory `python version.py <major, minor, patch>`
2. Commit changes with message: "chore: bump version to <SemVer>"
3. Assign a git tag to the commit according to the semantic version that was just created (e.g. "0.6.15")
4. Push to GitHub (don't forget to push tags, too)
5. Draft a GitHub release based on the tag, auto-create the changelog
6. Publish the release

The rest should be automated
