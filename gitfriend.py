#!/usr/bin/env python3
"""
git_autosync.py
----------------
One-click GitHub sync for people who don't want to learn git.

WHAT IT DOES (every time you double-click / run it):
  1. First run in a folder  -> sets up git, asks your name + the GitHub
     repo URL once, and saves them so it never asks again.
  2. Every run after that   -> pulls the latest changes, adds every file
     you changed, commits as "<your name> update", and pushes.

That's it. Work on your files, run this script, done. Your teammate
just runs `git clone <repo-url>` once, then runs this same script
whenever they want to grab the latest changes or send up their own.

Requirements: Git must be installed and on PATH.
  Windows: https://git-scm.com/download/win
  Mac:     run `git --version` in Terminal (it'll offer to install)

HOW TO RUN:
  - Double-click this file (if .py files are set to run with Python), OR
  - Open a terminal in this folder and run:  python git_autosync.py

If ANYTHING goes wrong, this script tries to explain the problem in
plain English and tells you what to do next — it should never just
show a scary wall of red text.
"""

import json
import subprocess
import sys
import os

CONFIG_FILE = ".gitautosync.json"
BRANCH = "main"


# ---------- small helpers ----------

def run(cmd, check=True):
    """Run a shell/git command, return (success, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        )
    except Exception as e:
        return False, f"Could not even run the command. Details: {e}"
    output = (result.stdout or "") + (result.stderr or "")
    if check and result.returncode != 0:
        return False, output
    return True, output


def git_installed():
    ok, _ = run("git --version", check=False)
    return ok


def is_git_repo():
    return os.path.isdir(".git")


def load_config():
    """Read the saved settings. If the file is broken/corrupted, treat
    it as if it doesn't exist so we just re-ask instead of crashing."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print("(Your settings file looked damaged, so we'll set it up again.)\n")
            return {}
    return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except OSError as e:
        print(f"\n⚠️  Couldn't save your settings to disk ({e}).")
        print("The sync may still work this time, but you might be asked")
        print("to set up again next time you run this.")


def ask(prompt):
    """Ask for input, always stripped, never crashes on weird input."""
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\nStopped — no problem, just run the program again when ready.")
        pause_and_exit(1)


def pause_and_exit(code=0):
    try:
        input("\nPress Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(code)


# ---------- setup (runs only on first use in a folder) ----------

def first_time_setup():
    print("=" * 50)
    print("First time running in this folder — quick 30-second setup.")
    print("(You'll only ever see this once per folder.)")
    print("=" * 50)

    cfg = {}

    print("\nStep 1: What's your name?")
    print("This gets used as your save label, like 'Vanshika update'.")
    name = ask("Your name: ")
    while not name:
        print("Please type something — even a nickname is fine.")
        name = ask("Your name: ")
    cfg["name"] = name

    if not is_git_repo():
        print("\nStep 2: Setting up this folder for GitHub...")
        ok, out = run("git init")
        if not ok:
            print("⚠️  Something went wrong setting up git here:\n" + out)
            pause_and_exit(1)
        run(f"git branch -M {BRANCH}")
        print("Done.")
    else:
        print("\nStep 2: This folder is already set up for git. Skipping.")

    ok, remotes = run("git remote", check=False)
    if "origin" not in remotes:
        print("\nStep 3: Where does this folder's GitHub repo live?")
        print("Paste the link that looks like:")
        print("  https://github.com/yourname/yourrepo.git")
        url = ask("Repo link: ")
        while not url:
            print("That was empty — please paste the repo link.")
            url = ask("Repo link: ")
        cfg["remote"] = url
        ok, out = run(f"git remote add origin {url}")
        if not ok:
            print("⚠️  Couldn't save that repo link:\n" + out)
            pause_and_exit(1)
    else:
        print("\nStep 3: This folder already knows where its GitHub repo is. Skipping.")
        cfg["remote"] = remotes.strip()

    save_config(cfg)
    print("\n✅ Setup complete! Your info is saved in this folder as", CONFIG_FILE)
    print("(Don't delete that file, or you'll be asked to set up again — that's OK too.)\n")
    return cfg


# ---------- plain-English explanations for common git problems ----------

def explain_pull_problem(out):
    low = out.lower()
    if "no upstream" in low or "couldn't find remote ref" in low or "unknown revision" in low:
        return None  # not a real problem — just means nothing to pull yet
    if "could not resolve host" in low or "network" in low or "timed out" in low:
        return "Looks like there's no internet connection right now. Connect to " \
               "wifi/data and run the program again."
    if "permission denied" in low or "authentication failed" in low or "403" in low:
        return "GitHub didn't accept your login for this repo. Make sure you've " \
               "signed in to git with the correct GitHub account, and that this " \
               "account has been added as a collaborator on the repo."
    if "repository not found" in low or "not found" in low:
        return "GitHub says this repo doesn't exist (or you don't have access to " \
               "it). Double check the repo link with the project owner."
    if "conflict" in low:
        return "Your files and the GitHub files changed in the exact same spot, " \
               "so the computer can't guess which version to keep. Send the " \
               "message below to the project owner — they'll sort it out:\n\n" + out
    return None  # unknown problem — caller will show the raw details


def explain_push_problem(out):
    low = out.lower()
    if "could not resolve host" in low or "network" in low or "timed out" in low:
        return "Looks like there's no internet connection right now. Connect to " \
               "wifi/data and run the program again."
    if "permission denied" in low or "authentication failed" in low or "403" in low:
        return "GitHub didn't accept your login, or you don't have permission to " \
               "upload to this repo yet. Ask the project owner to add you as a " \
               "collaborator on GitHub."
    if "non-fast-forward" in low or "fetch first" in low or "rejected" in low:
        return "Someone else's changes appeared on GitHub while this was running. " \
               "Just run the program one more time — it'll grab those changes first."
    return None


# ---------- main sync flow ----------

def sync(cfg):
    name = cfg["name"]
    commit_message = f"{name} update"

    # Make sure origin still matches what's saved (in case repo was
    # cloned fresh and origin already exists from the clone itself).
    ok, remotes = run("git remote", check=False)
    if "origin" not in remotes:
        run(f"git remote add origin {cfg['remote']}")

    print("Step 1 of 3: Checking for anyone else's changes on GitHub...")
    ok, out = run(f"git pull origin {BRANCH} --rebase", check=False)
    if not ok:
        explanation = explain_pull_problem(out)
        if explanation is None and (
            "no upstream" in out.lower()
            or "couldn't find remote ref" in out.lower()
            or "unknown revision" in out.lower()
        ):
            print("  (Nothing on GitHub yet — that's expected for a brand new repo.)")
        elif explanation:
            print("\n⚠️  " + explanation)
            pause_and_exit(1)
        else:
            print("\n⚠️  Couldn't check for updates. Here's the technical detail,")
            print("in case the project owner needs it:\n")
            print(out)
            pause_and_exit(1)
    else:
        print("  Up to date with GitHub.")

    print("Step 2 of 3: Saving your changes on this computer...")
    run("git add -A")

    ok, status = run("git status --porcelain", check=False)
    if not status.strip():
        print("  You have no new changes — nothing to send.")
        print("\nYou're all up to date. Safe to close this window.")
        return

    ok, out = run(f'git commit -m "{commit_message}"', check=False)
    if not ok and "nothing to commit" not in out.lower():
        print("\n⚠️  Something went wrong while saving your changes. Here's the")
        print("technical detail, in case the project owner needs it:\n")
        print(out)
        pause_and_exit(1)

    print(f"Step 3 of 3: Sending your changes to GitHub as '{commit_message}'...")
    ok, out = run(f"git push -u origin {BRANCH}", check=False)
    if not ok:
        explanation = explain_push_problem(out)
        if explanation:
            print("\n⚠️  " + explanation)
        else:
            print("\n⚠️  Couldn't send your changes to GitHub. Here's the technical")
            print("detail, in case the project owner needs it:\n")
            print(out)
        pause_and_exit(1)

    print("\n✅ Done! Your changes are safely on GitHub.")
    print("You're all synced up. Safe to close this window.")


def main():
    print("=" * 50)
    print("      GitHub AutoSync")
    print("=" * 50 + "\n")

    if not git_installed():
        print("Git isn't installed on this computer yet.")
        print("Ask the project owner, or download it here:")
        print("  https://git-scm.com/downloads")
        pause_and_exit(1)

    cfg = load_config()
    if not cfg or "name" not in cfg or "remote" not in cfg:
        cfg = first_time_setup()

    sync(cfg)
    pause_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Absolute last resort — this should never normally trigger,
        # but if it does, show something human instead of a crash log.
        print("\n⚠️  Something unexpected happened:")
        print(f"   {e}")
        print("\nThis isn't your fault — please screenshot this window and")
        print("send it to the project owner.")
        pause_and_exit(1)
