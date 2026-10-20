"""
ch01 - 安装、启动、第一个接口、自动交互式文档
对应脑图「二、入门阶段」：安装与启动 / 第一个项目 / 自动文档

知识点：
1. FastAPI() 创建应用实例（这是 ASGI 应用，不是 Flask 那种 WSGI）
2. @app.get(...) 路由装饰器：HTTP 方法 + 路径 -> 函数
3. async def 与 def 的区别（协程 vs 线程池）
4. 返回 dict 自动序列化为 JSON，状态码默认 200
5. 自动生成 /docs、/redoc、/openapi.json

运行（二选一）：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch01_hello:app --reload --port 8011
    .\\.venv\\Scripts\\fastapi.exe dev examples/ch01_hello.py --port 8011

    注意端口用 8011：8000 留给项目主应用 main.py。
    Windows 下两个进程可以同时监听同一端口（SO_REUSEADDR 语义），
    不报错但请求会随机落到其中一个，是常见的"改了代码没生效"的根源。

访问：
    http://127.0.0.1:8011/            -> {"message": "Hello World"}
    http://127.0.0.1:8011/docs        -> Swagger UI（可点 Try it out 发请求）
    http://127.0.0.1:8011/redoc       -> ReDoc（更易读的文档）
    http://127.0.0.1:8011/openapi.json -> 机器可读的接口描述（OpenAPI 3.1）
"""

from fastapi import FastAPI

# ── 1. 创建应用实例 ────────────────────────────────────────────────
# title/description/version 不是必需的，但会直接显示在 /docs 页面上，
# 相当于给自动文档提供元信息。
app = FastAPI(
    title="ch01 最小可运行示例",
    description="覆盖：应用实例、路由装饰器、同步/异步视图、自动文档",
    version="1.0.0",
)


# ── 2. 异步视图：async def ────────────────────────────────────────
# 只要函数体内有 await（比如 await 数据库、await HTTP 调用），就必须用 async def。
# FastAPI 会在事件循环里直接执行它，不占用线程。
@app.get("/")  # 等价于 @app.api_route("/", methods=["GET"])
async def read_root():
    # 直接返回 dict，FastAPI 会用 JSONResponse 序列化，
    # 并自动加上 Content-Type: application/json
    return {"message": "Hello World"}


# ── 3. 同步视图：def ──────────────────────────────────────────────
# 普通 def 会被 FastAPI 丢进线程池（anyio.to_thread）执行，
# 适合调用阻塞库（requests、同步 DB 驱动）。两种写法都合法。
@app.get("/health")
def health_check():
    # 返回非 dict 也可以：str / list / Pydantic 模型 / Response 对象
    return {"status": "ok"}


# ── 4. 显式指定状态码 ─────────────────────────────────────────────
# 默认 200，这里演示 201 Created 的写法（创建资源的语义）。
# 注意：这里只是演示语法，没有真正写入数据。
@app.post("/echo", status_code=201)
async def echo(payload: dict):
    # payload 是请求体（body），类型 dict 时不做字段校验，原样回显。
    # 需要严格校验就应该用 Pydantic 模型 —— 见 ch03。
    return {"received": payload}


# ── 5. 直接返回 Response 对象 ────────────────────────────────────
# 当需要自定义响应头 / Content-Type 时，绕开自动序列化。
from fastapi.responses import PlainTextResponse  # noqa: E402


@app.get("/text", response_class=PlainTextResponse)
async def read_text():
    # response_class 只影响 /docs 里展示的响应类型和默认序列化方式；
    # 实际也可以直接 return PlainTextResponse("...")。
    return "纯文本响应，不是 JSON"
