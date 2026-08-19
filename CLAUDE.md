# Duskfade Save Tools — working agreement

This is an open-source repo on GitHub (`Zyrumi/duskfade-save-tools`) that other people may contribute to.

- **Before starting any work in this folder**, run `git fetch` and check whether `origin/main` is ahead of local `main`. If it is, pull first — never build on top of stale local state, since someone else may have pushed a fix or contribution since the last session here.
- **Commit and push automatically** as work is completed — no need to ask before each push, that's pre-authorized for this repo.
- **Never create a GitHub Release or version tag** without the user explicitly asking for one. Regular commits/pushes to `main` are fine on their own; cutting a release is a separate, deliberate step.
- Bump `CURRENT_VERSION` in `updater.py` only when actually cutting a release, to match the release tag.
