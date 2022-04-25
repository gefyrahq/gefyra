# How to release a new version

1. Run in the root directory `python version.py <major, minor, patch>`
2. Commit changes with message: "chore: bump version to <SemVer>"
3. Assign a g tag to the commit according to the semantic version that was just created (e.g. "0.6.15")
4. Push to GitHub (don't forget to push tags, too)
5. Draft a GitHub release based on the tag, auto-create the changelog
6. Publish the release

The rest should be automated