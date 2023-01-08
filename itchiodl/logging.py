import logging


class ColoredLogFormatter(logging.Formatter):
    grey = "\x1b[90m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[1;31m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey,
        logging.INFO: None,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red
    }

    def format(self, record):
        formatted = super().format(record)
        color = self.FORMATS.get(record.levelno)
        if color is not None:
            formatted = f"{color}{formatted}{self.reset}"
        return formatted


def configLogging():
    formatter = ColoredLogFormatter(logging.BASIC_FORMAT, None, '%')
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logging.basicConfig(level=logging.DEBUG, handlers=[stream])
