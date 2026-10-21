"""Public messenger links, never webhook URLs."""

import re
from urllib.parse import urlsplit


def group_url(base_url, dialog_id):
    origin = urlsplit(base_url)
    if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password:
        return ''
    if not re.fullmatch(r'chat[1-9][0-9]*', str(dialog_id)):
        return ''
    return f'https://{origin.netloc}/online/?IM_DIALOG={dialog_id}'
