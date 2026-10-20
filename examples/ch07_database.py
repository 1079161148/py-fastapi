"""
ch07 - SQLAlchemy 2.0 数据库集成
对应脑图「三、核心能力」：创建引擎 engine / 定义模型 Base / 依赖注入 Session / 增删改查

知识点：
1. create_engine 创建引擎（连接池由它管理）
2. DeclarativeBase + Mapped/mapped_column（2.0 类型注解风格）
3. sessionmaker + yield 依赖：每个请求一个 Session，用完必关
4. select() 查询 / add+commit 新增 / 属性赋值修改 / delete 删除
5. 内存 SQLite + StaticPool：演示用，不落盘；真实项目用文件/MySQL/PostgreSQL
6. 生产环境建表用 Alembic 迁移，不要用 create_all

运行：
    .\\.venv\\Scripts\\python.exe -m uvicorn examples.ch07_database:app --reload --port 8006

测试：
    POST   /users        {"name":"Tom","email":"tom@example.com"}
    GET    /users
    GET    /users/1
    PATCH  /users/1      {"email":"new@example.com"}
    DELETE /users/1
"""

from collections.abc import Generator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

# ── 1. 引擎 ───────────────────────────────────────────────────────
# "sqlite://" = 内存库。多线程访问同一内存库必须：
#   check_same_thread=False  允许跨线程使用连接
#   StaticPool               所有会话复用同一个连接，否则每个连接一个空库
# 换成 MySQL 大致是：create_engine("mysql+pymysql://user:pwd@host/db")
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,  # True 会打印所有 SQL，调试用
)

# sessionmaker 是"Session 工厂"：每次调用产出一个新 Session
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# ── 2. 声明式模型 ─────────────────────────────────────────────────
class Base(DeclarativeBase):
    """所有 ORM 模型的基类（2.0 写法，替代旧版 declarative_base()）"""


class User(Base):
    __tablename__ = "users"

    # Mapped[int] 声明类型，mapped_column 声明列属性
    # primary_key/autoincrement 自增主键
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # String(20) 限制长度；index=True 建索引（按名字查询会快）
    name: Mapped[str] = mapped_column(String(20), index=True)
    # str | None 自动推断 nullable=True
    email: Mapped[str | None] = mapped_column(String(50), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# 建表（开发期方便；生产用 alembic upgrade head）
Base.metadata.create_all(bind=engine)


# ── 3. Pydantic 出入参模型 ────────────────────────────────────────
# ORM 模型和 API schema 分离：不要把 SQLAlchemy 模型直接当响应模型，
# 否则容易把内部字段（密码哈希、内部备注）泄露出去。
class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=20)
    email: str | None = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str | None
    created_at: datetime

    # from_attributes=True 允许从 ORM 对象属性读取（旧版 orm_mode=True）
    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=20)
    email: str | None = None


# ── 4. Session 依赖 ───────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db          # 注入给接口
        # 注意：commit 放在接口里做，依赖只负责关闭，
        # 这样接口能控制事务边界（多个写操作要么全成功要么全回滚）
    finally:
        db.close()        # 无论异常与否都释放连接，避免连接池耗尽


DbSession = Annotated[Session, Depends(get_db)]


app = FastAPI(title="ch07 SQLAlchemy 2.0", version="1.0.0")


# ── 5. 增删改查 ───────────────────────────────────────────────────
@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: DbSession):
    user = User(name=payload.name, email=payload.email)  # 构造 ORM 对象
    db.add(user)          # 加入会话（还没写库）
    db.commit()           # 提交事务
    db.refresh(user)      # 回读数据库生成的值（id、created_at）
    return user


@app.get("/users", response_model=list[UserOut])
def list_users(db: DbSession, skip: int = 0, limit: int = 10):
    # select(User) 是 2.0 的查询方式；旧写法 db.query(User) 仍可用但不推荐
    stmt = select(User).offset(skip).limit(limit)
    return list(db.scalars(stmt))  # scalars 取出实体对象列表


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DbSession):
    # db.get(主键) 是最快的主键查询方式
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@app.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: DbSession):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # exclude_unset 区分"没传"和"传了 null"，PATCH 语义的关键
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)   # 修改属性后 commit 会自动生成 UPDATE

    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: DbSession):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    # 204 不能有响应体，所以这里什么都不 return
