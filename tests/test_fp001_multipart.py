"""FP-001 tests: multipart/form-data parsing (social_app.app).

Scenarios documented in docs/test-cases/fp001-multipart-parser.md. Multipart
bodies are built in-process with the card §6 ``build_multipart`` helper (no
network, no mocks). The ``_dispatch`` headers wiring (E2–E3) is exercised
through a real ``ThreadingHTTPServer`` on a random port with a capturing
route, matching the existing FP-001 skeleton test style.
"""

import contextlib
import threading
import urllib.request

import pytest

from social_app.app import (
    MultipartForm,
    Request,
    Response,
    SocialApp,
    UploadedFile,
    create_server,
    parse_form,
    parse_multipart,
)

BOUNDARY = "----WebKitFormBoundaryFP001"
CONTENT_TYPE = f"multipart/form-data; boundary={BOUNDARY}"


def build_multipart(boundary: str, parts: list[tuple[str, str | None, bytes]]) -> bytes:
    """(name, filename, data); filename 为 None 表示文本字段。"""
    out: list[bytes] = []
    for name, filename, data in parts:
        if filename is None:
            head = f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
        else:
            head = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            )
        out.append(head.encode("utf-8") + data + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(out)


class TestMixedParsing:
    """A1–A5: text + file parts."""

    def test_text_plus_three_files_in_order(self):
        body = build_multipart(
            BOUNDARY,
            [
                ("content", None, "带图帖子".encode("utf-8")),
                ("images", "a.png", b"\x89PNG-aaa"),
                ("images", "b.jpg", b"\xff\xd8-b"),
                ("images", "c.webp", b"RIFF-c"),
            ],
        )
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.fields == {"content": "带图帖子"}
        assert [(f.filename, f.data) for f in form.files] == [
            ("a.png", b"\x89PNG-aaa"),
            ("b.jpg", b"\xff\xd8-b"),
            ("c.webp", b"RIFF-c"),
        ]
        assert all(f.field == "images" for f in form.files)

    def test_part_content_type_header_is_ignored(self):
        body = build_multipart(BOUNDARY, [("images", "a.png", b"BYTES")])
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.files[0].data == b"BYTES"

    def test_empty_filename_is_still_a_file(self):
        body = build_multipart(BOUNDARY, [("images", "", b"")])
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.fields == {}
        assert [(f.filename, f.data) for f in form.files] == [("", b"")]

    def test_text_only_body(self):
        body = build_multipart(
            BOUNDARY, [("content", None, b"hi"), ("tag", None, b"t")]
        )
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.files == []
        assert form.fields == {"content": "hi", "tag": "t"}

    def test_empty_form_yields_empty_result(self):
        form = parse_multipart(
            f"--{BOUNDARY}--\r\n".encode("utf-8"), CONTENT_TYPE
        )
        assert form.fields == {}
        assert form.files == []


class TestDuplicateNamesAndUnicode:
    """B1–B4: duplicate names, Chinese filenames."""

    def test_duplicate_text_field_keeps_first_value(self):
        body = build_multipart(
            BOUNDARY,
            [("tag", None, b"a"), ("tag", None, b"b")],
        )
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.fields == {"tag": "a"}

    def test_duplicate_file_field_keeps_all_in_order(self):
        body = build_multipart(
            BOUNDARY,
            [("images", "1.png", b"one"), ("images", "2.png", b"two")],
        )
        form = parse_multipart(body, CONTENT_TYPE)
        assert [(f.filename, f.data) for f in form.files] == [
            ("1.png", b"one"),
            ("2.png", b"two"),
        ]

    def test_chinese_filename_decoded_and_content_intact(self):
        body = build_multipart(
            BOUNDARY,
            [
                ("tag", None, b"first"),
                ("tag", None, b"second"),
                ("images", "图片1.png", "第一张".encode("utf-8")),
                ("images", "图片2.png", "第二张".encode("utf-8")),
            ],
        )
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.fields == {"tag": "first"}
        assert [f.filename for f in form.files] == ["图片1.png", "图片2.png"]
        assert [f.data for f in form.files] == [
            "第一张".encode("utf-8"),
            "第二张".encode("utf-8"),
        ]

    def test_utf8_text_value(self):
        body = build_multipart(BOUNDARY, [("content", None, "你好".encode("utf-8"))])
        assert parse_multipart(body, CONTENT_TYPE).fields == {"content": "你好"}


class TestBoundaryAndErrors:
    """C1–C8: boundary forms and error paths."""

    def test_unquoted_boundary(self):
        body = build_multipart(BOUNDARY, [("content", None, b"ok")])
        form = parse_multipart(body, CONTENT_TYPE)
        assert form.fields == {"content": "ok"}

    def test_quoted_boundary(self):
        body = build_multipart(BOUNDARY, [("content", None, b"ok")])
        content_type = f'multipart/form-data; boundary="{BOUNDARY}"'
        assert parse_multipart(body, content_type).fields == {"content": "ok"}

    @pytest.mark.parametrize(
        "content_type",
        [
            "multipart/form-data",
            "",
            "application/x-www-form-urlencoded",
            'multipart/form-data; boundary=""',
        ],
    )
    def test_missing_boundary_raises(self, content_type):
        body = build_multipart(BOUNDARY, [("content", None, b"ok")])
        with pytest.raises(ValueError):
            parse_multipart(body, content_type)

    def test_boundary_mismatch_raises(self):
        body = build_multipart("----OtherBoundary", [("content", None, b"ok")])
        with pytest.raises(ValueError):
            parse_multipart(body, CONTENT_TYPE)

    def test_empty_body_raises(self):
        with pytest.raises(ValueError):
            parse_multipart(b"", CONTENT_TYPE)

    def test_missing_closing_delimiter_raises(self):
        part = (
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="content"'
            "\r\n\r\nok\r\n"
        ).encode("utf-8")
        with pytest.raises(ValueError):
            parse_multipart(part, CONTENT_TYPE)

    def test_part_without_header_separator_raises(self):
        broken = (
            f"--{BOUNDARY}\r\nContent-Disposition: form-data; name=\"content\"\r\n"
            f"--{BOUNDARY}--\r\n"
        ).encode("utf-8")
        with pytest.raises(ValueError):
            parse_multipart(broken, CONTENT_TYPE)


class TestParseFormRegression:
    """D1–D3: the urlencoded path is untouched."""

    def test_plus_decoding(self):
        assert parse_form(b"content=hello+world") == {"content": "hello world"}

    def test_duplicate_name_keeps_first(self):
        assert parse_form(b"a=1&a=2") == {"a": "1"}

    def test_blank_value_preserved(self):
        assert parse_form(b"content=") == {"content": ""}


@contextlib.contextmanager
def serving(app):
    """Serve `app` on a random free port; yield its base URL."""
    server = create_server(app, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestRequestHeadersWiring:
    """E1–E3: Request.headers default + _dispatch filling."""

    def test_default_headers_is_empty_dict(self):
        request = Request(method="GET", path="/")
        assert request.headers == {}
        assert request.params == {} and request.cookies == {}

    def test_dispatch_lowercases_and_preserves_headers(self):
        captured: list[Request] = []

        def capture(request: Request) -> Response:
            captured.append(request)
            return Response(body="ok")

        app = SocialApp()
        app.route("POST", "/capture", capture)
        with serving(app) as base_url:
            urllib.request.urlopen(
                urllib.request.Request(
                    base_url + "/capture?x=1",
                    data=b"payload",
                    method="POST",
                    headers={
                        "X-Custom-Header": "abc",
                        "Content-Type": CONTENT_TYPE,
                        "Cookie": "session=tok",
                    },
                ),
                timeout=5,
            ).read()
        request = captured[0]
        assert request.headers["x-custom-header"] == "abc"
        assert request.headers["content-type"] == CONTENT_TYPE
        # E3: existing fields unaffected by the wiring.
        assert request.method == "POST"
        assert request.path == "/capture"
        assert request.query == {"x": ["1"]}
        assert request.body == b"payload"
        assert request.cookies == {"session": "tok"}


# Contract sanity: the dataclasses expose exactly the card §3.2 attributes.
def test_contract_shapes():
    uploaded = UploadedFile(field="images", filename="图片1.png", data=b"x")
    form = MultipartForm(fields={"a": "1"}, files=[uploaded])
    assert (uploaded.field, uploaded.filename, uploaded.data) == (
        "images",
        "图片1.png",
        b"x",
    )
    assert form.fields == {"a": "1"} and form.files == [uploaded]
