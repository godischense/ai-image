from typing import Dict, Optional

from flask import g

LOCAL_USER = {
    'username': '本地用户',
    'creator': '',
    'is_admin': True,
}

ADMIN_CREATORS = {'', '本地用户', '李', '王龙'}


def load_current_user() -> Optional[Dict[str, object]]:
    if hasattr(g, 'current_user'):
        return g.current_user
    g.current_user = dict(LOCAL_USER)
    return g.current_user


def current_user() -> Optional[Dict[str, object]]:
    return load_current_user()


def current_creator() -> str:
    user = current_user()
    return str(user.get('creator', '') if user else '').strip()


def current_user_is_admin() -> bool:
    return True


def scoped_creator(requested_creator: str = '') -> str:
    if current_user_is_admin():
        return (requested_creator or '').strip()
    return current_creator()


def can_access_creator(creator: str) -> bool:
    return True
