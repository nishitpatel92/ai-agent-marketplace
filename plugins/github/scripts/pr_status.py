#!/usr/bin/env python3
"""Report CI status for a GitHub PR using only stdlib + GITHUB_TOKEN.

Combines three signals so the answer is correct across token types:
  - pull.mergeable_state  — `clean`/`unstable`/`blocked`/`behind`/`dirty`/`unknown`.
                            Encodes required-check status when branch protection
                            or rulesets are configured (Pro+ for private repos).
  - statusCheckRollup.state (GraphQL) — overall SUCCESS/FAILURE/PENDING.
                            Works with fine-grained PATs (the rollup state is
                            visible even though per-check details aren't).
  - Actions runs by head_sha — per-workflow detail. Needs `Actions: Read`.

Use `--watch` to poll until terminal. Use `--json` for machine output.

Auth: reads GITHUB_TOKEN (or GH_TOKEN) from env.

Exit codes:
  0  passing  (rollup SUCCESS, or all workflow runs success, or mergeable_state clean/unstable)
  1  failing  (any signal indicates failure)
  2  pending  (only meaningful in non-watch mode — checks still running)
  3  error    (auth, network, parse)
  4  timeout  (watch mode hit --timeout)
"""

from __future__ import annotations
import argparse, json, os, sys, time
import urllib.request, urllib.error


def _request(url: str, token: str, *, method: str = "GET", body: dict | None = None,
             accept: str = "application/vnd.github+json") -> dict | list | None:
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {token}" if accept != "graphql" else f"bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else None


def _graphql(token: str, query: str, variables: dict) -> dict:
    req = urllib.request.Request("https://api.github.com/graphql", method="POST")
    req.add_header("Authorization", f"bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps({"query": query, "variables": variables}).encode()
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_summary(repo: str, pr: int, token: str) -> dict:
    owner, name = repo.split("/", 1)
    pr_data = _request(f"https://api.github.com/repos/{repo}/pulls/{pr}", token)

    rollup_state = None
    try:
        gql = _graphql(token, """
            query($o:String!, $n:String!, $p:Int!) {
              repository(owner:$o, name:$n) {
                pullRequest(number:$p) {
                  commits(last:1) { nodes { commit { statusCheckRollup { state } } } }
                }
              }
            }""", {"o": owner, "n": name, "p": pr})
        rollup_state = (gql.get("data", {}).get("repository", {}).get("pullRequest", {})
                        .get("commits", {}).get("nodes", [{}])[0].get("commit", {})
                        .get("statusCheckRollup", {}) or {}).get("state")
    except (urllib.error.HTTPError, KeyError, TypeError, IndexError):
        rollup_state = None

    head_sha = pr_data["head"]["sha"]
    runs_data = _request(
        f"https://api.github.com/repos/{repo}/actions/runs"
        f"?head_sha={head_sha}&per_page=100", token)
    workflow_runs = [
        {"id": r["id"], "name": r["name"],
         "status": r["status"], "conclusion": r.get("conclusion"),
         "url": r["html_url"]}
        for r in (runs_data or {}).get("workflow_runs", [])
    ]

    return {
        "repo": repo, "pr": pr,
        "state": pr_data.get("state"),
        "mergeable": pr_data.get("mergeable"),
        "mergeable_state": pr_data.get("mergeable_state"),
        "head_sha": head_sha,
        "head_branch": pr_data["head"]["ref"],
        "rollup_state": rollup_state,
        "workflow_runs": workflow_runs,
    }


_ICONS = {"success": "✓", "failure": "✗", "cancelled": "-",
          "skipped": "-", "timed_out": "✗", "action_required": "?",
          "neutral": "·", "stale": "·"}


def render(s: dict) -> str:
    out = [f"PR {s['repo']}#{s['pr']} [{s['state']}] @ {s['head_sha'][:8]} ({s['head_branch']})",
           f"  mergeable_state: {s['mergeable_state']}",
           f"  rollup_state:    {s['rollup_state']}",
           f"  workflow runs ({len(s['workflow_runs'])}):"]
    for r in s["workflow_runs"]:
        icon = _ICONS.get(r.get("conclusion") or "", "·")
        status = r["conclusion"] or r["status"]
        out.append(f"    {icon} {r['name']:30s} {status:12s} run_id={r['id']}")
    return "\n".join(out)


def is_terminal(s: dict) -> bool:
    if s["mergeable_state"] == "unknown" and s["state"] == "open":
        return False
    runs = s["workflow_runs"]
    if not runs:
        return True
    return all(r["status"] == "completed" for r in runs)


def verdict(s: dict) -> str:
    """Returns 'pass'/'fail'/'pending'."""
    runs = s["workflow_runs"]
    if runs and any(r.get("conclusion") in ("failure", "cancelled", "timed_out") for r in runs):
        return "fail"
    if not is_terminal(s):
        return "pending"
    if s["mergeable_state"] in ("clean", "unstable"):
        return "pass"
    if s["rollup_state"] == "SUCCESS":
        return "pass"
    if runs and all(r.get("conclusion") == "success" for r in runs):
        return "pass"
    if s["rollup_state"] == "FAILURE" or s["mergeable_state"] in ("blocked", "behind", "dirty"):
        return "fail"
    return "pending"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--watch", action="store_true",
                    help="poll until terminal state, then exit")
    ap.add_argument("--interval", type=int, default=30,
                    help="seconds between polls in --watch (default 30)")
    ap.add_argument("--timeout", type=int, default=1800,
                    help="abort --watch after N seconds (default 1800)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("error: GITHUB_TOKEN (or GH_TOKEN) must be set in env", file=sys.stderr)
        sys.exit(3)

    deadline = time.time() + args.timeout
    while True:
        try:
            s = fetch_summary(args.repo, args.pr, token)
        except urllib.error.HTTPError as e:
            print(f"error: HTTP {e.code} {e.reason} on {e.url}", file=sys.stderr)
            sys.exit(3)
        except urllib.error.URLError as e:
            print(f"error: network: {e.reason}", file=sys.stderr)
            sys.exit(3)

        if args.as_json:
            print(json.dumps({**s, "verdict": verdict(s)}, indent=2))
        else:
            print(render(s))

        v = verdict(s)
        if not args.watch or is_terminal(s):
            sys.exit({"pass": 0, "fail": 1, "pending": 2}[v])
        if time.time() > deadline:
            print(f"error: timed out after {args.timeout}s", file=sys.stderr)
            sys.exit(4)
        if not args.as_json:
            print(f"  → polling in {args.interval}s")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
