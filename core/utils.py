import contextvars
import re

FIND_CAMEL = re.compile(r'(?<!^)(?=[A-Z])')

url_context = contextvars.ContextVar("url")
