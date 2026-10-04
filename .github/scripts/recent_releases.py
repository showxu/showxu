#!/usr/bin/env python3
"""Rewrite the recent releases block in the profile README."""

import argparse
import json
import os
import re
import sys
import urllib.request

OWNERS = ("swift-library", "computer-mcp", "skill-cli", "showxu")
LIMIT = 6
START = "<!-- recent-releases:start -->"
END = "<!-- recent-releases:end -->"
QUERY = """
query($login: String!) {
  repositoryOwner(login: $login) {
    repositories(first: 100, privacy: PUBLIC, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        isArchived
        latestRelease { tagName url publishedAt }
      }
    }
  }
}
"""


def fetch_repositories(owner, token):
    body = json.dumps({"query": QUERY, "variables": {"login": owner}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        sys.exit(f"GraphQL error for {owner}: {payload['errors'][0]['message']}")
    owner_node = payload["data"]["repositoryOwner"]
    if owner_node is None:
        sys.exit(f"Owner not found: {owner}")
    return owner_node["repositories"]["nodes"]


def recent_releases(token):
    releases = []
    for owner in OWNERS:
        for repo in fetch_repositories(owner, token):
            release = repo["latestRelease"]
            if release and not repo["isArchived"]:
                releases.append((release["publishedAt"], repo["name"], release))
    releases.sort(key=lambda item: item[0], reverse=True)
    return releases[:LIMIT]


def render(releases):
    lines = []
    for published_at, name, release in releases:
        version = re.sub(r"^v(?=\d)", "", release["tagName"])
        lines.append(f"- [{name} {version}]({release['url']}) - {published_at[:10]}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("readme", nargs="?", default="README.md")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("Set GITHUB_TOKEN or GH_TOKEN.")

    releases = recent_releases(token)
    if not releases:
        sys.exit("No releases found; leaving the README unchanged.")

    with open(args.readme, encoding="utf-8") as handle:
        readme = handle.read()
    pattern = re.compile(f"{re.escape(START)}\n.*?{re.escape(END)}", re.DOTALL)
    if not pattern.search(readme):
        sys.exit(f"Markers {START} and {END} not found in {args.readme}.")

    block = f"{START}\n{render(releases)}\n{END}"
    updated = pattern.sub(lambda _: block, readme, count=1)
    if updated == readme:
        print("Recent releases unchanged.")
        return
    with open(args.readme, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print(f"Updated {len(releases)} recent releases.")


if __name__ == "__main__":
    main()
