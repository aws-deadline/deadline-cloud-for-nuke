---
name: nuke-dev-setup
description: Automated dev environment setup for deadline-cloud-for-nuke. Use when onboarding, setting up the Nuke integration repo, building the package, or installing dependencies. The agent automates all steps and only prompts when user input is required.
tags: [skill, deadline-cloud, deadline-cloud-for-nuke, dev-setup, onboarding, nuke, compositing]
---

# Nuke Dev Setup

## Overview

AI-guided automated setup for the `deadline-cloud-for-nuke` project. The agent executes all steps, validates results, and only prompts the user when manual intervention is truly required.

## Usage

Use this skill when:
- Setting up a new dev environment for the Nuke integration
- Onboarding to the `deadline-cloud-for-nuke` repo
- Building the Python packages for the first time

## Core Concepts

**Platform:** Windows, Linux, or macOS. Nuke 15 or 16, Python 3.9+.

**Build system:** Hatch (Python)

## Agent Behavior

You **MUST** automate all possible steps by running commands directly.
You **MUST** only prompt the user when their input is required (fork URL, Nuke version, custom paths).
You **MUST** validate each step's output before proceeding to the next.
You **MUST** inform the user clearly when manual intervention is needed (e.g., installing Nuke itself).
You **SHOULD** report progress at each step.

## Setup Workflow

Follow the detailed step-by-step workflow in [references/setup-guide.md](references/setup-guide.md).

Summary of steps:
1. Detect OS (Windows, Linux, or macOS)
2. Verify Python 3.9+
3. Detect Nuke installation
4. Install Hatch
5. Build the package (`hatch build`)
6. Install the package into Nuke's Python (editable mode)
7. Install `deadline-cloud` client library into Nuke's Python
8. Configure `NUKE_PATH` environment variable
9. Set `NUKE_EXECUTABLE` environment variable
10. Install test dependencies
11. Display summary
