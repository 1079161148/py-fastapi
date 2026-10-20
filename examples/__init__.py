# 空文件即可：把 examples 目录标记为 Python 包，
# 这样可以用 `uvicorn examples.ch01_hello:app` 这种"模块路径:变量"的形式启动。
# （不建这个文件，命名空间包通常也能导入，但显式声明更稳妥、IDE 跳转更准）
