"""
gitstats.py - count one author's commits and lines of code across local clones.

    python tools/gitstats.py --author me@example.com --author "My Name" \
        --skip-loc Josh-Heath123 ../Equity-Lens ../Culprit ... > tools/stats.json

Commits: every commit the author made, on every branch, merges included.
Lines:   lines added in the author's non-merge commits, counting code files
         only. Lockfiles, virtual environments, site-packages, build output,
         minified files, source maps and test data are skipped, as are
         commits titled "Merge ..." (they carry other people's work).
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import subprocess
import sys

CODE = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".java": "Java", ".php": "PHP",
    ".cpp": "C++", ".cc": "C++", ".h": "C++", ".hpp": "C++", ".c": "C", ".rs": "Rust",
    ".css": "CSS", ".scss": "CSS", ".html": "HTML", ".sql": "SQL", ".pl": "Prolog",
    ".sh": "Shell", ".ps1": "Shell", ".yml": "YAML", ".yaml": "YAML", ".tf": "Terraform", ".hcl": "Terraform",
    ".toml": "Config", ".mako": "Config", ".tpl": "Config",
}
SKIP = re.compile(
    r"(^|/)(node_modules|dist|build|vendor|coverage|\.?venv[^/]*|site-packages|__pycache__|testdata)/"
    r"|\.min\.(js|css)$|\.map$|(-lock\.(json|yaml)|\.lock)$"
)


def language(path: str) -> str | None:
    if SKIP.search(path):
        return None
    base = os.path.basename(path)
    if base.startswith("Dockerfile") or base == "Makefile":
        return "Config"
    return CODE.get(os.path.splitext(base)[1].lower())


def repo_name(path: str) -> str:
    url = subprocess.run(["git", "-C", path, "config", "--get", "remote.origin.url"],
                         capture_output=True, text=True).stdout.strip()
    m = re.search(r"github\.com[:/](.+?)(\.git)?$", url)
    return m.group(1) if m else os.path.basename(os.path.abspath(path))


def scan(path: str, authors: set[str]):
    log = subprocess.run(
        ["git", "-C", path, "log", "--all", "--no-renames", "--numstat", "--date=short",
         "--format=@@%H|%ae|%an|%ad|%s"],
        capture_output=True, text=True, errors="replace").stdout
    seen, counted = set(), set()
    days = collections.Counter()
    langs = collections.Counter()
    added = deleted = 0
    current = None
    for line in log.splitlines():
        if line.startswith("@@"):
            sha, email, name, day, subject = line[2:].split("|", 4)
            current = None
            if email.lower() in authors or name.lower() in authors:
                if sha not in seen:
                    seen.add(sha)
                    days[day] += 1
                if not subject.startswith("Merge ") and sha not in counted:
                    counted.add(sha)
                    current = sha
            continue
        if current and line.strip():
            a, d, file = line.split("\t", 2)
            lang = language(file) if a != "-" else None
            if lang:
                added += int(a)
                deleted += int(d)
                langs[lang] += int(a)
    return {"commits": len(seen), "added": added, "deleted": deleted, "languages": langs, "days": days}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", action="append", required=True, help="email or name, repeatable")
    ap.add_argument("--skip-loc", action="append", default=[], help="repo name whose lines are not counted")
    ap.add_argument("repos", nargs="+")
    args = ap.parse_args()
    authors = {a.lower() for a in args.author}

    repos, langs, days = [], collections.Counter(), collections.Counter()
    for path in args.repos:
        name = repo_name(path)
        s = scan(path, authors)
        if not s["commits"]:
            continue
        skip = any(k.lower() in name.lower() for k in args.skip_loc)
        repos.append({"repo": name, "commits": s["commits"],
                      "added": 0 if skip else s["added"], "deleted": 0 if skip else s["deleted"]})
        if not skip:
            langs.update(s["languages"])
        days.update(s["days"])

    json.dump({
        "generated": dt.date.today().isoformat(),
        "totals": {"repos": len(repos), "commits": sum(r["commits"] for r in repos),
                   "added": sum(r["added"] for r in repos), "deleted": sum(r["deleted"] for r in repos)},
        "repos": sorted(repos, key=lambda r: -r["commits"]),
        "languages": dict(langs.most_common()),
        "days": dict(sorted(days.items())),
    }, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
