import logging
import pathlib
from datetime import datetime
import sys


def setup_logging(
    log_root_folder=None,
    folder_depth=1,
    dir_name="logs",
    log_name="log - ",
    log_suffix="txt",
    use_timestamp=True,
    strftime_format="%d.%m.%y - %H:%M:%S",
    logging_format="%(asctime)s [%(threadName)s] %(name)s:%(funcName)s:%(lineno)d %(levelname)s - %(message)s",
    file_level=logging.DEBUG,
    console_level=logging.INFO,
):
    """
    Set up your logging
    :param log_root_folder: The root of your project
    :param folder_depth: The depth of the submodule in comparison to your project root. A depth of 1 will create the log folder in the submodule folder
    :param dir_name: The directory name of the log folder
    :param log_name: The name prefix of the log
    :param log_suffix: The extension of the log
    :param use_timestamp: Use a timestamp in the log file name?
    :param strftime_format: The strftime format for the log file name
    :param logging_format: The logging format
    :param file_level: The logging level for the file
    :param console_level: The logging level for the console
    :return:
    """
    if log_root_folder is None:
        log_root_folder = pathlib.Path(__file__).absolute()

        for i in range(folder_depth):
            log_root_folder = log_root_folder.parent

    log_formatter = logging.Formatter(logging_format)

    logging_folder = pathlib.Path(f"{pathlib.Path(log_root_folder).absolute()}/{dir_name}")
    logging_folder.mkdir(exist_ok=True, parents=True)

    timestamp = datetime.now().strftime(strftime_format)
    filename = f"{log_name}{timestamp if use_timestamp else ''}.{log_suffix}"

    file_handler = logging.FileHandler(f"{logging_folder}/{filename}")
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(file_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(console_level)

    logging.basicConfig(
        level=file_level,
        encoding="utf-8",
        format=logging_format,
        handlers=[console_handler, file_handler],
    )


def log_traceback():
    logging.getLogger(__name__)
    logging.exception("An exception has occurred:", exc_info=True)
