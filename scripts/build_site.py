"""Build a complete Pages snapshot using only the Python standard library."""

import json
import os
import re
import shutil
import sys
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OWNER = "Untergang1"


class ProjectParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lists = []
        self.projects = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "ul":
            self.lists.append("list" in (attrs.get("class") or "").split())
        if tag != "a" or not any(self.lists) or "data-repo" not in attrs:
            return
        repo = attrs["data-repo"]
        author = attrs.get("data-author")
        if not repo or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
            raise ValueError("Invalid data-repo")
        if repo in self.projects:
            raise ValueError(f"Duplicate project: {repo}")
        if author is not None and not re.fullmatch(r"[A-Za-z0-9-]+", author):
            raise ValueError(f"Invalid data-author for {repo}")
        self.projects[repo] = author

    def handle_endtag(self, tag):
        if tag == "ul" and self.lists:
            self.lists.pop()


def read_projects(html):
    parser = ProjectParser()
    parser.feed(html)
    parser.close()
    if not parser.projects:
        raise ValueError("No projects found in ul.list")
    return parser.projects


def commit_data(payload, link_header):
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError("Expected one latest commit; received empty or invalid data")
    try:
        entry = payload[0]
        sha = entry["sha"]
        commit = entry["commit"]
        timestamp = ((commit.get("author") or {}).get("date") or
                     (commit.get("committer") or {}).get("date"))
        message = commit["message"].split("\n")[0]
        if not re.fullmatch(r"[a-f0-9]{40}", sha) or not message.strip():
            raise ValueError("Invalid SHA or empty commit message")
        commit_date = date.fromisoformat(timestamp[:10]).isoformat()
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError("Incomplete commit data") from error

    # With per_page=1, the last page number is the filtered commit count.
    pages = {}
    for part in link_header.split(","):
        match = re.search(r'<([^>]+)>;\s*rel="([^"]+)"', part)
        if match:
            pages[match[2]] = parse_qs(urlsplit(match[1]).query)
    if "next" in pages and "last" not in pages:
        raise ValueError("Pagination is missing the last page")
    try:
        count = int(pages["last"]["page"][0]) if "last" in pages else 1
        if count < 1 or count > 2**53 - 1:
            raise ValueError("Invalid commit count")
    except (KeyError, IndexError, ValueError) as error:
        raise ValueError("Invalid pagination") from error
    return {"sha": sha[:7], "date": commit_date, "msg": message, "count": count}


def fetch_project(repo, author, token):
    query = {"per_page": "1"}
    if author:
        query["author"] = author
    request = Request(
        f"https://api.github.com/repos/{OWNER}/{repo}/commits?{urlencode(query)}",
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": f"Bearer {token}",
                 "User-Agent": "Untergang1-homepage"},
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return commit_data(json.load(response), response.headers.get("Link", ""))
        except HTTPError as error:
            # Permission, missing repository and rate-limit errors are not retried.
            error.close()
            if not 500 <= error.code < 600 or attempt == 2:
                raise RuntimeError(f"GitHub HTTP {error.code}") from error
        except (URLError, TimeoutError, ConnectionError) as error:
            if attempt == 2:
                raise RuntimeError(f"Network request failed: {error}") from error
        time.sleep((2, 5)[attempt])


def build_site(source, output, token):
    # Never leave a previous local artifact available after a failed build.
    if output.exists():
        shutil.rmtree(output)
    if not token:
        raise ValueError("GITHUB_TOKEN is required")
    html = (source / "index.html").read_text(encoding="utf-8")
    projects = {}
    failures = []
    for repo, author in read_projects(html).items():
        try:
            projects[repo] = fetch_project(repo, author, token)
            print(f"Fetched {repo}")
        except (RuntimeError, ValueError) as error:
            failures.append(f"{repo}: {error}")
    if failures:
        raise RuntimeError("Snapshot failed; no deployment artifact created:\n" + "\n".join(failures))
    snapshot = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "projects": projects,
    }
    try:
        (output / "data").mkdir(parents=True)
        (output / "index.html").write_text(html, encoding="utf-8")
        (output / "data/projects.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        shutil.rmtree(output)
        raise
    return snapshot


def main():
    try:
        snapshot = build_site(ROOT, ROOT / "_site", os.environ.get("GITHUB_TOKEN", ""))
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    summary = f"Fetched {len(snapshot['projects'])} projects at {snapshot['generatedAt']}.\n"
    print(summary, end="")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
