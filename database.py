import os
import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", ""),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", ""),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        connection_timeout=10,
    )


def get_user_by_telegram_id(telegram_id: int):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, telegram_id, name, phone, created_at FROM users WHERE telegram_id = %s",
            (telegram_id,),
        )
        return cur.fetchone()
    except Exception as exc:
        print(f"Database error while fetching user: {exc}")
        return None
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def create_user(telegram_id: int, name: str, phone: str) -> None:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (telegram_id, name, phone) VALUES (%s, %s, %s)",
            (telegram_id, name, phone),
        )
        conn.commit()
    except Exception as exc:
        print(f"Database error while creating user: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def create_video(title: str, youtube_link: str) -> None:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO videos (title, youtube_link) VALUES (%s, %s)",
            (title, youtube_link),
        )
        conn.commit()
    except Exception as exc:
        print(f"Database error while creating video: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def get_all_videos():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, youtube_link, created_at FROM videos ORDER BY id")
        return cur.fetchall()
    except Exception as exc:
        print(f"Database error while fetching videos: {exc}")
        return []
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def get_video_by_title(title: str):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, youtube_link, created_at FROM videos WHERE title = %s",
            (title,),
        )
        return cur.fetchone()
    except Exception as exc:
        print(f"Database error while fetching video: {exc}")
        return None
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def get_all_users():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, phone, telegram_id FROM users ORDER BY id")
        return cur.fetchall()
    except Exception as exc:
        print(f"Database error while fetching users: {exc}")
        return []
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def delete_user_by_telegram_id(telegram_id: int) -> None:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE telegram_id = %s", (telegram_id,))
        conn.commit()
    except Exception as exc:
        print(f"Database error while deleting user: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def get_all_videos_with_id():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, youtube_link FROM videos ORDER BY id")
        return cur.fetchall()
    except Exception as exc:
        print(f"Database error while fetching videos: {exc}")
        return []
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def delete_video_by_id(video_id: int) -> None:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))
        conn.commit()
    except Exception as exc:
        print(f"Database error while deleting video: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def create_tables() -> None:
    create_users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(20) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_videos_table = """
    CREATE TABLE IF NOT EXISTS videos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        youtube_link TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_admins_table = """
    CREATE TABLE IF NOT EXISTS admins (
        id INT AUTO_INCREMENT PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(create_users_table)
        cur.execute(create_videos_table)
        cur.execute(create_admins_table)
        conn.commit()
    except Exception as exc:
        print(f"Database error while creating tables: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def add_admin(telegram_id: int) -> None:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admins (telegram_id) VALUES (%s) "
            "ON DUPLICATE KEY UPDATE telegram_id = telegram_id",
            (telegram_id,),
        )
        conn.commit()
    except Exception as exc:
        print(f"Database error while adding admin: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def is_admin(telegram_id: int) -> bool:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM admins WHERE telegram_id = %s", (telegram_id,))
        result = cur.fetchone()
        return result is not None
    except Exception as exc:
        print(f"Database error while checking admin: {exc}")
        return False
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def get_all_admins():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, telegram_id, created_at FROM admins ORDER BY id")
        return cur.fetchall()
    except Exception as exc:
        print(f"Database error while fetching admins: {exc}")
        return []
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


def init_db() -> None:
    create_tables()