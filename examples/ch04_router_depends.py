"""
ch04 - APIRouter 拆分项目 + Depends 依赖注入
对应脑图「三、核心能力」：APIRouter 拆分项目 / prefix 与 tags 分类 / Depends 依赖注入

知识点：
1. APIRouter(prefix, tags) 拆分路由，app.include_router 挂载
2. Depends 函数依赖：多个接口共享同一段准备工作
3. 类依赖：把一组参数打包成一个类
4. 子依赖：依赖里再依赖
5. yield 依赖：在请求结束后执行清理（关连接、释放资源）
6. 全局依赖：dependencies=[...] 作用于整个 app 或整个 router

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch04_router_depends:app --reload --port 8003

测试：
    GET /api/v1/items
    GET /api/v1/items/1
    GET /api/v1/items/99            -> 404
    GET /api/v1/reports?token=abc   -> 校验 token，见 /docs
    GET /docs                       -> 可以看到 "items（子路由）" 分组
"""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query

from .routers import items as items_router

app = FastAPI(title="ch04 APIRouter 与依赖注入", version="1.0.0")


# ── 1. 挂载子路由 ─────────────────────────────────────────────────
# include_router 的 prefix 会再拼一层：/api/v1 + /items + /{item_id}
# 这样同一套 items 路由可以同时挂到 /api/v1 和 /api/v2（版本隔离）。
app.include_router(items_router.router, prefix="/api/v1")


# ── 2. 函数依赖 ───────────────────────────────────────────────────
# 依赖就是一个普通函数，返回值会被注入到接口参数里。
# 收益：分页参数、鉴权、DB 连接等横切逻辑只写一次。
async def common_pagination(
    skip: Annotated[int, Query(ge=0, description="跳过条数")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 10,
) -> dict:
    # 返回值可以是任意类型，这里用一个 dict 打包
    return {"skip": skip, "limit": limit}


@app.get("/api/v1/reports")
async def list_reports(
    # Depends(common_pagination)：FastAPI 会先执行这个依赖，
    # 把它的返回值作为 pagination 传进来。
    pagination: Annotated[dict, Depends(common_pagination)],
):
    return {"pagination": pagination, "data": ["report-a", "report-b"]}


# ── 3. 类依赖 ─────────────────────────────────────────────────────
# 类的 __init__ 参数会被当成接口参数（来源规则和普通函数一致）。
# 适合把"一组相关的 query 参数"打包，避免函数签名越来越长。
class SearchParams:
    def __init__(
        self,
        keyword: str = "",
        order_by: str = "id",
        desc: bool = True,
    ) -> None:
        self.keyword = keyword
        self.order_by = order_by
        self.desc = desc


@app.get("/api/v1/search")
async def search(params: Annotated[SearchParams, Depends(SearchParams)]):
    # params 是 SearchParams 实例，直接访问属性
    return {"keyword": params.keyword, "order_by": params.order_by, "desc": params.desc}


# ── 4. 子依赖 ─────────────────────────────────────────────────────
# 依赖函数自己也可以声明 Depends，形成依赖树。
async def get_token(x_token: Annotated[str, Header(alias="X-Token")] = "") -> str:
    # Header(alias=...)：从请求头读取，alias 是真实的头名（大小写不敏感）
    if not x_token:
        raise HTTPException(status_code=401, detail="缺少 X-Token 请求头")
    return x_token


async def get_current_user(token: Annotated[str, Depends(get_token)]) -> dict:
    # 这里依赖 get_token，FastAPI 会自动按拓扑顺序执行
    # 真实项目应在这里解 JWT / 查库，见 ch08
    return {"username": "demo", "token": token}


@app.get("/api/v1/me")
async def read_me(user: Annotated[dict, Depends(get_current_user)]):
    return user


# ── 5. yield 依赖（资源清理）─────────────────────────────────────
# yield 之前的代码在请求处理前执行，yield 之后的代码在响应发出后执行。
# 无论接口是否抛异常，清理代码都会被调用 —— 等价于 try/finally。
async def get_db_session():
    session = {"connected": True, "id": id(object())}  # 模拟连接
    try:
        yield session  # 注入给接口使用
    finally:
        # 关闭连接 / 回滚未提交事务 / 释放锁
        session["connected"] = False


@app.get("/api/v1/db-ping")
async def db_ping(session: Annotated[dict, Depends(get_db_session)]):
    return {"session": session}


# ── 6. 全局/路由级依赖 ────────────────────────────────────────────
# dependencies=[Depends(...)] 里的依赖不注入参数，只做"前置检查"，
# 常用于统一鉴权、统一限流。下面这个 router 下所有接口都要求 X-Token。
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin（统一鉴权）"],
    dependencies=[Depends(get_token)],
)


@admin_router.get("/stats")
async def admin_stats():
    # 函数签名里不需要写 token，鉴权已在 router 层完成
    return {"users": 128, "orders": 64}


app.include_router(admin_router)
