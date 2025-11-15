import tbot
from functools import wraps

TC_SKIP = "skipped"
TC_FAIL = "failed"
TC_OKAY = "okay"


def require_cfg(get_flag, msg=None):
    """
    Decorator für tbot-Testcases, der eine Config-Variable prüft.
    msg: Optional eigene Fehlermeldung, sonst generisch.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not get_flag:
                text = msg or f"{func.__name__} not configured"
                tbot.log.message(tbot.log.c(text).yellow)
                return TC_SKIP
            return func(*args, **kwargs)
        return wrapper
    return decorator
