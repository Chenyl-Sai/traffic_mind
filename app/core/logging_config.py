import logging.config
from app.core.config import settings
import os

os.makedirs(settings.LOG_FILE_PATH_DIR, exist_ok=True)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': settings.LOG_FILE_PATH_DIR + settings.LOG_FILE_NAME,
            'when': 'midnight',
            'interval': 1,
            'backupCount': 7,
        },
    },
    'loggers': {
        '': {
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': False
        },
        'app': {
            'handlers': ['default', 'file'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)  # 记录 SQL 和参数