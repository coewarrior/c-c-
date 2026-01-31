import sqlite3
import datetime
import os

DB_FILE = "fund_data.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        sort_order INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS funds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        account TEXT DEFAULT '默认账户',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fund_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        trade_time TEXT NOT NULL,
        amount REAL NOT NULL,
        shares REAL NOT NULL,
        price REAL,
        fee REAL DEFAULT 0,
        note TEXT,
        FOREIGN KEY(fund_id) REFERENCES funds(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS positions (
        fund_id INTEGER PRIMARY KEY,
        shares REAL DEFAULT 0,
        cost_amount REAL DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(fund_id) REFERENCES funds(id)
    )''')
    # migrate old db: add account column if missing
    c.execute("PRAGMA table_info(funds)")
    cols = [row[1] for row in c.fetchall()]
    if "account" not in cols:
        c.execute("ALTER TABLE funds ADD COLUMN account TEXT DEFAULT '默认账户'")
    # seed default accounts
    c.execute("SELECT COUNT(1) FROM accounts")
    if c.fetchone()[0] == 0:
        for name in ["默认账户", "支付宝", "微信"]:
            try:
                c.execute("INSERT INTO accounts (name) VALUES (?)", (name,))
            except Exception:
                pass
    # migrate accounts: add sort_order if missing, and backfill
    c.execute("PRAGMA table_info(accounts)")
    a_cols = [row[1] for row in c.fetchall()]
    if "sort_order" not in a_cols:
        c.execute("ALTER TABLE accounts ADD COLUMN sort_order INTEGER")
    c.execute("UPDATE accounts SET sort_order = id WHERE sort_order IS NULL")
    conn.commit()
    conn.close()

def add_fund(code, name, account="默认账户"):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO funds (code, name, account) VALUES (?, ?, ?)", (code, name, account))
        fund_id = c.lastrowid
        c.execute("INSERT INTO positions (fund_id, shares, cost_amount) VALUES (?, 0, 0)", (fund_id,))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, "基金代码已存在"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_all_funds_with_positions():
    conn = get_connection()
    c = conn.cursor()
    query = '''
        SELECT f.id, f.code, f.name, f.account, p.shares, p.cost_amount 
        FROM funds f 
        LEFT JOIN positions p ON f.id = p.fund_id
    '''
    c.execute(query)
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_trade(fund_id, trade_type, date_str, amount, shares, price, fee, note):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO trades (fund_id, type, trade_time, amount, shares, price, fee, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (fund_id, trade_type, date_str, amount, shares, price, fee, note))
    conn.commit()
    conn.close()

def update_position(fund_id, shares, cost_amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE positions 
        SET shares = ?, cost_amount = ?, updated_at = CURRENT_TIMESTAMP
        WHERE fund_id = ?
    ''', (shares, cost_amount, fund_id))
    conn.commit()
    conn.close()

def get_trades_by_fund(fund_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE fund_id = ? ORDER BY trade_time ASC", (fund_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_accounts():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM accounts ORDER BY sort_order ASC, id ASC")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

def add_account(name):
    if not name:
        return False, "名称不能为空"
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM accounts")
        next_order = c.fetchone()[0]
        c.execute("INSERT INTO accounts (name, sort_order) VALUES (?, ?)", (name, next_order))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, "仓位已存在"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_account(name):
    if not name:
        return False, "名称不能为空"
    if name == "默认账户":
        return False, "默认账户不能删除"
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(1) FROM funds WHERE account = ?", (name,))
        if c.fetchone()[0] > 0:
            return False, "该仓位下已有基金，请先删除或迁移基金"
        c.execute("DELETE FROM accounts WHERE name = ?", (name,))
        conn.commit()
        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def rename_account(old_name, new_name):
    if not new_name:
        return False, "名称不能为空"
    if old_name == "默认账户":
        return False, "默认账户不能重命名"
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(1) FROM accounts WHERE name = ?", (new_name,))
        if c.fetchone()[0] > 0:
            return False, "仓位名称已存在"
        c.execute("UPDATE accounts SET name = ? WHERE name = ?", (new_name, old_name))
        c.execute("UPDATE funds SET account = ? WHERE account = ?", (new_name, old_name))
        conn.commit()
        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def set_accounts_order(names):
    try:
        conn = get_connection()
        c = conn.cursor()
        for idx, name in enumerate(names, start=1):
            c.execute("UPDATE accounts SET sort_order = ? WHERE name = ?", (idx, name))
        conn.commit()
        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()
def get_fund_with_position(fund_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT f.id, f.code, f.name, p.shares, p.cost_amount
        FROM funds f
        LEFT JOIN positions p ON f.id = p.fund_id
        WHERE f.id = ?
    ''', (fund_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_trade_shares(trade_id, shares, price):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE trades
        SET shares = ?, price = ?
        WHERE id = ?
    ''', (shares, price, trade_id))
    conn.commit()
    conn.close()

def delete_fund(fund_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM trades WHERE fund_id = ?", (fund_id,))
        c.execute("DELETE FROM positions WHERE fund_id = ?", (fund_id,))
        c.execute("DELETE FROM funds WHERE id = ?", (fund_id,))
        conn.commit()
        return True, "Success"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
