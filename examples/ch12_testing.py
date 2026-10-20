"""
ch12 - 测试：pytest + TestClient
对应脑图「四、进阶实战」：TestClient / pytest 测试用例

知识点：
1. TestClient(app)：在进程内调用 ASGI 应用，不占端口、不走网络
2. pytest fixture：复用测试客户端，scope 控制生命周期
3. 断言三件套：状态码 / 响应体 / 响应头
4. 参数化测试：@pytest.mark.parametrize 覆盖多组输入
5. 断言"敏感字段不外泄"—— 安全回归测试
6. 直接运行本文件也能跑（不依赖 pytest），方便快速自检

运行（两种）：
    # 1) 用 pytest（推荐）
    .venv/Scripts/python.exe -m pytest examples/ch12_testing.py -v
    # 2) 直接跑
    .venv/Scripts/python.exe examples/ch12_testing.py

说明：
- 这里复用 ch03 的 app，测试的是真实业务代码，不是另写的假接口
- 如果测试里需要异步（pytest-asyncio），本示例刻意不用，避免额外依赖；
  TestClient 内部已经用 portal 处理了异步事件循环
"""

import pytest
from fastapi.testclient import TestClient

# 被测试的应用：复用 ch03 的请求体/响应模型示例
from examples.ch03_pydantic import app


# ── 1. fixture：整个模块共用一个 client ──────────────────────────
@pytest.fixture(scope="module")
def client():
    # with 语句会触发 startup/shutdown 事件（lifespan）
    with TestClient(app) as c:
        yield c


# ── 2. 正常路径 ───────────────────────────────────────────────────
def test_create_user_ok(client: TestClient):
    resp = client.post(
        "/users",
        json={"name": "Tom", "age": 20, "password": "secret123"},
    )
    # 断言状态码
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Tom"
    # 断言敏感字段被 response_model 过滤掉
    assert "password" not in body


# ── 3. 校验失败路径 ───────────────────────────────────────────────
def test_create_user_invalid(client: TestClient):
    resp = client.post(
        "/users",
        json={"name": "T", "age": 200, "password": "123"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    # detail 是逐字段错误列表，取字段名集合做断言
    fields = {err["loc"][-1] for err in detail}
    assert {"name", "age", "password"} <= fields


# ── 4. 参数化：多组合法输入 ───────────────────────────────────────
@pytest.mark.parametrize(
    "payload,expected_total",
    [
        ({"order_id": 1, "items": [{"sku": "AB", "price": 10, "qty": 2}]}, 20.0),
        ({"order_id": 2, "items": [{"sku": "C", "price": 1.5, "qty": 3}]}, 4.5),
        ({"order_id": 3, "items": []}, 0),
    ],
)
def test_order_total(client: TestClient, payload, expected_total):
    resp = client.post("/orders", json=payload)
    assert resp.status_code == 200
    assert resp.json()["total"] == expected_total


# ── 5. 非法枚举/格式 ──────────────────────────────────────────────
def test_order_bad_sku(client: TestClient):
    # sku 必须是大写字母 1-5 位，这里故意用小写
    resp = client.post(
        "/orders",
        json={"order_id": 9, "items": [{"sku": "ab", "price": 1}]},
    )
    assert resp.status_code == 422


# ── 6. 同步兜底：直接运行本文件自检 ──────────────────────────────
if __name__ == "__main__":
    # 不装 pytest 也能跑：手动调用测试函数
    with TestClient(app) as c:
        test_create_user_ok(c)
        test_create_user_invalid(c)
        test_order_total(
            c, {"order_id": 1, "items": [{"sku": "AB", "price": 10, "qty": 2}]}, 20.0
        )
        test_order_bad_sku(c)
    print("全部断言通过")
