# 这是一个示例 Python 脚本。

# 按 Shift+F10 执行或将其替换为您的代码。
# 按 双击 Shift 在所有地方搜索类、文件、工具窗口、操作和设置。

from fastapi import FastAPI, Query, Cookie,Form, File, UploadFile,Depends
from datetime import datetime
from fastapi.encoders import jsonable_encoder
import fastapi_cdn_host
from pydantic import BaseModel
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer

fake_db = {}


app = FastAPI(title="我的第一个 API")
fastapi_cdn_host.patch_docs(app)  # 自动测速并替换 CDN

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

# description 和 tax 是可选的（默认值为 None）
class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

class FormData(BaseModel):
    username: str
    password: str
    # 在某些特殊使用情况下（可能并不常见），你可能希望将表单字段限制为仅在 Pydantic 模型中声明过的字段，并禁止任何额外的字段
    model_config = {"extra": "forbid"}

class Items(BaseModel):
    title: str
    timestamp: datetime
    description: str | None = None

def fake_decode_token(token):
    return User(
        username=token + "fakedecoded", email="john@example.com", full_name="John Doe"
    )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    return user

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
# 路径参数
async def read_item(item_id: int) -> dict:
    return {"item_id": item_id}

@app.get("/query")
# 查询参数 不想让某个参数必填，给默认值即可
async def read_query(query: str = "default", age: int = 0):
    return {"query": query, "age": age}

@app.post("/good/")
# post 请求
async def create_item(item: Item):
    return item

"""
GET /tax/
  → 200 {"items":[{"item_id":"Foo"},{"item_id":"Bar"}]}

GET /tax/?q=hello
  → 200 {"items":[...], "q":"hello"}

GET /tax/?q=
  → 200 {"items":[...]}        # 空串是 falsy，不进 if

GET /tax/?q=<51 字符>
  → 422 {"detail":[{"type":"string_too_long", ...}]}
"""
@app.get("/tax/")
# Annotated[类型, 元数据] str | None：类型允许字符串或 None（Python 3.10+ 写法；等价 Optional[str]）
# Query(max_length=50)：FastAPI 的校验元数据 —— 限制 q 最多 50 字符，超过自动返回 422 = None：默认值 None，让 q 变成"可省略"，不传时不报错
async def read_items(q: Annotated[str | None, Query(max_length=50)] = None):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results

@app.get("/test/")
async def read_items(ads_id: Annotated[str | None, Cookie()] = None):
    return {"ads_id": ads_id}

@app.post("/login/")
async def login(data: Annotated[FormData, Form()]):
    return data

@app.post("/files/")
async def create_file(file: Annotated[bytes, File()]):
    return {"file_size": len(file)}


@app.post("/uploadfile/",summary="登录接口",
    description="接口描述",)
async def create_upload_file(file: UploadFile):
    return {"filename": file.filename}


@app.put("/items/{id}")
def update_item(id: str, item: Items):
    # 核心验证代码：将 Pydantic 模型转成 dict，并处理 datetime
    json_compatible_item_data = jsonable_encoder(item)

    # 存入假数据库
    fake_db[id] = json_compatible_item_data

    # 为了验证，我们把存入数据库的数据返回给客户端看看
    return {"id": id, "saved_data": fake_db[id]}

@app.get("/users/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user