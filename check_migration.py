"""
检查数据库迁移状态
"""
import pymysql
from core.settings import get_settings

def check_migration():
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
            # 检查表结构
            cursor.execute("DESCRIBE conversation_memory")
            columns = cursor.fetchall()
            print("Table structure:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} {col[2] if col[2] == 'NO' else 'NULL'}")
            
            # 检查索引
            cursor.execute("SHOW INDEX FROM conversation_memory")
            indexes = cursor.fetchall()
            print("\nIndexes:")
            for idx in indexes:
                print(f"  - {idx[2]} ({idx[4]})")
            
            # 检查记录数
            cursor.execute("SELECT COUNT(*) FROM conversation_memory")
            count = cursor.fetchone()[0]
            print(f"\nRecord count: {count}")
            
            # 检查是否有 user_id 字段且允许 NULL
            has_user_id = any(col[0] == 'user_id' for col in columns)
            print(f"\nHas user_id field: {has_user_id}")
            
            if has_user_id:
                user_id_col = next(col for col in columns if col[0] == 'user_id')
                print(f"user_id nullable: {user_id_col[2] == 'YES'}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    check_migration()
