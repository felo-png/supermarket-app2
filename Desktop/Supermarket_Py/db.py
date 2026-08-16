import sqlite3

DB_NAME = "pos_database_v2.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")  # تفعيل الـ Foreign Keys
    return conn

def connect_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. جدول المنتجات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                barcode TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                cost REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        ''')

        # 2. جدول الفواتير
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                total REAL NOT NULL,
                profit REAL NOT NULL
            )
        ''')

        # 3. تفاصيل الفواتير (ربط بالباركود)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                product_barcode TEXT,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (product_barcode) REFERENCES products(barcode)
            )
        ''')

        # 4. جدول المشتريات (ربط بالباركود)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_barcode TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                total REAL NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (product_barcode) REFERENCES products(barcode)
            )
        ''')

        # 5. إعدادات النظام / الخزنة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value REAL NOT NULL
            )
        ''')

        # تهيئة الخزنة
        cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES ('vault_balance', 0.0)")

# دالة لتحديث الخزنة
def update_vault_balance(amount):
    with get_connection() as conn:
        conn.execute("UPDATE system_settings SET value = value + ? WHERE key = 'vault_balance'", (amount,))

# دالة للحصول على رصيد الخزنة
def get_vault_balance():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'vault_balance'")
        res = cursor.fetchone()
        return res[0] if res else 0.0

# دالة لتصفير الخزنة
def reset_vault_balance():
    with get_connection() as conn:
        conn.execute("UPDATE system_settings SET value = 0.0 WHERE key = 'vault_balance'")

# دالة إضافة شراء جديد (تنفذ العمليات في Transaction واحدة)
def add_purchase(product_barcode, quantity, price, date_str):
    total_cost = quantity * price
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # إضافة عملية الشراء
        cursor.execute(
            "INSERT INTO purchases (product_barcode, quantity, price, total, date) VALUES (?, ?, ?, ?, ?)",
            (product_barcode, quantity, price, total_cost, date_str)
        )
        
        # تحديث كمية المنتج بالمخزن بناءً على الباركود
        cursor.execute("UPDATE products SET quantity = quantity + ? WHERE barcode = ?", (quantity, product_barcode))
        
        # خصم المبلغ من الخزنة في نفس الـ Transaction
        cursor.execute("UPDATE system_settings SET value = value - ? WHERE key = 'vault_balance'", (total_cost,))

if __name__ == "__main__":
    connect_db()