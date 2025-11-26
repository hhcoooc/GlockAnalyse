import mysql.connector
import bcrypt
import streamlit as st
import pandas as pd
from datetime import datetime

# 配置
# 本地默认配置
LOCAL_DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Aa2445386326',
    'database': 'stock_app_db'
}

def get_connection():
    # 优先尝试从 Streamlit Secrets 读取配置 (用于云端部署)
    if hasattr(st, "secrets") and "mysql" in st.secrets:
        try:
            return mysql.connector.connect(
                host=st.secrets["mysql"]["host"],
                user=st.secrets["mysql"]["user"],
                password=st.secrets["mysql"]["password"],
                database=st.secrets["mysql"]["database"],
                port=st.secrets["mysql"].get("port", 3306)
            )
        except Exception as e:
            st.error(f"云端数据库连接失败: {e}")
            return None
            
    # 本地回退
    return mysql.connector.connect(**LOCAL_DB_CONFIG)

def get_user_stats(user_id):
    """获取用户预测战绩"""
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'CORRECT' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN status = 'INCORRECT' THEN 1 ELSE 0 END) as incorrect
            FROM predictions 
            WHERE user_id = %s AND status != 'PENDING'
        """, (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def register_user(username, password):
    conn = get_connection()
    if not conn: return False, "数据库连接失败"
    cursor = conn.cursor()
    try:
        # Hash password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed))
        conn.commit()
        return True, "注册成功！请登录。"
    except mysql.connector.IntegrityError:
        return False, "用户名已存在。"
    except Exception as e:
        return False, f"注册失败: {e}"
    finally:
        cursor.close()
        conn.close()

def login_user(username, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return True, user
        return False, None
    finally:
        cursor.close()
        conn.close()

def add_to_watchlist(user_id, symbol, name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO user_stocks (user_id, symbol, stock_name) VALUES (%s, %s, %s)", 
                       (user_id, symbol, name))
        conn.commit()
        return True, "已添加到自选股"
    except mysql.connector.IntegrityError:
        return False, "该股票已在自选股中"
    finally:
        cursor.close()
        conn.close()

def remove_from_watchlist(user_id, symbol):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM user_stocks WHERE user_id = %s AND symbol = %s", (user_id, symbol))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_watchlist(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM user_stocks WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def add_prediction(user_id, symbol, name, p_type, current_price):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO predictions (user_id, symbol, stock_name, prediction_type, initial_price)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, symbol, name, p_type, current_price))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
    finally:
        cursor.close()
        conn.close()

def check_predictions(user_id, current_prices):
    """
    检查用户的预测是否正确
    current_prices: dict, {symbol: price}
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    messages = []
    try:
        cursor.execute("SELECT * FROM predictions WHERE user_id = %s AND status = 'PENDING'", (user_id,))
        predictions = cursor.fetchall()
        
        for p in predictions:
            symbol = p['symbol']
            if symbol in current_prices:
                curr_price = current_prices[symbol]
                init_price = float(p['initial_price'])
                p_type = p['prediction_type']
                
                # 简单的验证逻辑：只要当前价格相对于初始价格的方向正确，就算预测正确
                # 实际应用可能需要更复杂的逻辑（如时间限制、幅度限制）
                is_correct = False
                is_wrong = False
                
                if p_type == 'UP':
                    if curr_price > init_price * 1.01: # 涨幅超过1%才算对
                        is_correct = True
                    elif curr_price < init_price * 0.98: # 跌幅超过2%算错
                        is_wrong = True
                elif p_type == 'DOWN':
                    if curr_price < init_price * 0.99:
                        is_correct = True
                    elif curr_price > init_price * 1.02:
                        is_wrong = True
                
                if is_correct:
                    cursor.execute("UPDATE predictions SET status = 'CORRECT' WHERE id = %s", (p['id'],))
                    messages.append(f"🎉 恭喜你！你对 {p['stock_name']} ({symbol}) 的看涨预测正确！该股票涨势正盛！")
                elif is_wrong:
                    cursor.execute("UPDATE predictions SET status = 'INCORRECT' WHERE id = %s", (p['id'],))
                    messages.append(f"💔 很遗憾，你对 {p['stock_name']} ({symbol}) 的预测偏差较大。")
        
        conn.commit()
        return messages
    finally:
        cursor.close()
        conn.close()
