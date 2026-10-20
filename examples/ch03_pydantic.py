"""
ch03 - 请求体与 Pydantic 模型
对应脑图「三、核心能力」：Pydantic 模型 / Field 字段约束 / 嵌套模型、模型继承 / response_model

知识点：
1. BaseModel 定义请求体，自动校验 + 类型转换
2. Field() 做字段级约束（长度、数值范围、默认值、示例）
3. 嵌套模型（模型里套模型 / 套列表）
4. 模型继承复用字段
5. 请求体 + 路径参数 + 查询参数混合
6. response_model 过滤响应字段（隐藏密码等敏感信息）
7. model_config 补充文档示例
8. 校验失败自动返回 422，detail 里逐字段说明原因

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch03_pydantic:app --reload --port 8002

测试：
    POST /users   {"name":"Tom","age":20,"password":"secret123"}
    POST /users   {"name":"T","age":200}          -> 422，name 太短 + age 越界
    GET  /users/1
    POST /orders  {"order_id":1,"items":[{"sku":"A","price":9.9,"qty":2}]}
"""

from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="ch03 请求体与 Pydantic", version="1.0.0")


# ── 1. 基础模型 ───────────────────────────────────────────────────
# 继承 BaseModel 后，这个类就是一个"带校验的数据结构"。
# FastAPI 看到参数类型是 BaseModel 子类，就知道它要从请求体（body）里读。
class UserIn(BaseModel):
    # Field(...) 里：
    #   第一个位置参数是默认值（... 表示必填）
    #   min_length / max_length / ge / le 都是校验约束
    name: Annotated[str, Field(min_length=2, max_length=20, description="用户名")]
    age: Annotated[int, Field(ge=0, le=150)] = 18  # 有默认值 = 可选
    password: Annotated[str, Field(min_length=6, exclude=True)]  # exclude=True 不参与序列化
    email: str | None = None


# ── 2. 响应模型：过滤敏感字段 ────────────────────────────────────
# 出参单独定义，绝不复用带 password 的入参模型 —— 这是权限安全的底线。
class UserOut(BaseModel):
    name: str
    age: int
    email: str | None = None


# response_model 会：
#   1) 按该模型过滤字段（password 不会出现在响应里）
#   2) 校验返回值，类型不符会抛错（帮你早发现 bug）
#   3) 生成准确的 OpenAPI 文档
@app.post("/users", response_model=UserOut, status_code=201)
async def create_user(user: UserIn):
    # 这里只是演示，没有真正持久化。
    # 实际项目里应该在这里做 hash(user.password) 再存库。
    return user


# ── 3. 嵌套模型 ───────────────────────────────────────────────────
# 模型可以嵌套模型，也可以嵌套"模型列表"，Pydantic 会递归校验。
class Item(BaseModel):
    sku: Annotated[str, Field(pattern=r"^[A-Z]{1,5}$", description="商品编码，大写字母")]
    price: Annotated[float, Field(gt=0)]
    qty: Annotated[int, Field(ge=1, default=1)]


class OrderIn(BaseModel):
    order_id: int
    items: list[Item]  # 嵌套列表：每个元素都要满足 Item 的约束
    remark: str | None = None

    # model_config 只影响文档展示和行为，不做校验。
    # json_schema_extra 会出现在 /docs 的示例里，方便前端调试。
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_id": 1,
                "items": [{"sku": "ABC", "price": 9.9, "qty": 2}],
                "remark": "加急",
            }
        }
    )


@app.post("/orders")
async def create_order(order: OrderIn):
    # order.items 自动是 list[Item]，可以直接访问 .sku / .price
    total = sum(item.price * item.qty for item in order.items)
    return {"order_id": order.order_id, "total": round(total, 2)}


# ── 4. 模型继承 ───────────────────────────────────────────────────
# 子类继承父类字段，再追加/覆盖。适合"创建用一套、更新用另一套"的场景。
class UserBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=20)]
    email: str | None = None


class UserCreate(UserBase):
    password: Annotated[str, Field(min_length=6)]


class UserUpdate(UserBase):
    # 更新时所有字段都变成可选
    name: Annotated[str | None, Field(min_length=2, max_length=20)] = None
    email: str | None = None


@app.put("/users/{user_id}")
async def update_user(user_id: int, user: UserUpdate):
    # exclude_unset=True：只取客户端显式传了的字段，
    # 这样"没传"和"传了 null"就能区分开（PATCH 语义的关键）。
    return {"user_id": user_id, "changed": user.model_dump(exclude_unset=True)}


# ── 5. 请求体 + 路径 + 查询混合 ──────────────────────────────────
# FastAPI 根据类型判断来源：
#   BaseModel 子类 -> body
#   简单类型且名字在路径里 -> path
#   简单类型不在路径里 -> query
@app.post("/users/{user_id}/profile")
async def update_profile(
    user_id: int,          # path
    profile: UserBase,     # body
    notify: bool = False,  # query
):
    return {"user_id": user_id, "profile": profile.model_dump(), "notify": notify}


# ── 6. 单值请求体（不推荐，但要知道）────────────────────────────
# 只有一个简单类型参数又想让它从 body 读，必须显式用 Body()。
from fastapi import Body  # noqa: E402


@app.post("/echo-name")
async def echo_name(name: Annotated[str, Body(embed=True)]):
    # embed=True 让请求体变成 {"name": "Tom"} 而不是裸字符串 "Tom"
    return {"name": name}
