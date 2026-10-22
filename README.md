# My Feather build

I use this workflow to build Feather commit `7078b053c0af262809a48e4d3898d42b0d35fedf` with the newest iOS 27.2 SDK installed on GitHub's Apple Silicon `xcode-27` runner. Feather itself is unchanged and remains the work of its upstream contributors, under their GPL-3.0 license.

The resulting IPA is ad-hoc signed and requires re-signing before ordinary installation. The build keeps the minimum iOS version at 16.0, so the deployment target allows my iPhone and iPad running 27.0.1. This is not a physical-device test.

GitHub made the Apple Silicon `xcode-27` image generally available on October 15, 2026. Standard runners are free for public repositories. The image software list dated October 12 currently documents Xcode 27.2 beta 2. Apple's newest published Xcode is 27.2 RC (27B48). The workflow prefers RC when installed and records the exact compiler, SDK build, commit, and IPA SHA-256; it does not claim a beta build is the latest RC.

This repository contains build instructions only. It does not include an Apple SDK, account credentials, personal signing certificates, provisioning profiles, or source code from my Hackintosh projects. No release is published automatically. Build artifacts expire after seven days.

I largely prepared these build instructions with AI assistance (GPT-6.1 Sol).

## Files

- `.github/workflows/feather-ipa.yml`: manual or build-file-change trigger, standard Apple Silicon runner, read-only repository permissions, pinned GitHub actions.
- `build_feather.py`: official Xcode project build, current resource compilation, source hash verification, framework and application signing, IPA integrity checks.

I use the full matching Xcode toolchain here. The local Intel experiments and their SwiftPM adapter are not used by this workflow.
