# GEO 可发布图片的「图片原件」备份 / 恢复服务
#
# 功能描述：
#   在 GEO 页面中，图片被标记为「可发布」时会被压缩为 _publish.jpg 并移动到「可发布/日期」目录。
#   为了在「取消发布」时能恢复原图（被压缩前的 png / jpg），本服务在压缩时把原图备份到
#   「可发布/_originals/」目录下，取消发布时再从该目录恢复到 GEO 根目录。
#
# 实现逻辑：
#   1. backup_original_to_originals_dir：标记为可发布时，把源原图移动到 _originals 目录；
#      重名时通过 unique_destination_path 自动追加 _1、_2...。
#   2. restore_original_from_originals：取消发布时，根据 publish 文件名推算原图 base，
#      在 _originals 目录查找原图，移动到 GEO 根目录。
#   3. 跨日期移动 publish 图片时不需要操作 _originals（原图位置不随时间组变化）。

import os
import re
import shutil


# 支持的图片扩展名（与 geo.py 中保持一致）
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')

# 解析 publish 文件名中的可选 _N 序号（_1、_2、...）
PUBLISH_INDEX_PATTERN = re.compile(r'^(.*)_(\d+)$')

# 解析 publish 文件名尾部的 _publish 标识
PUBLISH_SUFFIX = '_publish'

# 原图备份目录（相对 GEO 根目录）
ORIGINALS_BACKUP_DIR = '可发布/_originals'


def strip_publish_suffix(publish_filename):
    # 根据 publish 文件名推导「原始文件」的 base 名称（不含扩展名）。
    # 形如 {base}_{N}_publish.jpg 或 {base}_publish.jpg 都会被还原成 {base}。
    base = os.path.splitext(os.path.basename(publish_filename))[0]
    if base.endswith(PUBLISH_SUFFIX):
        base = base[: -len(PUBLISH_SUFFIX)]
    match = PUBLISH_INDEX_PATTERN.match(base)
    if match:
        base = match.group(1)
    return base


def is_publishable_output_filename(filename):
    # 判断文件名是否是「可发布压缩后的」_publish 文件。
    # 例如 xxx_publish.jpg 返回 True，xxx.png 返回 False。
    return os.path.splitext(os.path.basename(filename))[0].endswith(PUBLISH_SUFFIX)


def unique_destination_path(directory, filename):
    # 在目标目录下计算一个不会与已有文件冲突的最终路径。
    # 与 geo.py 中的同名工具逻辑保持一致：若同名则追加 _1、_2...。
    os.makedirs(directory, exist_ok=True)
    base, ext = os.path.splitext(filename)
    candidate = filename
    index = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f'{base}_{index}{ext}'
        index += 1
    return os.path.join(directory, candidate), candidate


def backup_original_to_originals_dir(source_path, geo_dir, source_filename):
    # 把「原图」备份到「可发布/_originals/」目录下，便于取消发布时恢复。
    # 返回 (备份后绝对路径, 备份后文件名)。源与目标相同时只返回路径，不执行移动。
    backup_dir = os.path.join(geo_dir, ORIGINALS_BACKUP_DIR)
    backup_path, final_filename = unique_destination_path(backup_dir, source_filename)
    if os.path.abspath(source_path) == os.path.abspath(backup_path):
        return backup_path, final_filename
    if os.path.exists(source_path):
        shutil.move(source_path, backup_path)
    return backup_path, final_filename


def find_original_in_backup_dir(geo_dir, base_name):
    # 在「可发布/_originals/」备份目录中按 base_name + 图片扩展名查找原图。
    # 找到则返回绝对路径，否则返回 None。
    backup_dir = os.path.join(geo_dir, ORIGINALS_BACKUP_DIR)
    if not os.path.isdir(backup_dir):
        return None
    for ext in IMAGE_EXTENSIONS:
        candidate = os.path.join(backup_dir, base_name + ext)
        if os.path.isfile(candidate):
            return candidate
    return None


def restore_original_from_originals(row, geo_dir):
    # 取消发布时，从「可发布/_originals/」恢复原图到 GEO 根目录。
    # 返回 (恢复后绝对路径, 恢复后文件名)；找不到原图时返回 (None, None)。
    publish_filename = os.path.basename(row['filename'])
    base = strip_publish_suffix(publish_filename)
    if not base:
        return None, None

    original_path = find_original_in_backup_dir(geo_dir, base)
    if not original_path:
        return None, None

    target_path, final_filename = unique_destination_path(geo_dir, os.path.basename(original_path))
    shutil.move(original_path, target_path)
    return target_path, final_filename
