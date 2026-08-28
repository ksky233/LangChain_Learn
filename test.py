import psycopg
import os
from dotenv import load_dotenv
load_dotenv(override=True)

DB_URL = os.getenv("DATABASE_URL")
# 连接数据库
conn = psycopg.connect(DB_URL)   # 这一行会报真正的错误
