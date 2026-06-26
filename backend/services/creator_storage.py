import os

from services.auth_service import ADMIN_CREATORS
from services.folder_service import sanitize_folder_name


def creator_subdir(creator: str) -> str:
    creator = (creator or '').strip()
    if not creator or creator in ADMIN_CREATORS:
        return ''
    return sanitize_folder_name(creator)


def creator_storage_dir(root_dir: str, creator: str) -> str:
    subdir = creator_subdir(creator)
    return os.path.join(root_dir, subdir) if subdir else root_dir


def static_url_for_path(path: str, root_dir: str, static_prefix: str) -> str:
    if not path:
        return ''
    try:
        relative_path = os.path.relpath(path, root_dir)
    except ValueError:
        return ''
    if relative_path.startswith('..'):
        return ''
    return f"{static_prefix.rstrip('/')}/{relative_path.replace(os.sep, '/')}"
