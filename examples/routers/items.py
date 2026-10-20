"""
ch04 的子路由：演示如何用 APIRouter 把一个模块的路由拆出去。

APIRouter 的好处：
1. 文件按业务拆分，避免 main.py 变成几千行
2. prefix / tags / dependencies 可以在这层统一声明，子路由不用重复写
3. 子路由可以再被别的 app include，方便复用

注意：这个文件不是独立应用，没有 app 变量，只能被 include_router 挂载。
"""

from fastapi import APIRouter, HTTPException

# prefix 会在所有子路由路径前拼上 "/items"
# tags 会让这些接口在 /docs 里归到同一个分组
router = APIRouter(
    prefix="/items",
    tags=["items（子路由）"],
    responses={404: {"description": "条目不存在"}},  # 统一声明该组可能的响应
)

# 用内存字典模拟存储，仅用于演示，重启即丢失
fake_items_db = {1: {"name": "Foo"}, 2: {"name": "Bar"}}


@router.get("")  # 最终路径 = /api/v1/items
async def list_items():
    return {"items": list(fake_items_db.values())}


@router.get("/{item_id}")  # 最终路径 = /api/v1/items/{item_id}
async def get_item(item_id: int):
    if item_id not in fake_items_db:
        # HTTPException 会被 FastAPI 转成 {"detail": "..."}，
        # 状态码 404 同时影响响应码和文档
        raise HTTPException(status_code=404, detail=f"item {item_id} not found")
    return fake_items_db[item_id]
