# py-fastapi

FastAPI 学习项目：按学习路线拆成 12 个**最小可运行单元**，每个文件只讲一个主题、都能独立启动，注释覆盖核心语法。

代码基于 Python 3.12 + FastAPI 0.146。

## 环境要求

- Python >= 3.12（本项目用 3.12.8）
- 无需数据库，示例使用内存 SQLite，重启即重置

## 快速开始

```powershell
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活（若报"禁止运行脚本"，先执行下面这行）
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1

# 3. 安装依赖
python -m pip install "fastapi[standard]" sqlalchemy pytest pyjwt fastapi-cdn-host

# 4. 启动主应用
fastapi dev main.py
# 或：python -m uvicorn main:app --reload
```

打开：

| 地址 | 内容 |
|---|---|
| http://127.0.0.1:8000/ | 根接口 |
| http://127.0.0.1:8000/docs | Swagger UI（可 Try it out） |
| http://127.0.0.1:8000/redoc | ReDoc |
| http://127.0.0.1:8000/openapi.json | OpenAPI 3.1 描述 |

## 目录结构

```
fastapi-demo/
├── main.py                     项目主入口，端口 8000
├── pyproject.toml
├── fastapi-roadmap.png         学习路线脑图（示例就是按它拆的）
└── examples/                   12 个最小可运行单元
    ├── ch01_hello.py
    ├── ch02_path_query.py
    ├── ...
    ├── ch12_testing.py
    ├── routers/items.py        ch04 用的 APIRouter 子路由
    ├── static/style.css        ch10 静态资源
    └── templates/index.html    ch10 Jinja2 模板
```

## 示例清单

| 文件 | 主题 | 端口 |
|---|---|---|
| `ch01_hello.py` | 应用实例、路由装饰器、同步/异步视图、自动文档 | 8011 |
| `ch02_path_query.py` | 路径参数、类型转换、Enum、Path/Query 校验 | 8001 |
| `ch03_pydantic.py` | 请求体、Field 约束、嵌套与继承、response_model | 8002 |
| `ch04_router_depends.py` | APIRouter 拆分、prefix/tags、Depends 依赖注入 | 8003 |
| `ch05_params_upload.py` | Path/Query/Header/Cookie、Form、文件上传 | 8004 |
| `ch06_errors.py` | HTTPException、自定义 handler、统一响应结构 | 8005 |
| `ch07_database.py` | SQLAlchemy 2.0、Session 依赖、完整 CRUD | 8006 |
| `ch08_auth.py` | OAuth2 密码流、JWT、密码哈希 | 8007 |
| `ch09_middleware.py` | 中间件、请求日志、CORS、GZip | 8008 |
| `ch10_static_template.py` | StaticFiles 挂载、Jinja2 模板渲染 | 8009 |
| `ch11_background_ws.py` | BackgroundTasks、WebSocket 广播 | 8010 |
| `ch12_testing.py` | pytest + TestClient | 无 |

启动任意一个（以 ch03 为例）：

```powershell
python -m uvicorn examples.ch03_pydantic:app --reload --port 8002
```

跑测试：

```powershell
pytest examples/ch12_testing.py -v
```

端口刻意错开：`8000` 留给主应用 `main.py`，示例用 `8001`–`8011`。

## 建议的学习顺序

1. `ch01` → `ch02`：先建立"路径参数 vs 查询参数"的直觉
2. `ch03`：Pydantic 是 FastAPI 的核心，出参入参必须分开建模
3. `ch04` → `ch06`：依赖复用 + 统一错误结构
4. `ch05` → `ch09`：参数来源与跨域
5. `ch07`：**数据库是分水岭**，理解 Session 为何用 `yield` 依赖
6. `ch08`：认证，理解 token 签发/校验与密码哈希
7. `ch10` → `ch12`：页面渲染、实时通信、自动化测试

每个文件建议这样用：**先跑起来看效果 → 改一处再跑 → 故意传错参数读 422 报错**。422 的 `loc` 字段会告诉你哪个字段、哪个位置错了，比死记 API 有效得多。

## 常见问题

**`/docs` 打开是白屏或一直转圈**

FastAPI 默认的 Swagger 资源托管在 `cdn.jsdelivr.net`，国内网络经常连不上。解决办法是加两行：

```python
import fastapi_cdn_host
fastapi_cdn_host.patch_docs(app)  # 自动测速并切换到可达的 CDN
```

`main.py` 已包含这段。

**改了代码但接口行为没变**

Windows 的 `SO_REUSEADDR` 允许第二个进程绑定已被占用的端口，不报错，但请求会随机落到其中一个。检查：

```powershell
netstat -ano | findstr :8000
```

同一端口出现多个 `LISTENING` 就说明撞了。保持"同一时刻只跑一个服务"，用完 `Ctrl+C`。

**`RuntimeError: To use the fastapi command, please install "fastapi[standard]"`**

终端 `PATH` 里排在最前的 `fastapi.exe` 属于别的虚拟环境。用绝对路径绕开：

```powershell
.\.venv\Scripts\fastapi.exe dev main.py
```

**`where python` 出现两个结果**

`...\Microsoft\WindowsApps\python.exe` 是 Microsoft Store 的应用执行别名占位符（0 字节），不能用。真正的是 `...\Programs\Python\Python312\python.exe`。

## 依赖

| 包 | 版本 | 用途 |
|---|---|---|
| fastapi | 0.146.0 | Web 框架（含 CLI） |
| uvicorn | 0.54.0 | ASGI 服务器 |
| pydantic | 2.14.1 | 数据校验 |
| sqlalchemy | 2.1.5 | ORM（ch07） |
| pyjwt | 2.15.1 | JWT（ch08） |
| pytest | 9.1.1 | 测试（ch12） |
| jinja2 | 3.1.6 | 模板（ch10） |
| python-multipart | 0.0.32 | 表单/文件解析（ch05） |
| fastapi-cdn-host | 0.10.0 | docs 静态资源加速 |

## 许可

MIT
