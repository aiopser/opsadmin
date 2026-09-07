import multiprocessing
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RUN_DIR = BASE_DIR / "run"
LOG_DIR = BASE_DIR / "logs" / "server"

RUN_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

bind = "0.0.0.0:8000"  # 绑定 IP 和端口
backlog = 1024  # 监听队列
chdir = str(BASE_DIR)  # gunicorn 切换到的工作目录
timeout = 60  # 超时时间
worker_class = "gthread"  # 适合后台管理 API 的线程 worker
workers = multiprocessing.cpu_count() * 2 + 1  # 进程数
threads = 2  # 每个进程开启的线程数
worker_connections = 2000
pidfile = str(RUN_DIR / "DevOps_server.pid")  # 进程文件
loglevel = "info"  # 错误日志级别
access_log_format = '%(t)s %(p)s %(h)s "%(r)s" %(s)s %(L)s %(b)s %(f)s" "%(a)s"'
accesslog = str(LOG_DIR / "DevOps_server_access.log")  # 访问日志文件
errorlog = str(LOG_DIR / "DevOps_server_error.log")  # 错误日志文件
