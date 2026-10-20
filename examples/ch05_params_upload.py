"""
ch05 - 参数来源全解 + 表单 + 文件上传
对应脑图「三、核心能力」：Path/Query/Header/Cookie / 请求体 / 文件上传 / 表单

知识点：
1. 四个"显式来源"：Path() / Query() / Header() / Cookie()
2. 默认值 vs Annotated 两种写法
3. Form() 接收表单（application/x-www-form-urlencoded / multipart）
4. File() 与 UploadFile 的区别
5. 多文件上传、读取文件内容、客户端文件名与 MIME 类型
6. 表单 + 文件混合提交

依赖：python-multipart（解析 multipart/form-data 必需，未装会报 "Form data requires python-multipart"）

关于 /docs 显示：
    FastAPI 新版按 OpenAPI 3.1 把文件字段描述成
    {"type":"string","contentMediaType":"application/octet-stream"}，
    而 Swagger UI 5.x 只认老写法 {"type":"string","format":"binary"}，
    于是文件数组会被渲染成普通字符串数组（出现 "Add string item"，无法选文件）。
    接口功能不受影响，只是文档控件不对。文件末尾有一段补丁修正这个渲染。

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch05_params_upload:app --reload --port 8004

测试（PowerShell）：
    # 表单
    curl.exe -X POST http://127.0.0.1:8004/form -d "username=tom&age=20"
    # 文件
    curl.exe -X POST http://127.0.0.1:8004/upload -F "file=@E:\\fastapi-demo\\fastapi-roadmap.png"
    # 多文件
    curl.exe -X POST http://127.0.0.1:8004/upload-many -F "files=@a.png" -F "files=@b.png"
    # 表单 + 文件
    curl.exe -X POST http://127.0.0.1:8004/upload-with-meta -F "note=hello" -F "file=@a.png"
    # 也可以直接打开 /docs 用 Try it out
"""

from typing import Annotated

from fastapi import Cookie, FastAPI, File, Form, Header, Path, Query, UploadFile

app = FastAPI(title="ch05 参数来源与文件上传", version="1.0.0")

# 上传大小上限（演示用，实际应结合业务定）
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


# ── 1. 四个显式来源 ───────────────────────────────────────────────
# 虽然 FastAPI 能自动推断来源，但显式声明更清晰，也能加校验/描述。
@app.get("/sources/{item_id}")
async def all_sources(
    item_id: Annotated[int, Path(gt=0, description="路径参数")],
    q: Annotated[str | None, Query(max_length=20, description="查询参数")] = None,
    user_agent: Annotated[str | None, Header(description="请求头，下划线转连字符")] = None,
    session_id: Annotated[str | None, Cookie(description="Cookie 值")] = None,
):
    # Header 参数名里的下划线会自动转成连字符：user_agent -> User-Agent
    # （想完全自定义就用 Header(alias="X-Real-Name")）
    return {
        "path": item_id,
        "query": q,
        "header_user_agent": user_agent,
        "cookie_session_id": session_id,
    }


# ── 2. 表单 ───────────────────────────────────────────────────────
# Form() 表示从表单体读取，而不是 query string。
# 表单和 JSON 不能同时出现在一个请求里（Content-Type 不同）。
@app.post("/form")
async def submit_form(
    username: Annotated[str, Form(min_length=2)],
    age: Annotated[int, Form(ge=0, le=150)] = 0,
):
    return {"username": username, "age": age}


# ── 3. 单个文件上传 ───────────────────────────────────────────────
# File() vs UploadFile：
#   bytes  -> File() 读成 bytes，适合小文件（全部进内存）
#   UploadFile -> 有 .filename / .content_type / .file（SpooledTemporaryFile），
#                 大文件不会一次性读进内存，必须用 await file.read()
@app.post("/upload")
async def upload_file(
    file: Annotated[UploadFile, File(description="单个文件")],
):
    # 读取全部内容（注意：大文件应分块读，见下面的循环写法）
    content = await file.read()

    # 手动做大小限制（生产环境建议在 Nginx/网关层也限一次）
    if len(content) > MAX_UPLOAD_BYTES:
        # 这里不抛 HTTPException 是为了保持示例单一职责，ch06 有专门演示
        return {"error": "文件过大", "size": len(content)}

    return {
        "filename": file.filename,        # 客户端提供的文件名（可伪造，不可信）
        "content_type": file.content_type,  # MIME 类型，同样可伪造
        "size": len(content),
    }


# ── 4. 多文件上传 ─────────────────────────────────────────────────
@app.post("/upload-many")
async def upload_many(
    # list[UploadFile] 支持同一个字段名重复传多个文件
    files: Annotated[list[UploadFile], File(description="多个文件")],
):
    result: list[dict[str, object]] = []
    for f in files:
        # 分块读取，避免大文件撑爆内存
        total = 0
        while chunk := await f.read(1024 * 1024):  # 每次 1 MB
            total += len(chunk)
        result.append({"filename": f.filename, "size": total})
        # 用完关闭底层文件句柄
        await f.close()
    return {"files": result}


# ── 5. 表单 + 文件混合 ────────────────────────────────────────────
# 同一个 multipart 请求里既有普通字段又有文件，这是最常见的前端表单场景。
@app.post("/upload-with-meta")
async def upload_with_meta(
    note: Annotated[str, Form(description="文本字段")],
    file: Annotated[UploadFile, File(description="文件字段")],
):
    head = await file.read(64)  # 只读前 64 字节做演示
    return {
        "note": note,
        "filename": file.filename,
        "first_bytes": head[:16].hex(),
    }


# ── 6. 修正 /docs 的文件控件渲染（纯文档层补丁，可整段删除）────────
# 为什么要这一段：
#   OpenAPI 3.1 规范用 contentMediaType 描述二进制，Swagger UI 5.x 仍按
#   3.0 的 format: binary 判断"这是文件选择框"。两者不一致时，数组项就被
#   当成普通字符串，文档里只能点 "Add string item" 手动填，很反直觉。
# 做了什么：生成 openapi 后递归遍历，把 contentMediaType 同时补上 format: binary。
#   只影响 /openapi.json 的展示，不影响任何运行时校验逻辑。
# 不想要它：删掉本段即可，接口照样能收文件，用 curl 验证。
from fastapi.openapi.utils import get_openapi  # noqa: E402


# PEP 695 递归类型别名（Python 3.12+）：描述 OpenAPI schema 这种任意 JSON 结构。
# 比 Any 精确：每层 isinstance 收窄后能拿到确定的类型。
type JsonNode = dict[str, JsonNode] | list[JsonNode] | str | int | float | bool | None


def _add_binary_format(node: JsonNode) -> None:
    """递归给文件字段补上 Swagger UI 认识的 format: binary。"""
    if isinstance(node, dict):
        if node.get("contentMediaType") == "application/octet-stream":
            if "format" not in node:
                node["format"] = "binary"
        for value in node.values():
            _add_binary_format(value)
    elif isinstance(node, list):
        for value in node:
            _add_binary_format(value)


def custom_openapi():
    # 缓存：FastAPI 会反复调用 openapi()，只在首次生成
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    _add_binary_format(schema)
    app.openapi_schema = schema
    return schema


# 覆盖 FastAPI 默认的 openapi 生成方法
app.openapi = custom_openapi  # type: ignore[method-assign]
