"""
ch06 - 错误处理与统一响应结构
对应脑图「三、核心能力」：HTTPException / 自定义 exception_handler / JSON 结构一致

知识点：
1. HTTPException：主动抛业务错误，FastAPI 自动转 {"detail": ...}
2. 自定义异常类 + @app.exception_handler：业务异常与 HTTP 解耦
3. RequestValidationError：接管 422 校验错误，统一成自己的格式
4. StarletteHTTPException：接管 404 等框架层错误
5. 异常处理器里可以访问 request（打日志、返回 trace_id）

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch06_errors:app --reload --port 8005

测试：
    GET /items/1                -> 正常
    GET /items/99               -> 404 {"code": 40400, "message": "..."}
    GET /items/abc              -> 422 {"code": 42200, "errors": [...]}
    GET /balance?amount=9999    -> 402 {"code": 40200, ...}（自定义业务异常）
    GET /no-such-path           -> 404（全局兜底格式）
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(title="ch06 错误处理", version="1.0.0")

fake_items_db = {1: {"name": "Foo"}}


# ── 1. HTTPException ─────────────────────────────────────────────
@app.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id not in fake_items_db:
        # 参数说明：
        #   status_code: 必须是 4xx/5xx
        #   detail: 会放进 {"detail": ...}，可以是 str / dict / list
        #   headers: 可选，附加响应头（如 401 时的 WWW-Authenticate）
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"item {item_id} 不存在",
            headers={"X-Error-Source": "get_item"},
        )
    return fake_items_db[item_id]


# ── 2. 自定义业务异常 ─────────────────────────────────────────────
# 业务代码只抛 AppError，不关心 HTTP；由处理器统一翻译成响应。
# 好处：service 层不依赖 FastAPI，可单独测试。
class AppError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    # 统一响应结构：{code, message, path}
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "path": request.url.path,
        },
    )


@app.get("/balance")
async def check_balance(amount: int = 0):
    balance = 100
    if amount > balance:
        # 抛业务异常，被上面的 handler 捕获
        raise AppError(code=40200, message="余额不足", http_status=402)
    return {"balance": balance, "amount": amount}


# ── 3. 接管 422 校验错误 ──────────────────────────────────────────
# 默认 422 的 detail 是一个很长的数组，前端解析麻烦。
# 这里改成固定结构，并把字段路径压平。
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        errors.append(
            {
                # loc 形如 ("path", "item_id") / ("body", "name") / ("query", "q")
                "field": ".".join(str(x) for x in e["loc"]),
                "message": e["msg"],
                "type": e["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={"code": 42200, "message": "参数校验失败", "errors": errors},
    )


# ── 4. 接管框架层 HTTP 错误（404/405 等）────────────────────────
# 注意：这里用的是 Starlette 的 HTTPException，
# FastAPI 的 HTTPException 是它的子类，所以上面 /items/99 抛的 404 也会走这里。
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code * 100,
            "message": exc.detail,
            "path": request.url.path,
        },
    )


# ── 5. 未捕获异常兜底 ─────────────────────────────────────────────
# 注意：Exception 处理器在开发模式下可能被 uvicorn 的调试页覆盖。
# 生产环境务必不要返回堆栈信息给客户端。
@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    # 真实项目：这里 should 记日志 + 上报 Sentry，附带 trace_id
    return JSONResponse(
        status_code=500,
        content={"code": 50000, "message": "服务器内部错误"},
    )
