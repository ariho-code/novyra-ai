# build_files.py
import os
import subprocess
import sys

# Make sure Django is importable
sys.path.append(os.path.dirname(__file__))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'novyra_ai.settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'

import django
django.setup()

# Run collectstatic
subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput", "--clear"])
