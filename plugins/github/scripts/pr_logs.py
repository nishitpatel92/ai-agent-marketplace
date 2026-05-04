#!/usr/bin/env python3
"""Download logs of failed Actions jobs for a PR.

Finds the most recent failed workflow runs on the PR's head SHA, prints which
jobs and steps failed, and extracts the GitHub-supplied log archive into a
directory you specify.

Auth: GITHUB_TOKEN (or GH_TOKEN). Needs `Actions: Read` permission.
"""

from __future__ import annotations
import argparse, json, os, sys, tempfile, urllib.request, urllib.error, zipfile


def _request(url: str, token: str, *, json_out: bool = True) -> dict | bytes:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    return json.loads(data.decode()) if json_out else data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--out", default="./pr-logs", help="directory to extract logs into")
    ap.add_argument("--limit", type=int, default=1,
                    help="number of failed runs to download (default 1, most recent)")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("error: GITHUB_TOKEN (or GH_TOKEN) must be set", file=sys.stderr)
        sys.exit(3)

    try:
        pr_data = _request(f"https://api.github.com/repos/{args.repo}/pulls/{args.pr}", token)
        head_sha = pr_data["head"]["sha"]
        runs = _request(
            f"https://api.github.com/repos/{args.repo}/actions/runs"
            f"?head_sha={head_sha}&per_page=50", token)
    except urllib.error.HTTPError as e:
        print(f"error: HTTP {e.code} {e.reason}", file=sys.stderr)
        sys.exit(3)

    failed_terminals = ("failure", "cancelled", "timed_out")
    failed = [r for r in runs.get("workflow_runs", [])
              if r.get("conclusion") in failed_terminals][:args.limit]

    if not failed:
        print(f"no failed runs for {args.repo}#{args.pr} @ {head_sha[:8]}")
        sys.exit(0)

    os.makedirs(args.out, exist_ok=True)

    for run in failed:
        run_id = run["id"]
        print(f"\nfailed run: {run['name']} (id={run_id}, {run['html_url']})")

        try:
            jobs = _request(
                f"https://api.github.com/repos/{args.repo}/actions/runs/{run_id}/jobs", token)
        except urllib.error.HTTPError as e:
            print(f"  error fetching jobs: HTTP {e.code}")
            continue

        for j in jobs.get("jobs", []):
            if j.get("conclusion") not in failed_terminals:
                continue
            failed_steps = [s["name"] for s in j.get("steps", [])
                            if s.get("conclusion") in failed_terminals]
            steps_str = ", ".join(failed_steps) or "<no failed steps reported>"
            print(f"  ✗ job: {j['name']}\n    failed steps: {steps_str}")

        try:
            archive = _request(
                f"https://api.github.com/repos/{args.repo}/actions/runs/{run_id}/logs",
                token, json_out=False)
        except urllib.error.HTTPError as e:
            print(f"  error downloading logs: HTTP {e.code}")
            continue

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(archive)
            zip_path = tmp.name

        safe_name = run["name"].replace("/", "_").replace(" ", "-")
        subdir = os.path.join(args.out, f"{run_id}-{safe_name}")
        os.makedirs(subdir, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(subdir)
        os.unlink(zip_path)
        print(f"  extracted to: {subdir}")


if __name__ == "__main__":
    main()
