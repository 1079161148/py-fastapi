"""
ch10 - 静态文件挂载 + Jinja2 模板渲染
对应脑图「四、进阶实战」：StaticFiles 挂载 / 模板 Jinja2 + HTMX（这里演示纯 Jinja2）

知识点：
1. app.mount("/static", StaticFiles(directory=...), name="static") 挂载目录
2. Jinja2Templates(directory=...) 初始化模板引擎
3. TemplateResponse 渲染 HTML（新版推荐传 request=）
4. 模板里用 {{ }} 取值、{% for %} 循环、{% else %} 兜底
5. 表单 POST 后返回页面（传统服务端渲染，非前后端分离）
6. 挂载顺序：mount 在路由之后也行，但不能和已有路径前缀冲突

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch10_static_template:app --reload --port 8009

测试：
    浏览器打开 http://127.0.0.1:8009/
    http://127.0.0.1:8009/static/style.css   -> 静态文件
    页面里填用户名提交，观察表单 POST
"""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="ch10 静态文件与模板", version="1.0.0")

# ── 1. 路径基准 ───────────────────────────────────────────────────
# __file__ 是当前 py 文件路径，取 parent 得到 examples/ 目录。
# 用绝对路径，避免"从哪个目录启动服务"影响资源查找。
BASE_DIR = Path(__file__).resolve().parent

# ── 2. 挂载静态目录 ───────────────────────────────────────────────
# 第一个参数是 URL 前缀，第二个是磁盘目录。
# 访问 /static/style.css 就会读到 examples/static/style.css
# name 用于 url_for('static', path='style.css') 反向生成 URL
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# ── 3. 模板引擎 ───────────────────────────────────────────────────
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# 模拟数据；真实项目从数据库查
FAKE_PRODUCTS = [
    {"name": "机械键盘", "price": 399},
    {"name": "显示器", "price": 1299},
]


# ── 4. 渲染页面 ───────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 新版签名：request 作为关键字参数单独传（旧版是第一个位置参数）
    # 不传 request 会导致模板里的 url_for 等能力不可用
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "商品列表",
            "items": FAKE_PRODUCTS,
        },
    )


@app.post("/form-page", response_class=HTMLResponse)
async def form_page(
    request: Request,
    username: Annotated[str, Form(min_length=1)],
):
    # 表单提交后仍然返回 HTML（不是 JSON），这是传统 MVC 风格
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": f"你好，{username}",
            "items": FAKE_PRODUCTS,
        },
    )


# ── 5. 同一个 app 同时提供 HTML 和 JSON ──────────────────────────
# 前后端分离项目里常见的混合形态：页面走模板，数据走 JSON API。
@app.get("/api/products")
async def api_products():
    return {"items": FAKE_PRODUCTS}
