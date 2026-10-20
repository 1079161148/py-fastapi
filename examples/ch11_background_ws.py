"""
ch11 - 后台任务与 WebSocket
对应脑图「五、生态与扩展」：BackgroundTasks / 内置 WebSocket 双向通信

知识点：
1. BackgroundTasks.add_task：响应先返回，任务在响应发出后执行
2. 后台任务里不要用请求作用域的 Session（已被关闭）—— 要么新开，要么只传纯数据
3. WebSocket 端点用 @app.websocket，不是 @app.get
4. accept() -> receive_text() / send_json() -> close()
5. WebSocketDisconnect：客户端断开时抛出，必须捕获否则日志刷异常
6. ConnectionManager：维护连接集合，实现广播
7. WebSocket 也支持 Depends（query 参数取 token 是常见做法）

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch11_background_ws:app --reload --port 8010

测试：
    # 后台任务
    curl.exe -X POST "http://127.0.0.1:8010/orders?item=book"
    # 立刻返回 {"status":"accepted"}，服务端日志稍后打印"发送邮件"
    # WebSocket：浏览器控制台
    #   const ws = new WebSocket("ws://127.0.0.1:8010/ws/echo");
    #   ws.onmessage = e => console.log(e.data);
    #   ws.onopen = () => ws.send("hello");
    # 广播：开两个标签页连 ws://127.0.0.1:8010/ws/room/1，任一发送，另一个也能收到
"""

import asyncio
import logging

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Query,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
)
from fastapi import status as ws_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ch11")

app = FastAPI(title="ch11 后台任务与 WebSocket", version="1.0.0")


# ── 1. 后台任务 ───────────────────────────────────────────────────
def send_email(to: str, subject: str) -> None:
    """模拟耗时操作：发邮件、写日志、生成报表、调用第三方 API。"""
    # 真实项目这里是阻塞 I/O；BackgroundTasks 会在线程池里跑同步函数，
    # 协程函数则直接在事件循环里执行。
    logger.info("开始给 %s 发送邮件：%s", to, subject)
    # 注意：这里不能阻塞事件循环太久，重活应该丢给 Celery/ARQ
    logger.info("邮件发送完成：%s", to)


async def write_audit_log(order_id: int, item: str) -> None:
    """异步后台任务示例：适合 await 的 I/O。"""
    await asyncio.sleep(0.5)  # 模拟异步写日志/上报
    logger.info("审计日志已写入：order_id=%s item=%s", order_id, item)


@app.post("/orders", status_code=202)
async def create_order(
    background_tasks: BackgroundTasks,   # 直接声明即可，FastAPI 自动注入
    item: str = Query(description="商品名"),
    email: str = "user@example.com",
):
    # 1) 这里应该先落库（同步完成）
    order_id = 1001  # 演示用

    # 2) 把"不需要用户等待"的副作用丢到后台
    #    add_task(函数, *args, **kwargs) —— 参数是位置展开的，不是元组
    background_tasks.add_task(send_email, email, f"订单 {order_id} 已创建")
    background_tasks.add_task(write_audit_log, order_id, item)

    # 3) 立即返回 202 Accepted，客户端不用等邮件发完
    return {"status": "accepted", "order_id": order_id}


# ── 2. 简单 WebSocket echo ───────────────────────────────────────
@app.websocket("/ws/echo")
async def ws_echo(websocket: WebSocket):
    # 必须显式 accept，否则握手失败
    await websocket.accept()
    try:
        while True:
            # 阻塞等待客户端消息（协程挂起，不占线程）
            text = await websocket.receive_text()
            await websocket.send_text(f"服务端收到：{text}")
    except WebSocketDisconnect:
        # 客户端关闭页面/断网时走到这里。不捕获会不断刷异常栈。
        logger.info("客户端断开：%s", websocket.client)


# ── 3. WebSocket + 依赖注入（query 参数鉴权）──────────────────────
# WebSocket 不支持 HTTP 头鉴权（浏览器 WebSocket API 不能自定义头），
# 所以常见做法是把 token 放 query：ws://host/ws/secure?token=xxx
async def ws_verify(token: str = Query(default="")) -> str:
    if token != "demo-token":
        # WebSocket 里不能用 HTTPException（没有 HTTP 响应），
        # 用 WebSocketException，FastAPI 会以 1008 策略违规拒绝握手
        raise WebSocketException(
            code=ws_status.WS_1008_POLICY_VIOLATION, reason="invalid token"
        )
    return token


@app.websocket("/ws/secure")
async def ws_secure(
    websocket: WebSocket,
    token: str = Depends(ws_verify),
):
    await websocket.accept()
    await websocket.send_json({"msg": "鉴权通过", "token": token})
    await websocket.close()


# ── 4. 房间广播 ───────────────────────────────────────────────────
class ConnectionManager:
    """按房间维护连接，实现群聊/推送。"""

    def __init__(self) -> None:
        # room_id -> 连接列表
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)

    def disconnect(self, room_id: str, ws: WebSocket) -> None:
        # 用 remove 而非 pop，避免 KeyError；连接可能已被清理
        if ws in self.rooms.get(room_id, []):
            self.rooms[room_id].remove(ws)
        # 房间空了就删掉，避免字典无限增长（内存泄漏）
        if not self.rooms.get(room_id):
            self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: str, message: str) -> None:
        # 遍历副本：send 过程中可能有客户端断开并从列表移除
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_text(message)
            except Exception:
                # 单个连接发送失败不应影响其他人，直接移除
                self.disconnect(room_id, ws)


manager = ConnectionManager()


@app.websocket("/ws/room/{room_id}")
async def ws_room(websocket: WebSocket, room_id: str):
    await manager.connect(room_id, websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            # 广播给同房间所有人（含自己）
            await manager.broadcast(room_id, f"[{room_id}] {msg}")
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
        await manager.broadcast(room_id, f"有人离开了房间 {room_id}")
