bind = "unix:/home/ofriard/togru/togru.sock"

workers = 4

timeout = 360

# loglevel=debug
accesslog = "/var/log/togru/access.log"
acceslogformat = "%(h)s %(l)s %(u)s %(t)s %(r)s %(s)s %(b)s %(f)s %(a)s"

errorlog = "/var/log/togru/error.log"

