import os
import pathlib
import shutil


class File(object):
    @staticmethod
    def if_file_exists(abs_path):
        return os.path.isfile(abs_path)

    @staticmethod
    def if_file_endswith(file, pattern):
        return file.endswith(pattern)

    @staticmethod
    def get_file_name(abs_path):
        return os.path.basename(abs_path)

    @staticmethod
    def get_abs_path(abs_path):
        return os.path.dirname(abs_path)

    @staticmethod
    def get_dir_list(dir_path):
        return os.listdir(dir_path)

    @staticmethod
    def get_join_path(*args):
        return os.path.join(*args)

    @staticmethod
    def if_dir_exists(dir_path):
        return os.path.exists(dir_path)

    @staticmethod
    def create_dirs(dir_path):
        os.makedirs(dir_path)

    @staticmethod
    def create_dir(dir_path):
        os.mkdir(dir_path)

    @staticmethod
    def move_file(old_abs_file, abs_path):
        shutil.move(old_abs_file, abs_path)

    @staticmethod
    def rm_file(file_path):
        os.remove(file_path)

    @staticmethod
    def rm_dir(dir_path):
        try:
            os.rmdir(dir_path)
        except OSError:
            pass

    @staticmethod
    def rm_dirs(dir_path):
        shutil.rmtree(dir_path)

    @staticmethod
    def read_file(abs_file):
        file_obj = pathlib.Path(abs_file)
        return file_obj.read_text(encoding="utf-8")

    @staticmethod
    def write_file(abs_file, content):
        file_obj = pathlib.Path(abs_file)
        if not file_obj.is_file():
            file_obj.touch(mode=0o744)
        file_obj.write_text(content, encoding="utf-8")

    @staticmethod
    def rename_dir(dir_name, new_dir_name):
        if not File.if_dir_exists(dir_name):
            return "src_dir: {} not found.".format(dir_name), False

        try:
            return os.rename(dir_name, new_dir_name), True
        except Exception as exc:
            return exc.args, False
