import os
import site
import sys

# Ensure .venv site-packages is processed as a site directory (processing .pth files)
venv_site = os.path.join(os.path.dirname(__file__), ".venv", "Lib", "site-packages")
if os.path.exists(venv_site):
    site.addsitedir(venv_site)
