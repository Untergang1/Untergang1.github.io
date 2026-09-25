import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

from scripts import build_site as build


PAYLOAD = [{"sha": "a" * 40, "commit": {
    "author": {"date": "2026-09-25T01:02:03Z"},
    "committer": {"date": "2026-09-26T01:02:03Z"},
    "message": '更新 <script> & "说明"\n\nLong description',
}}]


def response():
    stream = io.BytesIO(json.dumps(PAYLOAD).encode())
    stream.headers = {}
    return stream


class SnapshotTests(unittest.TestCase):
    def make_source(self, source, html):
        (source / "assets").mkdir()
        (source / "index.html").write_text(html, encoding="utf-8")
        for name in ("main.js", "style.css"):
            (source / "assets" / name).write_text("/* asset */")

    @patch.object(build, "fetch_project")
    def test_single_page_edits_order_and_project_changes(self, fetch):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            output = source / "_site"
            self.make_source(source, "")
            fetch.return_value = build.commit_data(PAYLOAD, "")
            for names in (("one", "two"), ("two", "one", "three"), ("three",)):
                html = '<!doctype html><p>修改后的简介 &amp; 说明</p><ul class="list">'
                html += "".join(f'<li><a data-repo="{name}">{name}</a></li>' for name in names)
                html += '</ul><footer>页脚</footer>'
                (source / "index.html").write_text(html, encoding="utf-8")
                snapshot = build.build_site(source, output, "token")
                self.assertEqual((output / "index.html").read_bytes(),
                                 (source / "index.html").read_bytes())
                self.assertEqual(list(snapshot["projects"]), list(names))

    @patch.object(build, "fetch_project")
    def test_offline_preview_and_invalid_defaults(self, fetch):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            html = ('<ul class="list"><li><a data-repo="example" data-sha="abcdef1" '
                    'data-date="2026-09-25" data-msg="说明">'
                    '<span class="n">3</span></a></li></ul>')
            self.make_source(source, html)
            output = source / "_site"
            snapshot = build.build_site(source, output, "", preview=True)
            fetch.assert_not_called()
            self.assertEqual(snapshot["projects"], {"example": {
                "sha": "abcdef1", "date": "2026-09-25", "msg": "说明", "count": 3,
            }})
            self.assertEqual((output / "assets/main.js").read_bytes(),
                             (source / "assets/main.js").read_bytes())
            (source / "index.html").write_text(html.replace('data-sha="abcdef1"', 'data-sha="bad"'))
            with self.assertRaisesRegex(ValueError, "example"):
                build.build_site(source, output, "", preview=True)
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, "GITHUB_TOKEN"):
                build.build_site(source, output, "")

    def test_actual_page_has_valid_projects_and_defaults(self):
        html = (build.ROOT / "index.html").read_text(encoding="utf-8")
        projects = build.read_projects(html)
        defaults = build.preview_projects(html)
        self.assertTrue(projects)
        self.assertEqual(list(projects), list(defaults))

    def test_parser_preserves_optional_authors(self):
        self.assertEqual(build.read_projects(
            '<ul class="list"><li><a data-repo="original"></a></li>'
            '<li><a data-repo="fork" data-author="contributor"></a></li></ul>'
        ), {"original": None, "fork": "contributor"})

    def test_parser_ignores_non_project_links_and_rejects_duplicates(self):
        self.assertEqual(build.read_projects(
            '<a data-repo="outside"></a><ul class="list"><li>'
            '<a data-repo="one"></a></li></ul><ul><a data-repo="other"></a></ul>'
        ), {"one": None})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            build.read_projects('<ul class="list"><a data-repo="x"></a><a data-repo="x"></a></ul>')

    def test_single_commit_and_special_characters(self):
        self.assertEqual(build.commit_data(PAYLOAD, ""), {
            "sha": "aaaaaaa", "date": "2026-09-25",
            "msg": '更新 <script> & "说明"', "count": 1,
        })

    def test_pagination_with_query_parameters_after_page(self):
        link = ('<https://api.github.com/repos/u/r/commits?page=2&per_page=1>; rel="next", '
                '<https://api.github.com/repos/u/r/commits?page=123&per_page=1>; rel="last"')
        self.assertEqual(build.commit_data(PAYLOAD, link)["count"], 123)
        with self.assertRaisesRegex(ValueError, "last page"):
            build.commit_data(PAYLOAD, link.split(",")[0])

    def test_missing_author_date_uses_committer(self):
        payload = copy.deepcopy(PAYLOAD)
        payload[0]["commit"]["author"] = None
        self.assertEqual(build.commit_data(payload, "")["date"], "2026-09-26")

    def test_empty_and_incomplete_payloads_fail(self):
        for payload in ([], {}, [{}], [{"sha": "bad", "commit": {}}]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                build.commit_data(payload, "")

    @patch.object(build, "urlopen")
    def test_authenticated_request_preserves_author_filter(self, opened):
        opened.return_value = response()
        build.fetch_project("OSWorld", "untergang404", "test-token")
        request = opened.call_args.args[0]
        self.assertEqual(parse_qs(urlsplit(request.full_url).query), {
            "per_page": ["1"], "author": ["untergang404"],
        })
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertEqual(opened.call_args.kwargs["timeout"], 20)

    @patch.object(build.time, "sleep")
    @patch.object(build, "urlopen")
    def test_transient_errors_retry_then_succeed(self, opened, sleep):
        opened.side_effect = [URLError("offline"), HTTPError("url", 503, "busy", {}, None), response()]
        self.assertEqual(build.fetch_project("x", None, "token")["count"], 1)
        self.assertEqual(sleep.call_args_list, [call(2), call(5)])

    @patch.object(build.time, "sleep")
    @patch.object(build, "urlopen")
    def test_timeout_stops_after_three_attempts(self, opened, sleep):
        opened.side_effect = TimeoutError("timeout")
        with self.assertRaisesRegex(RuntimeError, "Network"):
            build.fetch_project("x", None, "token")
        self.assertEqual(opened.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(2), call(5)])

    @patch.object(build.time, "sleep")
    @patch.object(build, "urlopen")
    def test_permission_missing_and_rate_limit_errors_do_not_retry(self, opened, sleep):
        for code in (401, 403, 404, 429):
            with self.subTest(code=code):
                opened.reset_mock()
                opened.side_effect = HTTPError("url", code, "failed", {}, None)
                with self.assertRaisesRegex(RuntimeError, str(code)):
                    build.fetch_project("x", None, "token")
                self.assertEqual(opened.call_count, 1)
        sleep.assert_not_called()

    @patch.object(build, "fetch_project")
    def test_build_writes_only_site_files_and_failure_leaves_no_artifact(self, fetch):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            output = source / "_site"
            html = '<ul class="list"><a data-repo="one"></a><a data-repo="two"></a></ul>'
            self.make_source(source, html)
            fetch.return_value = build.commit_data(PAYLOAD, "")
            snapshot = build.build_site(source, output, "token")
            self.assertEqual(json.loads((output / "data/projects.json").read_text()), snapshot)
            self.assertEqual((output / "index.html").read_text(), html)
            self.assertEqual(len(snapshot["projects"]), 2)
            self.assertEqual(sorted(str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()),
                             ["assets/main.js", "assets/style.css", "data/projects.json", "index.html"])
            fetch.side_effect = [build.commit_data(PAYLOAD, ""), RuntimeError("GitHub HTTP 404")]
            with self.assertRaisesRegex(RuntimeError, "two: GitHub HTTP 404"):
                build.build_site(source, output, "token")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
