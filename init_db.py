import mysql.connector
from mysql.connector import Error
import streamlit as st
import sys

def get_db_config():
    """获取数据库配置，优先使用 secrets.toml"""
    # 1. 尝试从 Streamlit Secrets 获取 (本地 .streamlit/secrets.toml 或 云端 Secrets)
    if hasattr(st, "secrets") and "mysql" in st.secrets:
        print("Using configuration from secrets.toml / Streamlit Cloud Secrets")
        return {
            'host': st.secrets["mysql"]["host"],
            'port': st.secrets["mysql"].get("port", 4000),
            'user': st.secrets["mysql"]["user"],
            'password': st.secrets["mysql"]["password"],
            # 注意：TiDB Serverless 连接时通常需要指定数据库名，或者连接后再创建
            # 但为了通用性，我们先连接 server
        }
    
    # 2. 本地默认回退
    print("Using local default configuration (localhost)")
    return {
        'host': 'localhost',
        'user': 'root',
        'password': 'Aa2445386326'
    }

def create_database():
    config = get_db_config()
    target_db_name = 'stock_app_db'
    
    # 如果是 secrets 配置，通常 database 字段已经指定了
    if hasattr(st, "secrets") and "mysql" in st.secrets:
        target_db_name = st.secrets["mysql"]["database"]

    try:
        # 连接到 MySQL Server
        # 注意：对于 TiDB Serverless，必须在连接时指定 database，否则可能会报错
        # 如果 database 不存在，TiDB 可能允许连接但不选定库，或者拒绝
        # 我们先尝试直接连接指定库（假设库已存在或用户有权创建）
        # 为了稳妥，先尝试不带 database 连接
        try:
            connection = mysql.connector.connect(**config)
        except Error as err:
            # 如果连接失败，可能是因为 TiDB 强制要求指定 database
            # 尝试把 database 加入配置
            config['database'] = target_db_name
            connection = mysql.connector.connect(**config)

        if connection.is_connected():
            cursor = connection.cursor()
            
            # 尝试创建数据库 (TiDB Serverless 可能限制创建数据库权限，或者已经有一个默认库)
            try:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {target_db_name}")
                print(f"Database '{target_db_name}' created or checked.")
            except Error as e:
                print(f"Warning: Could not create database (might already exist or permission denied): {e}")
            
            # 切换到该数据库
            try:
                connection.database = target_db_name
            except Error as e:
                print(f"Error switching database: {e}")
                return

            # 1. 创建用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Table 'users' created.")
            
            # 2. 创建自选股表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_stocks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(50),
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE KEY unique_stock (user_id, symbol)
                )
            """)
            print("Table 'user_stocks' created.")
            
            # 3. 创建预测记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    stock_name VARCHAR(50),
                    prediction_type ENUM('UP', 'DOWN') NOT NULL,
                    initial_price DECIMAL(10, 2) NOT NULL,
                    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status ENUM('PENDING', 'CORRECT', 'INCORRECT') DEFAULT 'PENDING',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            print("Table 'predictions' created.")

    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection is closed")

if __name__ == "__main__":
    print("Running in CLI mode. Note: st.secrets might not be loaded. Use 'streamlit run init_db.py' to use secrets.toml")
    create_database()

# Streamlit UI execution
if hasattr(st, "runtime") and st.runtime.exists():
    st.title("Database Initialization Tool")
    st.write("This script initializes the database tables.")
    
    if hasattr(st, "secrets") and "mysql" in st.secrets:
        st.info(f"Target Database Host: {st.secrets['mysql']['host']}")
    else:
        st.warning("No secrets found. Will use localhost default if you continue.")

    if st.button("Initialize Database"):
        with st.spinner("Initializing..."):
            # Redirect stdout to streamlit
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                create_database()
            st.text(f.getvalue())
        st.success("Initialization process finished.")
