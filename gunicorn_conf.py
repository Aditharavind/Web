import multiprocessing

workers = max(2, multiprocessing.cpu_count() * 2 + 1)
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 30
keepalive = 2
accesslog = "-"
errorlog = "-"
loglevel = "info"
