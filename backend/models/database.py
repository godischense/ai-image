import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, 'storage', 'images.db')

# 确保存储目录存在
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 创建图片表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL DEFAULT '',
            thumbnail TEXT NOT NULL DEFAULT '',
            prompt TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            size TEXT NOT NULL DEFAULT '',
            quality TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            task_id TEXT,
            local_path TEXT,
            thumbnail_path TEXT,
            title TEXT,
            updated_at TEXT,
            parent_id TEXT,
            folder_path TEXT,
            image_type TEXT NOT NULL DEFAULT 'generation',
            aspect_ratio REAL,
            api_source TEXT NOT NULL DEFAULT 't8',
            poster_copy TEXT NOT NULL DEFAULT ''
        )
    ''')

    # 创建任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            image_id TEXT,
            platform TEXT,
            status TEXT NOT NULL,
            fail_reason TEXT DEFAULT '',
            submit_time INTEGER,
            start_time INTEGER,
            finish_time INTEGER,
            progress TEXT DEFAULT '',
            data TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (image_id) REFERENCES images(id)
        )
    ''')

    # 创建应用配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        )
    ''')

    # 创建编辑关系表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS edit_relations (
            id TEXT PRIMARY KEY,
            image_id TEXT NOT NULL,
            parent_id TEXT,
            root_id TEXT NOT NULL,
            depth INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (image_id) REFERENCES images(id),
            FOREIGN KEY (parent_id) REFERENCES images(id),
            FOREIGN KEY (root_id) REFERENCES images(id)
        )
    ''')

    # 创建预备成品图片元数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preparation_items (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            folder_path TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT '',
            score INTEGER NOT NULL DEFAULT 0,
            copy_text TEXT NOT NULL DEFAULT '',
            copy_title TEXT NOT NULL DEFAULT '',
            is_usable INTEGER NOT NULL DEFAULT 0,
            is_publishable INTEGER NOT NULL DEFAULT 0,
            publish_date TEXT NOT NULL DEFAULT '',
            social_copy TEXT NOT NULL DEFAULT '',
            publish_code TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geo_items (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            folder_path TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT '',
            publish_platform TEXT NOT NULL DEFAULT '',
            score INTEGER NOT NULL DEFAULT 0,
            copy_text TEXT NOT NULL DEFAULT '',
            copy_title TEXT NOT NULL DEFAULT '',
            is_usable INTEGER NOT NULL DEFAULT 0,
            is_publishable INTEGER NOT NULL DEFAULT 0,
            publish_date TEXT NOT NULL DEFAULT '',
            social_copy TEXT NOT NULL DEFAULT '',
            publish_code TEXT NOT NULL DEFAULT '',
            poster_copy TEXT NOT NULL DEFAULT '',
            audit_status TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


def migrate_add_edit_fields():
    """
    迁移数据库，添加编辑相关字段

    功能描述：
        为已存在的数据库添加 parent_id 和 folder_path 字段，以及 edit_relations 表

    实现逻辑：
        1. 检查 images 表是否存在 parent_id 字段，不存在则添加
        2. 检查 images 表是否存在 folder_path 字段，不存在则添加
        3. 创建 edit_relations 表（如果不存在）
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 检查并添加 parent_id 字段
        cursor.execute("PRAGMA table_info(images)")
        columns = [row['name'] for row in cursor.fetchall()]

        if 'thumbnail_path' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN thumbnail_path TEXT')
            print("[Database] Added thumbnail_path column to images table")

        if 'parent_id' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN parent_id TEXT')
            print("[Database] Added parent_id column to images table")

        if 'folder_path' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN folder_path TEXT')
            print("[Database] Added folder_path column to images table")

        if 'image_type' not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN image_type TEXT NOT NULL DEFAULT 'generation'")
            print("[Database] Added image_type column to images table")

        if 'aspect_ratio' not in columns:
            cursor.execute('ALTER TABLE images ADD COLUMN aspect_ratio REAL')
            print("[Database] Added aspect_ratio column to images table")

        if 'poster_copy' not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN poster_copy TEXT NOT NULL DEFAULT ''")
            print("[Database] Added poster_copy column to images table")

        # 制作人字段：用于生图/编辑页记录当前图片的制作人归属
        # 不发送到 API 请求，仅作为本地元数据保存
        if 'creator' not in columns:
            cursor.execute("ALTER TABLE images ADD COLUMN creator TEXT NOT NULL DEFAULT ''")
            print("[Database] Added creator column to images table")

        cursor.execute("""
            UPDATE images
            SET image_type = 'generation'
            WHERE image_type IS NULL OR TRIM(image_type) = ''
        """)

        # 创建 edit_relations 表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS edit_relations (
                id TEXT PRIMARY KEY,
                image_id TEXT NOT NULL,
                parent_id TEXT,
                root_id TEXT NOT NULL,
                depth INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (image_id) REFERENCES images(id),
                FOREIGN KEY (parent_id) REFERENCES images(id),
                FOREIGN KEY (root_id) REFERENCES images(id)
            )
        ''')

        # 创建索引以提高查询性能
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_edit_relations_root_id ON edit_relations(root_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_edit_relations_parent_id ON edit_relations(parent_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_edit_relations_image_id ON edit_relations(image_id)
        ''')

        # 检查 tasks 表是否存在 api_source 字段，不存在则添加
        # 功能描述：区分任务来源（openai / fal），TaskProcessor 根据此字段选择不同的查询服务
        cursor.execute("PRAGMA table_info(tasks)")
        tasks_columns = [row['name'] for row in cursor.fetchall()]
        if 'api_source' not in tasks_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN api_source TEXT DEFAULT 't8'")
            print("[Database] Added api_source column to tasks table")

        # 检查 preparation_items 表是否存在 is_usable 字段，不存在则添加
        cursor.execute("PRAGMA table_info(preparation_items)")
        prep_columns = [row['name'] for row in cursor.fetchall()]
        if 'is_usable' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN is_usable INTEGER NOT NULL DEFAULT 0")
            print("[Database] Added is_usable column to preparation_items table")

        if 'copy_title' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN copy_title TEXT NOT NULL DEFAULT ''")
            print("[Database] Added copy_title column to preparation_items table")

        if 'is_publishable' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN is_publishable INTEGER NOT NULL DEFAULT 0")
            print("[Database] Added is_publishable column to preparation_items table")

        if 'social_copy' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN social_copy TEXT NOT NULL DEFAULT ''")
            print("[Database] Added social_copy column to preparation_items table")

        if 'publish_code' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN publish_code TEXT NOT NULL DEFAULT ''")
            print("[Database] Added publish_code column to preparation_items table")

        if 'publish_date' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN publish_date TEXT NOT NULL DEFAULT ''")
            print("[Database] Added publish_date column to preparation_items table")

        if 'folder_path' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN folder_path TEXT NOT NULL DEFAULT ''")
            print("[Database] Added folder_path column to preparation_items table")

        if 'person_in_charge' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN person_in_charge TEXT NOT NULL DEFAULT ''")
            print("[Database] Added person_in_charge column to preparation_items table")

        if 'poster_copy' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN poster_copy TEXT NOT NULL DEFAULT ''")
            print("[Database] Added poster_copy column to preparation_items table")

        # 制作人字段：与 images / geo_items 对称
        if 'creator' not in prep_columns:
            cursor.execute("ALTER TABLE preparation_items ADD COLUMN creator TEXT NOT NULL DEFAULT ''")
            print("[Database] Added creator column to preparation_items table")

        cursor.execute("""
            UPDATE preparation_items
            SET is_publishable = 0
            WHERE is_usable != 1 AND is_publishable = 1
        """)

        cursor.execute("""
            UPDATE preparation_items
            SET publish_date = substr(created_at, 1, 10)
            WHERE is_publishable = 1
              AND (publish_date IS NULL OR TRIM(publish_date) = '')
              AND length(created_at) >= 10
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_preparation_publishable_created_at
            ON preparation_items(is_publishable, created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_preparation_folder_filename
            ON preparation_items(folder_path, filename)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_preparation_publish_date
            ON preparation_items(is_publishable, publish_date)
        """)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geo_items (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                folder_path TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                publish_platform TEXT NOT NULL DEFAULT '',
                score INTEGER NOT NULL DEFAULT 0,
                copy_text TEXT NOT NULL DEFAULT '',
                copy_title TEXT NOT NULL DEFAULT '',
                is_usable INTEGER NOT NULL DEFAULT 0,
                is_publishable INTEGER NOT NULL DEFAULT 0,
                publish_date TEXT NOT NULL DEFAULT '',
                social_copy TEXT NOT NULL DEFAULT '',
                publish_code TEXT NOT NULL DEFAULT '',
                poster_copy TEXT NOT NULL DEFAULT '',
                audit_status TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        cursor.execute("PRAGMA table_info(geo_items)")
        geo_columns = [row['name'] for row in cursor.fetchall()]
        geo_defaults = {
            'folder_path': "TEXT NOT NULL DEFAULT ''",
            'display_name': "TEXT NOT NULL DEFAULT ''",
            'platform': "TEXT NOT NULL DEFAULT ''",
            'publish_platform': "TEXT NOT NULL DEFAULT ''",
            'score': "INTEGER NOT NULL DEFAULT 0",
            'copy_text': "TEXT NOT NULL DEFAULT ''",
            'copy_title': "TEXT NOT NULL DEFAULT ''",
            'is_usable': "INTEGER NOT NULL DEFAULT 0",
            'is_publishable': "INTEGER NOT NULL DEFAULT 0",
            'publish_date': "TEXT NOT NULL DEFAULT ''",
            'social_copy': "TEXT NOT NULL DEFAULT ''",
            'publish_code': "TEXT NOT NULL DEFAULT ''",
            'poster_copy': "TEXT NOT NULL DEFAULT ''",
            'audit_status': "TEXT NOT NULL DEFAULT ''",
            'creator': "TEXT NOT NULL DEFAULT ''"
        }
        for column, definition in geo_defaults.items():
            if column not in geo_columns:
                cursor.execute(f"ALTER TABLE geo_items ADD COLUMN {column} {definition}")
                print(f"[Database] Added {column} column to geo_items table")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_geo_publishable_created_at
            ON geo_items(is_publishable, created_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_geo_folder_filename
            ON geo_items(folder_path, filename)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_geo_publish_date
            ON geo_items(is_publishable, publish_date)
        """)

        conn.commit()
        print("[Database] Migration completed successfully")
    except Exception as e:
        print(f"[Database] Migration failed: {e}")
    finally:
        conn.close()

def migrate_from_json():
    """从旧的 JSON 文件迁移数据到数据库"""
    old_file = os.path.join(os.path.dirname(DB_FILE), 'images.json')
    
    if not os.path.exists(old_file):
        return

    try:
        with open(old_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not data:
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        for item in data:
            cursor.execute('''
                INSERT OR IGNORE INTO images (
                    id, url, thumbnail, prompt, model, size, quality,
                    created_at, task_id, local_path, title, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.get('id'),
                item.get('url', ''),
                item.get('thumbnail', ''),
                item.get('prompt', ''),
                item.get('model', ''),
                item.get('size', ''),
                item.get('quality', ''),
                item.get('created_at', datetime.now().isoformat()),
                item.get('task_id'),
                item.get('local_path'),
                item.get('title'),
                datetime.now().isoformat()
            ))

        conn.commit()
        conn.close()

        print(f"[Database] Migrated {len(data)} images from JSON to database")
        
        # 重命名旧文件作为备份
        backup_file = old_file + '.backup'
        if os.path.exists(backup_file):
            os.remove(backup_file)
        os.rename(old_file, backup_file)
        print(f"[Database] Backed up old JSON file to {backup_file}")

    except Exception as e:
        print(f"[Database] Failed to migrate from JSON: {e}")

# 初始化数据库
init_db()
# 迁移旧数据
migrate_from_json()
# 迁移编辑相关字段
migrate_add_edit_fields()
