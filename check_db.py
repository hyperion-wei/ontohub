import sqlite3
import os

db_path = '.ontohub.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查现有表结构
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print('现有表结构:')
    for t in tables:
        print(t[0])
        print('---')
    
    conn.close()
else:
    print('数据库文件不存在')
