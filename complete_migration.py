"""
完成数据库迁移剩余步骤
"""
import pymysql
from core.settings import get_settings

def complete_migration():
    settings = get_settings()

    connection = pymysql.connect(
        host=settings.database.host,
        port=settings.database.port,
        user=settings.database.username,
        password=settings.database.password,
        database=settings.database.database,
        charset='utf8mb4'
    )

    try:
        with connection.cursor() as cursor:
            print("Completing remaining migration steps...")

            # 1. 清空现有数据（因为没有用户关联，存在安全风险）
            sql = "TRUNCATE TABLE conversation_memory"
            cursor.execute(sql)
            print("[OK] Clear existing data")

            # 2. 添加复合索引
            sql = "CREATE INDEX idx_user_session ON conversation_memory (user_id, session_id)"
            cursor.execute(sql)
            print("[OK] Add composite index")

            # 3. 修改字段为 NOT NULL
            sql = "ALTER TABLE conversation_memory MODIFY COLUMN user_id INT NOT NULL COMMENT '用户ID，关联users表'"
            cursor.execute(sql)
            print("[OK] Set user_id to NOT NULL")

        connection.commit()
        print("\n[SUCCESS] Database migration completed!")

        # 验证迁移结果
        with connection.cursor() as cursor:
            cursor.execute("DESCRIBE conversation_memory")
            columns = cursor.fetchall()
            print("\nTable structure:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} {col[2]}")

            cursor.execute("SHOW INDEX FROM conversation_memory")
            indexes = cursor.fetchall()
            print("\nIndexes:")
            for idx in indexes:
                print(f"  - {idx[2]} ({idx[4]})")

            cursor.execute("SELECT COUNT(*) FROM conversation_memory")
            count = cursor.fetchone()[0]
            print(f"\nCurrent record count: {count}")

    except Exception as e:
        connection.rollback()
        print(f"\n[FAILED] Migration error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connection.close()

if __name__ == "__main__":
    complete_migration()
