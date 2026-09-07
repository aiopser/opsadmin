import ast
import os
from pathlib import Path

import simplejson
import configparser


class ConfigUtil(object):
    """处理 config 配置的工具类"""

    def __init__(self, file=None):
        """
        :param path:
        """
        self.file = file
        self.cf = self.load_init(self.file)

    def load_init(self, file):
        """
        :return: 加载配置文件
        """
        cf = configparser.ConfigParser()
        cf.read(file, encoding="utf-8")
        return cf

    def get_sections(self):
        """
        :return: 获取文件中的所有 sections
        """
        sections = self.cf.sections()
        return sections

    def get_options(self, section):
        """
        :param section: 获取某个 section 对应的键
        :return:
        """
        options = self.cf.options(section)
        return options

    def get_items(self, sections):
        """
        :param sections: 获取某个 section 对应的键值对
        :return:
        """
        items = self.cf.items(sections)
        return items

    def get_value(self, section, key):
        """
        :param sections:
        :param key:
        :return: 获取某个 section 中某个 key 对应的 value
        """
        env_prefix = {
            "devops": "DEVOPS",
            "db.mysql": "DEVOPS_MYSQL",
            "db.redis": "DEVOPS_REDIS",
            "runner": "DEVOPS_RUNNER",
        }.get(section, f"DEVOPS_{section.replace('.', '_').upper()}")
        env_name = f"{env_prefix}_{key.upper()}"
        if env_name in os.environ:
            return os.environ[env_name]
        return self.cf.get(section, key)

    def get_int_val(self, section, key):
        return int(self.get_value(section, key))

    def get_bool_val(self, section, key):
        value = str(self.get_value(section, key)).strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"{section}.{key} must be a boolean")

    def get_dic_val(self, section, key):
        return simplejson.loads(self.get_value(section, key))

    def get_list_val(self, section, key):
        return ast.literal_eval(self.get_value(section, key))

    def get_default(self, key, type="str"):
        match type:
            case "str":
                return self.get_value("devops", key)
            case "int":
                return self.get_int_val("devops", key)
            case "list":
                return self.get_list_val("devops", key)
            case "dict":
                return self.get_dic_val("devops", key)

    def get_mysql(self, key):
        match key:
            case "port":
                return self.get_int_val("db.mysql", key)
            case "options":
                return self.get_dic_val("db.mysql", key)
            case _:
                return self.get_value("db.mysql", key)

    def get_redis(self, key):
        return self.get_value("db.redis", key)

    def get_runner(self, key, default=None):
        env_name = f"DEVOPS_RUNNER_{key.upper()}"
        if env_name in os.environ:
            return os.environ[env_name]
        return self.cf.get("runner", key, fallback=default)

    def set_val(self, section, key, val):
        self.cf.set(section, key, val)
        self.save_cf()

    def save_cf(self):
        with open(self.file, "w") as f:
            self.cf.write(f)

    def get_options_dic(self, section):
        return dict(self.cf.items(section, True))


file = Path(__file__).resolve().parents[1].joinpath("config", "devops.ini")
ConfigDispose = ConfigUtil(file)
