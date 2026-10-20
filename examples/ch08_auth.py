"""
ch08 - 认证与安全：OAuth2 密码流 + JWT + 密码哈希
对应脑图「三、核心能力」：OAuth2 密码流 / JWT / OAuth2PasswordBearer 与 Security / 密码哈希

知识点：
1. OAuth2PasswordRequestForm：标准表单登录（username + password）
2. OAuth2PasswordBearer：从 Authorization: Bearer <token> 取 token
3. JWT 签发与校验（PyJWT），含 exp 过期时间
4. 密码哈希：pbkdf2_hmac（标准库，无第三方依赖）+ 随机盐 + 恒定时间比较
5. get_current_user 依赖：把 token 换成用户对象，保护任意接口
6. /docs 里的 Authorize 按钮会自动出现（因为声明了 OAuth2 scheme）

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch08_auth:app --reload --port 8007

测试：
    1) 登录拿 token
       curl.exe -X POST http://127.0.0.1:8007/token -d "username=alice&password=secret123"
    2) 带 token 访问受保护接口
       curl.exe http://127.0.0.1:8007/users/me -H "Authorization: Bearer <上一步的access_token>"
    3) 不带 token -> 401
    或者直接打开 /docs，点右上角 Authorize，输入 alice / secret123

安全注意（示例刻意简化）：
- SECRET_KEY 从环境变量读；生产必须设置强随机值，绝不能硬编码提交到仓库
- 示例用内存 dict 存用户；真实项目存数据库，并且密码永不明文
- access_token 有效期 30 分钟；生产应配 refresh token
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt  # PyJWT：pip install pyjwt（注意不是 pip install jwt，那是另一个包）
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

# ── 1. 配置 ───────────────────────────────────────────────────────
# 生产环境用环境变量注入：$env:SECRET_KEY="..."  或 .env + pydantic-settings
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(title="ch08 OAuth2 + JWT", version="1.0.0")


# ── 2. 密码哈希（标准库实现）──────────────────────────────────────
# 格式：pbkdf2_sha256$迭代次数$盐$摘要
# 为什么不直接存 sha256？因为无盐哈希可被彩虹表/GPU 暴力破解。
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)          # 每个用户独立随机盐
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _, iterations, salt_hex, dk_hex = hashed.split("$")
    except ValueError:
        return False                         # 格式不对直接失败，不抛异常
    dk = hashlib.pbkdf2_hmac(
        "sha256", plain.encode(), bytes.fromhex(salt_hex), int(iterations)
    )
    # hmac.compare_digest 是恒定时间比较，避免通过响应时间猜密码（时序攻击）
    return hmac.compare_digest(dk.hex(), dk_hex)


# ── 3. 模拟用户库 ─────────────────────────────────────────────────
# 真实项目：user 表 + 唯一索引 + 只存 password_hash
fake_users_db: dict[str, dict] = {
    "alice": {
        "username": "alice",
        "full_name": "Alice Wang",
        "email": "alice@example.com",
        "hashed_password": hash_password("secret123"),
        "disabled": False,
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str          # 固定 "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None   # subject，通常放 username 或 user id


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool = False


# ── 4. tokenUrl 指向登录接口 ─────────────────────────────────────
# 它只用于生成 OpenAPI 的授权配置和 /docs 的 Authorize 按钮，
# 本身不会发请求、也不校验任何东西。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ── 5. JWT 签发与校验 ─────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # exp 必须是 UTC 时间戳；PyJWT 会自动校验它，过期抛 ExpiredSignatureError
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    # 统一的 401 响应，headers 里带 WWW-Authenticate 是 OAuth2 规范要求
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="凭证无效",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exc
    except jwt.ExpiredSignatureError:
        # token 过期：单独提示，方便前端触发刷新逻辑
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        # 签名不对 / 格式错 / 算法被篡改
        raise credentials_exc

    user = fake_users_db.get(username)
    if user is None:
        raise credentials_exc
    return User(**{k: v for k, v in user.items() if k != "hashed_password"})


# ── 6. 登录接口 ───────────────────────────────────────────────────
@app.post("/token", response_model=Token)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    # OAuth2PasswordRequestForm 从表单读 username/password（不是 JSON！）
    # 额外字段：grant_type / scope / client_id / client_secret
    user = fake_users_db.get(form.username)
    # 注意：用户不存在和密码错误返回同样的信息，避免枚举用户名
    if user is None or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user["disabled"]:
        raise HTTPException(status_code=400, detail="账号已禁用")

    token = create_access_token({"sub": user["username"]})
    return Token(access_token=token, token_type="bearer")


# ── 7. 受保护接口 ─────────────────────────────────────────────────
# 只要依赖 get_current_user，这个接口就必须带合法 Bearer token
@app.get("/users/me", response_model=User)
async def read_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


# 依赖同样可以用于 router 级：APIRouter(dependencies=[Depends(get_current_user)])
@app.get("/secret")
async def read_secret(_: Annotated[User, Depends(get_current_user)]):
    return {"message": "只有带合法 token 才能看到这条数据"}
