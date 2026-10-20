"""
ch09 - 中间件与 CORS
对应脑图「四、进阶实战」：CORS 跨域配置 / CORSMiddleware / 请求日志 / 报错日志

知识点：
1. @app.middleware("http")：每个请求前后都能插逻辑（计时、trace_id、日志）
2. call_next(request) 把请求交给后续处理链，返回 Response
3. CORSMiddleware：浏览器跨域（前后端分离必配）
4. GZipMiddleware：响应压缩
5. 中间件执行顺序：后添加的先进入（洋葱模型）
6. 注意：中间件里不要吞异常，否则日志里看不到错误

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch09_middleware:app --reload --port 8008

测试：
    GET  /ping
    GET  /boom                    -> 故意抛错，观察中间件是否记录
    # 观察响应头：X-Process-Time / X-Request-Id
    curl.exe -i http://127.0.0.1:8008/ping
    # 预检请求（浏览器跨域时自动发）
    curl.exe -i -X OPTIONS http://127.0.0.1:8008/ping -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET"
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("ch09")

app = FastAPI(title="ch09 中间件与 CORS", version="1.0.0")


# ── 1. 自定义 HTTP 中间件 ────────────────────────────────────────
# @app.middleware("http") 是 BaseHTTPMiddleware 的语法糖。
# 结构固定：before -> call_next -> after。
@app.middleware("http")
async def timing_and_trace(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]      # 每条日志都能串起来
    start = time.perf_counter()

    # 把信息挂到 request.state，后续接口/依赖里可以读：
    #   def endpoint(request: Request): request.state.request_id
    request.state.request_id = request_id

    try:
        response = await call_next(request)   # 继续走后面的中间件和路由
    except Exception:
        # 记录完整堆栈后必须重新抛出，否则异常被吞，客户端拿到空响应
        logger.exception("[%s] %s %s 未捕获异常", request_id, request.method, request.url.path)
        raise
    finally:
        # 即使抛异常也要打印耗时，方便定位慢请求/失败请求
        cost_ms = (time.perf_counter() - start) * 1000
        logger.info("[%s] %s %s %.2fms", request_id, request.method, request.url.path, cost_ms)

    # 往响应里塞头，方便前端/网关排查
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Process-Time"] = f"{(time.perf_counter() - start) * 1000:.2f}ms"
    return response


# ── 2. CORS 跨域 ─────────────────────────────────────────────────
# 浏览器同源策略：前端 http://localhost:5173 调 http://127.0.0.1:8008 属于跨域，
# 没有这些响应头，浏览器会拦截响应（注意：请求其实到达了服务端，只是前端读不到）。
app.add_middleware(
    CORSMiddleware,
    # 生产环境禁止写 ["*"]（尤其是同时 allow_credentials=True 时，浏览器也不允许）
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,       # 允许带 Cookie / Authorization
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],          # 允许任意请求头（含自定义 X-Token）
    expose_headers=["X-Request-Id", "X-Process-Time"],  # 前端 JS 能读到的响应头
    max_age=600,                  # 预检结果缓存 10 分钟，减少 OPTIONS 请求
)

# ── 3. 响应压缩 ──────────────────────────────────────────────────
# 只对超过 minimum_size 的响应生效，客户端需带 Accept-Encoding: gzip
app.add_middleware(GZipMiddleware, minimum_size=500)


# ── 4. 业务接口 ──────────────────────────────────────────────────
@app.get("/ping")
async def ping(request: Request):
    # 读取中间件塞进 state 的值
    return {"pong": True, "request_id": getattr(request.state, "request_id", None)}


@app.get("/boom")
async def boom():
    # 故意抛未捕获异常，观察日志和 500 响应
    raise RuntimeError("演示用：未捕获异常")
