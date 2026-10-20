"""
ch02 - 路径参数与查询参数
对应脑图「二、入门阶段」：路径参数与类型转换 / 查询参数默认值与可选 / Query 高级校验

知识点：
1. 路径参数 {name} 与类型自动转换、转换失败自动 422
2. 路径顺序陷阱：固定路径必须写在通配路径之前
3. Enum 限定取值范围
4. Path() 对路径参数做数值/字符串校验
5. 查询参数：必填 / 可选 / 默认值 / bool 自动转换
6. Query() 做长度、正则、别名、废弃标记
7. Annotated 推荐写法（类型与元数据分离）

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch02_path_query:app --reload --port 8001

测试：
    GET /items/5                       -> {"item_id": 5}
    GET /items/abc                     -> 422（int 转换失败）
    GET /items/me                      -> {"item_id": "the current user"}（固定路径优先）
    GET /models/alexnet                -> 合法枚举
    GET /models/resnet99               -> 422（不在枚举内）
    GET /files/0                       -> 422（Path gt=0 拦截）
    GET /search/?q=fastapi&limit=3     -> 查询参数
    GET /search/?q=ab                  -> 422（min_length=3）
    GET /search/?q_name=xx             -> alias 生效
"""

from enum import Enum
from typing import Annotated

from fastapi import FastAPI, Path, Query

app = FastAPI(title="ch02 路径参数与查询参数", version="1.0.0")


# ── 1. 路径顺序陷阱（先写固定路径）──────────────────────────────
# 路由按注册顺序匹配。如果把 /items/me 写在 /items/{item_id} 之后，
# 请求 /items/me 会先命中通配路由，然后因为 "me" 转不成 int 而报 422。
# 所以固定路径必须放在通配路径前面。
@app.get("/items/me")
async def read_current_user():
    return {"item_id": "the current user"}


# ── 2. 类型转换 ───────────────────────────────────────────────────
# {item_id} 是路径占位符；声明成 int 后，FastAPI 会把字符串 "5" 转成 5，
# 转换失败（如 "abc"）直接返回 422，函数体根本不会执行 —— 这就是"声明式校验"。
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id, "type": type(item_id).__name__}


# ── 3. Enum 限定取值 ──────────────────────────────────────────────
# 继承 str 的 Enum 会被 OpenAPI 描述成 enum，/docs 里直接变成下拉框。
class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    # model_name 已经是枚举成员，比较时可以直接用 ModelName.xxx
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}
    return {"model_name": model_name, "message": "Have some residuals"}


# ── 4. Path() 校验路径参数 ────────────────────────────────────────
# gt=0 表示必须 > 0；le=100 表示 <= 100。
# 这些约束会写进 OpenAPI，前端/文档能直接看到。
@app.get("/files/{file_no}")
async def read_file(
    file_no: Annotated[int, Path(title="文件编号", gt=0, le=100)],
):
    return {"file_no": file_no}


# ── 5. 查询参数基础 ───────────────────────────────────────────────
# 函数参数只要不在路径里，且是简单类型，就自动被当成 query string 参数。
# 有默认值 = 可选；没有默认值 = 必填。
@app.get("/search/")
async def search(
    q: str,                      # 必填：/search/ 不带 q 会 422
    skip: int = 0,               # 可选：默认 0
    limit: int = 10,             # 可选：默认 10
    only_active: bool = False,   # bool 会自动解析 "true"/"1"/"yes" 等
):
    return {"q": q, "skip": skip, "limit": limit, "only_active": only_active}


# ── 6. Query() 高级校验 ──────────────────────────────────────────
# Annotated[类型, Query(...)] = 类型 + 元数据的标准写法（FastAPI 官方推荐）。
# 等价的老写法：q: str | None = Query(default=None, min_length=3)
@app.get("/search/advanced")
async def search_advanced(
    q: Annotated[
        str | None,
        Query(
            alias="q_name",          # URL 里用 q_name，代码里仍叫 q
            min_length=3,
            max_length=50,
            pattern=r"^[a-zA-Z0-9 ]+$",  # 只允许字母数字空格（正则校验）
            description="搜索关键词，3-50 位",
            deprecated=False,            # True 会在文档里标记为"已废弃"
        ),
    ] = None,
    tags: Annotated[list[str], Query(description="可重复传：?tags=a&tags=b")] = [],
):
    # list[str] + Query 支持重复参数：/search/advanced?tags=x&tags=y
    return {"q": q, "tags": tags}


# ── 7. 路径 + 查询混合 ────────────────────────────────────────────
# 同一个函数里可以同时接收路径参数和查询参数，FastAPI 按名字自动区分。
@app.get("/users/{user_id}/orders/{order_id}")
async def read_order(
    user_id: int,
    order_id: int,
    detail: bool = False,
):
    return {"user_id": user_id, "order_id": order_id, "detail": detail}
