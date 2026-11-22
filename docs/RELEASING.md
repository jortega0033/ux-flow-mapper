# Releasing

A release here is a Git tag on `main` that marks a state where the Python test suite passes and `CHANGELOG.md` is up to date. Nothing is published to a package index: the project has no dependencies and no package.

Only the owner releases. Agents never create tags or releases.

## Steps

1. Check that `main` is green in CI and that every ticket for the release is merged.
2. On a clean checkout of `main`, run `python -m unittest discover -s tests -v`. Record the `Ran N tests` line and the result.
3. Run the server with `python -m flow_mapper --data-dir <temporary directory> --port 0`, open the printed URL, and check that `GET /api/v1/health` returns `{"status": "ok", ...}`. Stop the server.
4. In `CHANGELOG.md`, rename `Unreleased` to the version and date, and add a new empty `Unreleased` section. Commit this on a branch and merge it through a pull request.
5. Tag the merge commit: `git tag -a vX.Y.Z -m "vX.Y.Z"` and `git push origin vX.Y.Z`.
6. Optionally create a GitHub release from the tag with the changelog section as its text.
