"""
ASGI config for AgroTalhoes project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agrotalhoes.settings')

application = get_asgi_application()
