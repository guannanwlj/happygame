# FP-001 Test Scenarios — multipart 解析能力

Module under test: `social_app/app.py` — `parse_multipart`,
`UploadedFile`, `MultipartForm`, `Request.headers` wiring (spec: task card
§3.2/§7/§8). Pure-function tests build multipart bodies in-process with the
card §6 `build_multipart` helper (no network); the `_dispatch` wiring tests
run a real `ThreadingHTTPServer` on a random port with a capturing route,
matching the existing FP-001 skeleton test style.

## A. 文本＋文件混合解析

| # | Scenario | Expected |
|---|----------|----------|
| A1 | 1 个文本字段 `content`＋3 个同名 `images` 文件 part（不同字节） | `fields["content"]` 正确；`files` 恰 3 项，顺序＝构造顺序，filename/data 逐项一致 |
| A2 | 文件 part 自带 `Content-Type` 头 | 该头被忽略，data 不受影响 |
| A3 | 空文件（`filename=""`，data 为 `b""`） | 仍进 `files`，`filename == ""`、`data == b""` |
| A4 | 只有文本字段、没有文件 | `files == []`，`fields` 齐全 |
| A5 | 空表单（仅闭合 boundary） | `MultipartForm(fields={}, files=[])`，不抛错 |

## B. 同名字段与中文文件名

| # | Scenario | Expected |
|---|----------|----------|
| B1 | 同名文本字段出现 2 次（`tag=a`、`tag=b`） | `fields["tag"] == "a"`（取首个，与 parse_form 语义一致） |
| B2 | 同名文件字段 `images` 多次出现 | 全部保留在 `files`，顺序＝出现顺序，内容互不串 |
| B3 | 中文文件名「图片1.png」（UTF-8 字节） | `filename == "图片1.png"`，data 逐字节一致 |
| B4 | 文本字段值为 UTF-8 中文 | 按 UTF-8 解码进 `fields` |

## C. boundary 形式与错误路径

| # | Scenario | Expected |
|---|----------|----------|
| C1 | `boundary=----X`（无引号） | 正常解析 |
| C2 | `boundary="----X"`（带引号） | 引号剥离，正常解析 |
| C3 | content_type 缺 `boundary` 参数 | `ValueError` |
| C4 | content_type 为空串 / 非 multipart 串 | `ValueError` |
| C5 | boundary 与请求体对不上（不同 boundary 拼体） | `ValueError` |
| C6 | 空请求体 | `ValueError` |
| C7 | 请求体缺少闭合 `--boundary--`（截断） | `ValueError` |
| C8 | part 头部无空行分隔（结构坏） | `ValueError` |

## D. parse_form 回归（urlencoded 路径不变）

| # | Scenario | Expected |
|---|----------|----------|
| D1 | `content=hello+world` | `{"content": "hello world"}` |
| D2 | 重复名 `a=1&a=2` | 取首值 `{"a": "1"}` |
| D3 | 空串 `content=` | 保留 `{"content": ""}` |

## E. Request.headers 接线

| # | Scenario | Expected |
|---|----------|----------|
| E1 | `Request(method="GET", path="/")` 默认构造 | `headers == {}`（既有构造处零改动） |
| E2 | 真实 HTTP 请求带 `X-Custom-Header: abc` 与 `Content-Type` 头 | 捕获的 Request：headers 键为小写、值完整（`x-custom-header == "abc"`） |
| E3 | 同一请求带查询串＋Cookie＋POST body | method/path/query/body/cookies 均不受 headers 接线影响 |

Skeleton/test file: `tests/test_fp001_multipart.py`.
