import logging
import os
import platform


string_punctuation = "!#$%&()*+,-.:;<=?@[]_~"


def get_logger(name=""):
    return logging.getLogger("devops.%s" % os.path.basename(name).replace(".py", ""))


def make_dirs(name, mode=0o755, exist_ok=False):
    return os.makedirs(name, mode=mode, exist_ok=exist_ok)


def is_macos():
    return platform.system() == "Darwin"
