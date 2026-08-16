import customtkinter as ctk
from PIL import Image
from tkinter import messagebox
import os
import sqlite3
from datetime import datetime

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

DB_NAME = "pos_database_v2.db"

# ====================================================
# 🗄️ إعداد وتأسيس قاعدة البيانات
# ====================================================
def init_db():
    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                sec_question TEXT NOT NULL,
                sec_answer TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_blocked INTEGER DEFAULT 0
            )
        ''')

        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if "role" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        if "is_blocked" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")

        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, sec_question, sec_answer, role, is_blocked) VALUES ('admin', 'admin123', 'admin', 'admin', 'admin', 0)")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                cost_price REAL DEFAULT 0.0,
                price REAL NOT NULL,
                stock INTEGER NOT NULL
            )
        ''')

        cursor.execute("PRAGMA table_info(products)")
        prod_cols = [c[1] for c in cursor.fetchall()]
        if "cost_price" not in prod_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN cost_price REAL DEFAULT 0.0")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_num TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                total_price REAL NOT NULL,
                date_time TEXT NOT NULL,
                is_reset INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute("PRAGMA table_info(sales)")
        sales_cols = [c[1] for c in cursor.fetchall()]
        if "is_reset" not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN is_reset INTEGER DEFAULT 0")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_num TEXT NOT NULL,
                item_name TEXT NOT NULL,
                returned_qty INTEGER NOT NULL,
                refund_amount REAL NOT NULL,
                return_date TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                unit_cost REAL NOT NULL,
                quantity INTEGER NOT NULL,
                total_cost REAL NOT NULL,
                purchase_date TEXT NOT NULL
            )
        ''')

        sales_cols = [c[1] for c in cursor.execute("PRAGMA table_info(sales)").fetchall()]
        if "cost_price" not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN cost_price REAL DEFAULT 0.0")

        # حفظ تكلفة الشراء للبيانات القديمة قدر الإمكان.
        cursor.execute("""
            UPDATE sales
            SET cost_price = COALESCE(
                (SELECT cost_price FROM products WHERE products.name = sales.item_name), 0
            )
            WHERE COALESCE(cost_price, 0) = 0
        """)

        cursor.execute("SELECT value FROM system_state WHERE key = 'monthly_start'")
        if cursor.fetchone() is None:
            month_start = datetime.now().strftime("%Y-%m-01 00:00:00")
            cursor.execute("INSERT INTO system_state (key, value) VALUES ('monthly_start', ?)", (month_start,))

        cursor.execute("SELECT value FROM system_state WHERE key = 'treasury_balance'")
        if cursor.fetchone() is None:
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT COALESCE(SUM(total_price), 0) FROM sales WHERE is_reset = 1 OR date(date_time) != date(?)", (today,))
            initial_treasury = cursor.fetchone()[0] or 0.0
            cursor.execute("INSERT INTO system_state (key, value) VALUES ('treasury_balance', ?)", (str(initial_treasury),))

init_db()


class SupermarketPOSApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Supermarket POS")
        
        window_width = 1180
        window_height = 720
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        self.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        
        self.configure(fg_color="#CFE2FE")

        self.current_user = None
        self.current_user_role = "user"
        self.selected_product_id = None
        self.cart = []

        self.show_login_screen()

    # ====================================================
    # 🔑 1. شاشات الحسابات وتسجيل الدخول والخروج
    # ====================================================
    def handle_logout(self):
        if messagebox.askyesno("تسجيل الخروج", "هل أنت متأكد من تسجيل الخروج؟"):
            self.current_user = None
            self.current_user_role = "user"
            self.cart = []
            self.show_login_screen()

    def show_login_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.unbind('<Return>')
        self.geometry("950x640")
        
        card = ctk.CTkFrame(self, width=380, height=540, corner_radius=25, fg_color="#FFFFFF", border_width=1, border_color="#E5E7EB")
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        self.load_logo(card, image_name="images.jpeg")

        ctk.CTkLabel(card, text="Supermarket POS", font=ctk.CTkFont(family="Helvetica", size=18, weight="bold"), text_color="#111827").pack(pady=(0, 8))
        ctk.CTkLabel(card, text="أهلاً بك - تسجيل الدخول", font=ctk.CTkFont(family="Helvetica", size=11, weight="bold"), text_color="#374151").pack(anchor="e", padx=45, pady=(0, 4))

        u_box = ctk.CTkFrame(card, fg_color="transparent")
        u_box.pack(fill="x", padx=45, pady=(0, 6))
        ctk.CTkLabel(u_box, text="— Username —", font=ctk.CTkFont(size=9), text_color="#9CA3AF").pack(anchor="center", pady=(0, 1))
        self.user_ent = ctk.CTkEntry(u_box, placeholder_text="اسم المستخدم", height=38, corner_radius=8, justify="right")
        self.user_ent.pack(fill="x")

        p_box = ctk.CTkFrame(card, fg_color="transparent")
        p_box.pack(fill="x", padx=45, pady=(0, 4))
        ctk.CTkLabel(p_box, text="— Password —", font=ctk.CTkFont(size=9), text_color="#9CA3AF").pack(anchor="center", pady=(0, 1))
        self.pass_ent = ctk.CTkEntry(p_box, placeholder_text="كلمة المرور", show="•", height=38, corner_radius=8, justify="right")
        self.pass_ent.pack(fill="x")

        self.bind('<Return>', lambda event: self.handle_login())

        ctk.CTkButton(card, text="هل نسيت كلمة المرور؟", font=ctk.CTkFont(size=10, weight="bold"), text_color="#374151", fg_color="transparent", hover_color="#F3F4F6", width=0, height=20, command=self.show_forget_password_screen).pack(anchor="e", padx=45, pady=(2, 8))
        ctk.CTkButton(card, text="تسجيل الدخول  ›", font=ctk.CTkFont(size=12, weight="bold"), text_color="#FFFFFF", fg_color="#43A047", hover_color="#388E3C", height=40, corner_radius=20, command=self.handle_login).pack(fill="x", padx=45, pady=(0, 8))
        ctk.CTkButton(card, text="للمرة الأولى؟ إنشاء حساب جديد ✨", font=ctk.CTkFont(size=10, weight="bold"), text_color="#2563EB", fg_color="transparent", hover_color="#EFF6FF", width=0, height=20, command=self.show_register_screen).pack(pady=(2, 0))

    def show_register_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.unbind('<Return>')

        card = ctk.CTkFrame(self, width=380, height=560, corner_radius=25, fg_color="#FFFFFF", border_width=1, border_color="#E5E7EB")
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        self.load_logo(card, image_name="images.jpeg", size=(60, 60), pady=(10, 2))
        ctk.CTkLabel(card, text="إنشاء حساب جديد", font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"), text_color="#111827").pack(pady=(0, 6))

        self.reg_user = ctk.CTkEntry(card, placeholder_text="اسم المستخدم", height=35, corner_radius=8, justify="right")
        self.reg_user.pack(fill="x", padx=45, pady=(0, 4))

        self.reg_pass = ctk.CTkEntry(card, placeholder_text="كلمة المرور", show="•", height=35, corner_radius=8, justify="right")
        self.reg_pass.pack(fill="x", padx=45, pady=(0, 4))

        self.reg_question = ctk.CTkEntry(card, placeholder_text="سؤال الأمان", height=35, corner_radius=8, justify="right")
        self.reg_question.pack(fill="x", padx=45, pady=(0, 4))

        self.reg_answer = ctk.CTkEntry(card, placeholder_text="إجابة سؤال الأمان", height=35, corner_radius=8, justify="right")
        self.reg_answer.pack(fill="x", padx=45, pady=(0, 8))

        self.bind('<Return>', lambda event: self.handle_register())

        ctk.CTkButton(card, text="حفظ الحساب ✨", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#43A047", hover_color="#388E3C", height=38, corner_radius=19, command=self.handle_register).pack(fill="x", padx=45, pady=(0, 6))
        ctk.CTkButton(card, text="لديك حساب بالفعل؟ تسجيل الدخول ‹", font=ctk.CTkFont(size=10, weight="bold"), text_color="#4B5563", fg_color="transparent", hover_color="#F3F4F6", width=0, height=20, command=self.show_login_screen).pack(pady=(2, 0))

    def show_forget_password_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.unbind('<Return>')

        card = ctk.CTkFrame(self, width=380, height=520, corner_radius=25, fg_color="#FFFFFF", border_width=1, border_color="#E5E7EB")
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        self.load_logo(card, image_name="images.jpeg", size=(65, 65), pady=(15, 5))
        ctk.CTkLabel(card, text="استعادة كلمة المرور", font=ctk.CTkFont(family="Helvetica", size=16, weight="bold"), text_color="#111827").pack(pady=(0, 10))

        self.fp_user = ctk.CTkEntry(card, placeholder_text="اسم المستخدم الخاص بك", height=36, corner_radius=8, justify="right")
        self.fp_user.pack(fill="x", padx=45, pady=(0, 8))

        self.fp_answer = ctk.CTkEntry(card, placeholder_text="إجابة سؤال الأمان", height=36, corner_radius=8, justify="right")
        self.fp_answer.pack(fill="x", padx=45, pady=(0, 8))

        self.fp_new_pass = ctk.CTkEntry(card, placeholder_text="كلمة المرور الجديدة", show="•", height=36, corner_radius=8, justify="right")
        self.fp_new_pass.pack(fill="x", padx=45, pady=(0, 14))

        self.bind('<Return>', lambda event: self.handle_reset_password())

        ctk.CTkButton(card, text="تحديث كلمة المرور 🔑", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#43A047", hover_color="#388E3C", height=38, corner_radius=19, command=self.handle_reset_password).pack(fill="x", padx=45, pady=(0, 8))
        ctk.CTkButton(card, text="الرجوع لشاشة تسجيل الدخول ‹", font=ctk.CTkFont(size=10, weight="bold"), text_color="#4B5563", fg_color="transparent", hover_color="#F3F4F6", width=0, height=20, command=self.show_login_screen).pack(pady=(2, 0))

    # ====================================================
    # 📊 2. الشاشة الرئيسية Dashboard
    # ====================================================
    def show_dashboard_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.geometry("1180x720")
        self.configure(fg_color="#D9EBF8")

        outer_container = ctk.CTkFrame(self, fg_color="#F0F8FF", corner_radius=15, border_width=0)
        outer_container.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.98, relheight=0.96)

        sidebar = ctk.CTkFrame(outer_container, fg_color="#DDEEF9", width=200, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        role_label = "أدمن" if self.current_user_role == "admin" else "كاشير"
        ctk.CTkLabel(sidebar, text=f"Supermarket POS  🛒\n({role_label}: {self.current_user})", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E3A8A").pack(pady=(15, 10), anchor="w", padx=15)

        all_nav_items = [
            ("محطة الكاشير POS", "🖥️", self.show_cashier_station, ["admin", "user"]),
            ("تنبيه النواقص", "⚠️", self.show_stock_status, ["admin", "user"]),
            ("إدارة المستخدمين", "👥", self.show_user_management, ["admin"]),
            ("إدارة المرتجعات", "🔄", self.show_returns_screen, ["admin"]),
            ("سجل المبيعات", "📋", self.show_sales_log, ["admin"]),
            ("سجلات الفواتير", "📑", self.show_today_invoices, ["admin"]),
            ("إدارة المنتجات", "🛒", self.show_inventory_screen, ["admin"]),
            ("إدارة الخزنة", "💵", self.show_treasury_management, ["admin"]),
            ("المشتريات", "🛍️", self.show_purchases_screen, ["admin"]),
            ("التدفق النقدي", "💸", self.show_cash_flow, ["admin"]),
            ("التقارير", "📊", self.show_today_revenue_details, ["admin"]),
            ("إعدادات النظام", "⚙️", self.show_system_settings, ["admin"]),
        ]

        for idx, (text, icon, cmd, roles) in enumerate(all_nav_items):
            if self.current_user_role in roles:
                is_active = (idx == 0)
                btn_bg = "#BBE1FA" if is_active else "transparent"
                txt_color = "#0F172A" if is_active else "#334155"
                
                btn = ctk.CTkButton(
                    sidebar, text=f"{text}   {icon}", font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                    fg_color=btn_bg, hover_color="#CBD5E1", text_color=txt_color, anchor="e", height=32, corner_radius=6, command=cmd
                )
                btn.pack(fill="x", padx=8, pady=1)

        logout_btn = ctk.CTkButton(
            sidebar, text="تسجيل الخروج   🚪", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#FEE2E2", hover_color="#FCA5A5", text_color="#991B1B", anchor="e", height=34, corner_radius=6,
            command=self.handle_logout
        )
        logout_btn.pack(side="bottom", fill="x", padx=8, pady=10)

        main_content = ctk.CTkFrame(outer_container, fg_color="#FFFFFF", corner_radius=15)
        main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        header_frame = ctk.CTkFrame(main_content, fg_color="#CBE5F6", corner_radius=10, height=55)
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        header_frame.pack_propagate(False)

        now_str = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
        ctk.CTkLabel(header_frame, text=now_str, font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", justify="left").pack(side="left", padx=15)

        right_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_header.pack(side="right", padx=15)
        
        ctk.CTkButton(right_header, text="خروج 🚪", font=ctk.CTkFont(size=10, weight="bold"), fg_color="#EF4444", hover_color="#DC2626", width=65, height=28, command=self.handle_logout).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(right_header, text="Supermarket POS", font=ctk.CTkFont(size=15, weight="bold"), text_color="#0F172A").pack(side="right", padx=(8, 0))
        
        logo_bg = ctk.CTkFrame(right_header, width=32, height=32, corner_radius=16, fg_color="#4ADE80")
        logo_bg.pack(side="right")
        logo_bg.pack_propagate(False)
        ctk.CTkLabel(logo_bg, text="S", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")

        stats = self.get_live_statistics()

        stats_wrapper = ctk.CTkFrame(main_content, fg_color="transparent")
        stats_wrapper.pack(fill="x", padx=15, pady=(5, 10))

        ctk.CTkLabel(stats_wrapper, text="الإحصائيات العامة", font=ctk.CTkFont(size=16, weight="bold"), text_color="#1E293B").pack(anchor="e", pady=(0, 5))

        cards_frame = ctk.CTkFrame(stats_wrapper, fg_color="transparent")
        cards_frame.pack(fill="x")

        if self.current_user_role == "admin":
            # ⚡ تم إلغاء الربط والتفاعل لكارت صافي الربح ليصبح للعرض فقط
            cards_data = [
                ("تنبيه النواقص", str(stats['low_stock']), "⚠️", "#FCE8E6", "#D93025", "#FCA5A5", self.show_stock_status, True, True),
                ("الخزنة الحالية", f"${stats['treasury']:,.2f}", "💵", "#E6F4EA", "#137333", "#C6E7CE", self.show_treasury_management, False, True),
                ("صافي الربح اليوم", f"${stats['today_profit']:,.2f}", None, "#E6F4EA", "#137333", "#C6E7CE", None, False, False),
                ("صافي ربح الشهر", f"${stats['monthly_profit']:,.2f}", "📅", "#E0F2FE", "#0369A1", "#BAE6FD", self.show_monthly_profit_details, False, True),
                ("إيراد اليوم", f"${stats['today_revenue']:,.2f}", "📊", "#E6F4EA", "#137333", "#C6E7CE", self.show_today_revenue_details, False, True),
                ("فواتير اليوم", str(stats['today_invoices']), "🧾", "#F8FAFC", "#1E293B", "#CBD5E1", self.show_today_invoices, False, True),
                ("إجمالي المنتجات", str(stats['total_products']), "🛒", "#E6F4EA", "#137333", "#C6E7CE", self.show_inventory_screen, False, True),
            ]
        else:
            cards_data = [
                ("تنبيه النواقص", str(stats['low_stock']), "⚠️", "#FCE8E6", "#D93025", "#FCA5A5", self.show_stock_status, True, True),
                ("محطة البيع", "فتح POS", "🖥️", "#E6F4EA", "#137333", "#C6E7CE", self.show_cashier_station, False, True),
            ]

        for title, val, icon, bg_col, txt_col, border_col, action_cmd, has_alert, is_interactive in cards_data:
            cursor_style = "hand2" if is_interactive else "arrow"
            c_card = ctk.CTkFrame(
                cards_frame, 
                fg_color=bg_col, 
                corner_radius=8, 
                border_width=1, 
                border_color=border_col, 
                height=110,
                cursor=cursor_style
            )
            c_card.pack(side="right", padx=4, fill="both", expand=True)
            c_card.pack_propagate(False)

            lbl_title = ctk.CTkLabel(c_card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#374151", cursor=cursor_style)
            lbl_title.pack(pady=(12 if icon is None else 6, 2))

            lbl_icon = None
            if icon is not None:
                lbl_icon = ctk.CTkLabel(c_card, text=icon, font=ctk.CTkFont(size=20), text_color=txt_col, cursor=cursor_style)
                lbl_icon.pack(pady=1)

            lbl_val = ctk.CTkLabel(c_card, text=val, font=ctk.CTkFont(size=16 if icon is None else 14, weight="bold"), text_color="#111827", cursor=cursor_style)
            lbl_val.pack(pady=(8 if icon is None else 2, 4))

            if is_interactive and action_cmd:
                widgets_to_bind = [c_card, lbl_title, lbl_val]
                if lbl_icon:
                    widgets_to_bind.append(lbl_icon)

                for widget in widgets_to_bind:
                    widget.bind("<Button-1>", lambda event, cmd=action_cmd: cmd())

            if has_alert and stats['low_stock'] > 0:
                alert_badge = ctk.CTkFrame(c_card, fg_color="#DC2626", corner_radius=6, height=30, width=100, cursor="hand2")
                alert_badge.place(relx=1.0, rely=0.2, anchor="ne")

                lbl_alert = ctk.CTkLabel(alert_badge, text="تنبيه: منتجات قريبة\nمن النفاد", font=ctk.CTkFont(size=8, weight="bold"), text_color="#FFFFFF", justify="right", cursor="hand2")
                lbl_alert.pack(padx=2, pady=1)

                if action_cmd:
                    alert_badge.bind("<Button-1>", lambda event, cmd=action_cmd: cmd())
                    lbl_alert.bind("<Button-1>", lambda event, cmd=action_cmd: cmd())

        table_wrapper = ctk.CTkFrame(main_content, fg_color="transparent")
        table_wrapper.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        if self.current_user_role == "admin":
            ctk.CTkLabel(table_wrapper, text="آخر عمليات البيع", font=ctk.CTkFont(size=15, weight="bold"), text_color="#1E293B").pack(anchor="e", pady=(0, 6))

            th_frame = ctk.CTkFrame(table_wrapper, fg_color="#CBE5F6", height=32, corner_radius=4)
            th_frame.pack(fill="x")
            th_frame.pack_propagate(False)

            headers = ["عرض التفاصيل", "رقم الفاتورة", "الوقت", "اسم الصنف", "الكمية", "الإجمالي ($)"]
            widths = [100, 100, 150, 160, 80, 100]

            for h, w in zip(headers, widths):
                ctk.CTkLabel(th_frame, text=h, font=ctk.CTkFont(size=11, weight="bold"), text_color="#0F172A", width=w).pack(side="right", padx=4)

            recent_sales = self.get_recent_sales()

            if not recent_sales:
                ctk.CTkLabel(table_wrapper, text="لا توجد عمليات بيع مسجلة حالياً", font=ctk.CTkFont(size=12), text_color="#64748B").pack(pady=20)
            else:
                for row in recent_sales:
                    r_frame = ctk.CTkFrame(table_wrapper, fg_color="#FFFFFF", height=32, corner_radius=2, border_width=1, border_color="#E2E8F0")
                    r_frame.pack(fill="x", pady=1)
                    r_frame.pack_propagate(False)

                    detail_btn = ctk.CTkButton(r_frame, text="عرض التفاصيل", font=ctk.CTkFont(size=9, weight="bold"), fg_color="#22C55E", hover_color="#16A34A", width=85, height=22, corner_radius=10, command=lambda r=row: messagebox.showinfo("تفاصيل الفاتورة", f"فاتورة رقم #{r[0]}\nاسم الصنف: {r[2]}\nالكمية: {r[3]}\nالإجمالي: ${r[4]:.2f}\nتاريخ العملية: {r[1]}"))
                    detail_btn.pack(side="right", padx=10)

                    ent_op = ctk.CTkEntry(r_frame, width=100, height=24, fg_color="transparent", border_width=0, justify="center")
                    ent_op.insert(0, str(row[0]))
                    ent_op.configure(state="readonly")
                    ent_op.pack(side="right", padx=4)

                    ctk.CTkLabel(r_frame, text=str(row[1]), font=ctk.CTkFont(size=10), text_color="#334155", width=150).pack(side="right", padx=4)
                    ctk.CTkLabel(r_frame, text=str(row[2]), font=ctk.CTkFont(size=10), text_color="#334155", width=160).pack(side="right", padx=4)
                    ctk.CTkLabel(r_frame, text=str(row[3]), font=ctk.CTkFont(size=10), text_color="#334155", width=80).pack(side="right", padx=4)
                    ctk.CTkLabel(r_frame, text=f"${row[4]:.2f}", font=ctk.CTkFont(size=10, weight="bold"), text_color="#1E293B", width=100).pack(side="left", padx=10)
        else:
            ctk.CTkLabel(table_wrapper, text="مرحباً بك في محطة الكاشير! اضغط على (محطة الكاشير POS) للبدء في إصدار الفواتير.", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2563EB").pack(expand=True)

    # ====================================================
    # 👑 2.5 إدارة المستخدمين والترقية والحظر (الأدمن)
    # ====================================================
    def show_user_management(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("إدارة المستخدمين والصلاحيات 👥")

        scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role, is_blocked FROM users")
            users = cursor.fetchall()

        for u_id, username, role, is_blocked in users:
            row = ctk.CTkFrame(scroll, fg_color="#FFFFFF", height=45, corner_radius=8, border_width=1, border_color="#CBD5E1")
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=f"المستخدم: {username}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#0F172A", width=150, anchor="e").pack(side="right", padx=15)
            
            role_text = "أدمن (Admin)" if role == "admin" else "كاشير (User)"
            role_color = "#2563EB" if role == "admin" else "#64748B"
            ctk.CTkLabel(row, text=f"الصلاحية: {role_text}", font=ctk.CTkFont(size=11, weight="bold"), text_color=role_color, width=140).pack(side="right", padx=10)

            status_text = "محظور 🔴" if is_blocked else "نشط 🟢"
            status_color = "#DC2626" if is_blocked else "#10B981"
            ctk.CTkLabel(row, text=status_text, font=ctk.CTkFont(size=11, weight="bold"), text_color=status_color, width=80).pack(side="right", padx=10)

            btn_box = ctk.CTkFrame(row, fg_color="transparent")
            btn_box.pack(side="left", padx=10)

            new_role = "user" if role == "admin" else "admin"
            btn_role_txt = "تنزيل لكاشير" if role == "admin" else "ترقية لأدمن 👑"
            ctk.CTkButton(
                btn_box, text=btn_role_txt, font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#3B82F6", hover_color="#2563EB", width=100, height=28,
                command=lambda uid=u_id, r=new_role: self.toggle_user_role(uid, r)
            ).pack(side="left", padx=3)

            block_txt = "فك الحظر 🟢" if is_blocked else "حظر المستخدم 🚫"
            block_bg = "#16A34A" if is_blocked else "#E11D48"
            ctk.CTkButton(
                btn_box, text=block_txt, font=ctk.CTkFont(size=10, weight="bold"),
                fg_color=block_bg, width=100, height=28,
                command=lambda uid=u_id, b=is_blocked: self.toggle_user_block(uid, b)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                btn_box, text="حذف 🗑️", font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#991B1B", hover_color="#7F1D1D", width=60, height=28,
                command=lambda uid=u_id, uname=username: self.delete_user(uid, uname)
            ).pack(side="left", padx=3)

    def toggle_user_role(self, user_id, new_role):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        messagebox.showinfo("نجاح", "تم تغيير صلاحية المستخدم بنجاح!")
        self.show_user_management()

    def toggle_user_block(self, user_id, current_block):
        new_block = 0 if current_block == 1 else 1
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (new_block, user_id))
        messagebox.showinfo("نجاح", "تم تغيير حالة الحظر بنجاح!")
        self.show_user_management()

    def delete_user(self, user_id, username):
        if messagebox.askyesno("تأكيد الحذف", f"هل أنت متأكد من حذف الحساب ({username}) نهائياً؟"):
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            messagebox.showinfo("نجاح", "تم حذف المستخدم من قاعدة البيانات!")
            self.show_user_management()

    # ====================================================
    # 🖥️ 3. محطة الكاشير وإصدار الفواتير
    # ====================================================
    def show_cashier_station(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.cart = []

        header = ctk.CTkFrame(self, fg_color="#0F172A", height=50, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkButton(header, text="الرئيسية 🏠", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#334155", hover_color="#475569", width=90, height=32, command=self.show_dashboard_screen).pack(side="left", padx=15, pady=8)
        ctk.CTkLabel(header, text="محطة البيع السريع - POS Cashier", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF").pack(side="right", padx=15)

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=10, pady=10)

        left_panel = ctk.CTkFrame(main_box, fg_color="#FFFFFF", width=520, corner_radius=12, border_width=1, border_color="#CBD5E1")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))

        search_box = ctk.CTkFrame(left_panel, fg_color="transparent")
        search_box.pack(fill="x", padx=10, pady=10)

        self.barcode_ent = ctk.CTkEntry(search_box, placeholder_text="امسح الباركود أو اكتب اسم المنتج واضغط Enter...", height=38, justify="right")
        self.barcode_ent.pack(fill="x")
        self.barcode_ent.bind("<Return>", self.add_by_barcode)
        self.barcode_ent.focus_set()

        cart_header = ctk.CTkFrame(left_panel, fg_color="#E2E8F0", height=30, corner_radius=6)
        cart_header.pack(fill="x", padx=10, pady=(0, 5))
        cart_header.pack_propagate(False)

        ctk.CTkLabel(cart_header, text="المنتج", font=ctk.CTkFont(size=11, weight="bold"), text_color="#334155").pack(side="right", padx=15)
        ctk.CTkLabel(cart_header, text="الكمية والتحكم", font=ctk.CTkFont(size=11, weight="bold"), text_color="#334155").pack(side="right", padx=50)
        ctk.CTkLabel(cart_header, text="الإجمالي", font=ctk.CTkFont(size=11, weight="bold"), text_color="#334155").pack(side="left", padx=15)

        self.cart_scroll = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.cart_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        total_card = ctk.CTkFrame(left_panel, fg_color="#2563EB", corner_radius=10, height=60)
        total_card.pack(fill="x", padx=10, pady=8)
        total_card.pack_propagate(False)

        ctk.CTkLabel(total_card, text="الإجمالي الكلي", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFFFFF").pack(side="right", padx=15)
        self.total_val_label = ctk.CTkLabel(total_card, text="$0.00", font=ctk.CTkFont(size=22, weight="bold"), text_color="#FFFFFF")
        self.total_val_label.pack(side="left", padx=15)

        btn_action_box = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_action_box.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(btn_action_box, text="إلغاء الفاتورة ❌", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#EF4444", hover_color="#DC2626", height=40, command=self.clear_cart).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btn_action_box, text="دفع وإصدار الفاتورة 💵", font=ctk.CTkFont(size=13, weight="bold"), fg_color="#10B981", hover_color="#059669", height=40, command=self.checkout).pack(side="right", expand=True, fill="x", padx=(4, 0))

        right_panel = ctk.CTkFrame(main_box, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#CBD5E1")
        right_panel.pack(side="right", fill="both", expand=True, padx=(5, 0))

        ctk.CTkLabel(right_panel, text="قائمة المنتجات السريعة", font=ctk.CTkFont(size=14, weight="bold"), text_color="#0F172A").pack(anchor="e", padx=15, pady=(10, 5))

        self.products_grid = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.products_grid.pack(fill="both", expand=True, padx=10, pady=5)

        self.load_cashier_products()

    def load_cashier_products(self):
        for child in self.products_grid.winfo_children():
            child.destroy()

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price, stock FROM products")
            products = cursor.fetchall()

        if not products:
            ctk.CTkLabel(self.products_grid, text="لا توجد منتجات مسجلة، يرجى طلب إضافتها من الأدمن", font=ctk.CTkFont(size=12), text_color="#64748B").pack(pady=40)
            return

        row, col = 0, 0
        for p_id, name, price, stock in products:
            btn_text = f"{name}\n${price:.2f}\nالمخزون: {stock}"
            btn = ctk.CTkButton(
                self.products_grid, text=btn_text, font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#F8FAFC", text_color="#1E293B", border_width=1, border_color="#CBD5E1",
                hover_color="#BAE6FD", width=120, height=75, corner_radius=10,
                command=lambda n=name, p=price: self.add_to_cart(n, p)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            col += 1
            if col > 2:
                col = 0
                row += 1

    def add_to_cart(self, item_name, price):
        found = False
        for item in self.cart:
            if item["name"] == item_name:
                item["qty"] += 1
                item["total"] = item["qty"] * item["price"]
                found = True
                break

        if not found:
            self.cart.append({"name": item_name, "price": price, "qty": 1, "total": price})

        self.update_cart_ui()

    def change_qty(self, item_name, delta):
        for item in self.cart:
            if item["name"] == item_name:
                item["qty"] += delta
                if item["qty"] <= 0:
                    self.cart.remove(item)
                else:
                    item["total"] = item["qty"] * item["price"]
                break
        self.update_cart_ui()

    def remove_item(self, item_name):
        self.cart = [item for item in self.cart if item["name"] != item_name]
        self.update_cart_ui()

    def add_by_barcode(self, event):
        query = self.barcode_ent.get().strip()
        if not query:
            return

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, price FROM products WHERE barcode = ? OR name LIKE ?", (query, f"%{query}%"))
            prod = cursor.fetchone()

        if prod:
            self.add_to_cart(prod[0], prod[1])
            self.barcode_ent.delete(0, 'end')
        else:
            messagebox.showwarning("تنبيه", "لم يتم العثور على المنتج!")

    def update_cart_ui(self):
        for widget in self.cart_scroll.winfo_children():
            widget.destroy()

        grand_total = 0.0
        for item in self.cart:
            grand_total += item["total"]

            row_frame = ctk.CTkFrame(self.cart_scroll, fg_color="#F8FAFC", corner_radius=8, height=42, border_width=1, border_color="#E2E8F0")
            row_frame.pack(fill="x", pady=2, padx=2)
            row_frame.pack_propagate(False)

            ctk.CTkLabel(row_frame, text=item["name"], font=ctk.CTkFont(size=11, weight="bold"), text_color="#0F172A", width=120, anchor="e").pack(side="right", padx=5)

            ctrl_box = ctk.CTkFrame(row_frame, fg_color="transparent")
            ctrl_box.pack(side="right", padx=5)

            name_val = item["name"]

            ctk.CTkButton(ctrl_box, text="-", width=24, height=24, fg_color="#EF4444", hover_color="#DC2626", font=ctk.CTkFont(size=12, weight="bold"), command=lambda n=name_val: self.change_qty(n, -1)).pack(side="left", padx=2)
            ctk.CTkLabel(ctrl_box, text=str(item["qty"]), font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", width=25).pack(side="left")
            ctk.CTkButton(ctrl_box, text="+", width=24, height=24, fg_color="#10B981", hover_color="#059669", font=ctk.CTkFont(size=12, weight="bold"), command=lambda n=name_val: self.change_qty(n, 1)).pack(side="left", padx=2)

            ctk.CTkLabel(row_frame, text=f"${item['total']:.2f}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#2563EB", width=60).pack(side="left", padx=5)
            ctk.CTkButton(row_frame, text="🗑️", width=25, height=24, fg_color="transparent", hover_color="#FEE2E2", text_color="#EF4444", command=lambda n=name_val: self.remove_item(n)).pack(side="left", padx=2)

        self.total_val_label.configure(text=f"${grand_total:.2f}")
        self.update_idletasks()

    def clear_cart(self):
        self.cart = []
        self.update_cart_ui()

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("تنبيه", "السلة فارغة!")
            return

        try:
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                sale_costs = {}
                for item in self.cart:
                    cursor.execute("SELECT stock, cost_price FROM products WHERE name = ?", (item["name"],))
                    res = cursor.fetchone()
                    if res:
                        current_stock, current_cost = res
                        if item["qty"] > current_stock:
                            messagebox.showerror("فشل العملية ❌", f"الكمية غير كافية للمنتج: ({item['name']})\nالمطلوب: {item['qty']} | المتاح بالمخزن: {current_stock}")
                            return
                        sale_costs[item["name"]] = float(current_cost or 0.0)
                    else:
                        messagebox.showerror("خطأ", f"المنتج ({item['name']}) غير موجود بقاعدة البيانات!")
                        return

                inv_num = f"INV-{datetime.now().strftime('%M%S%f')[-6:]}"
                dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                sales_data = [
                    (inv_num, item["name"], item["qty"], item["total"], dt, 0, sale_costs.get(item["name"], 0.0))
                    for item in self.cart
                ]

                cursor.executemany(
                    "INSERT INTO sales (invoice_num, item_name, quantity, total_price, date_time, is_reset, cost_price) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    sales_data
                )

                for item in self.cart:
                    cursor.execute("UPDATE products SET stock = stock - ? WHERE name = ?", (item["qty"], item["name"]))

            messagebox.showinfo("تم بنجاح ✨", f"تم إصدار الفاتورة رقم #{inv_num} وتضم {len(self.cart)} منتجات!")
            self.clear_cart()
            self.load_cashier_products()
        except Exception as e:
            messagebox.showerror("خطأ في الدفع", f"حدث خطأ أثناء معالجة الفاتورة: {e}")

    # ====================================================
    # ⚠️ 4. شاشة تنبيه النواقص بالمخزون
    # ====================================================
    def show_stock_status(self):
        self.create_screen_base("تنبيه النواقص بالمخزون ⚠️📟")

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, barcode, name, category, price, stock FROM products WHERE stock <= 5")
            low_products = cursor.fetchall()

        if not low_products:
            ctk.CTkLabel(self.content_area, text="🎉 لا توجد أية منتجات ناقصة بالمخزن في الوقت الحالي!", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10B981").pack(pady=50)
            return

        scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        for p_id, barcode, name, cat, price, stock in low_products:
            f = ctk.CTkFrame(scroll, fg_color="#FEE2E2", height=42, corner_radius=8, border_width=1, border_color="#FCA5A5")
            f.pack(fill="x", pady=3)
            f.pack_propagate(False)

            ctk.CTkLabel(f, text=f"اسم الصنف: {name}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#991B1B").pack(side="right", padx=15)
            
            ent_bar = ctk.CTkEntry(f, width=160, height=28, fg_color="transparent", border_width=0, font=ctk.CTkFont(size=11), justify="right")
            ent_bar.insert(0, f"الباركود: {barcode}")
            ent_bar.configure(state="readonly")
            ent_bar.pack(side="right", padx=10)

            ctk.CTkLabel(f, text=f"القسم: {cat}", font=ctk.CTkFont(size=11), text_color="#7F1D1D").pack(side="right", padx=10)
            ctk.CTkLabel(f, text=f"الكمية المتبقية: {stock} قطع فقط!", font=ctk.CTkFont(size=12, weight="bold"), text_color="#DC2626").pack(side="left", padx=15)

    # ====================================================
    # 🔄 5. شاشات الأدمن والعمليات
    # ====================================================
    def show_returns_screen(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("إدارة مرتجعات المبيعات 🔄")

        top_bar = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#CBD5E1")
        top_bar.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(top_bar, text="ابحث برقم الفاتورة:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#0F172A").pack(side="right", padx=10, pady=10)

        self.return_inv_entry = ctk.CTkEntry(top_bar, placeholder_text="مثال: INV-1234", height=36, justify="right")
        self.return_inv_entry.pack(side="right", padx=10, pady=10)

        ctk.CTkButton(top_bar, text="بحث 🔍", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#2563EB", hover_color="#1D4ED8", width=90, height=36, command=self.search_invoice_for_return).pack(side="right", padx=10)

        self.returns_scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        self.returns_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    def search_invoice_for_return(self):
        inv_num = self.return_inv_entry.get().strip()
        if not inv_num:
            messagebox.showwarning("تنبيه", "يرجى كتابة رقم الفاتورة للبحث.")
            return

        for widget in self.returns_scroll.winfo_children():
            widget.destroy()

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, item_name, quantity, total_price, date_time FROM sales WHERE invoice_num = ?", (inv_num,))
            items = cursor.fetchall()

        if not items:
            messagebox.showinfo("تنبيه", "لم يتم العثور على فاتورة بهذا الرقم!")
            return

        th = ctk.CTkFrame(self.returns_scroll, fg_color="#E2E8F0", height=35, corner_radius=4)
        th.pack(fill="x", pady=(0, 5))
        th.pack_propagate(False)

        ctk.CTkLabel(th, text="اسم المنتج", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", width=150).pack(side="right", padx=5)
        ctk.CTkLabel(th, text="الكمية المباعة", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", width=90).pack(side="right", padx=5)
        ctk.CTkLabel(th, text="إجمالي المبلغ", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", width=100).pack(side="right", padx=5)
        ctk.CTkLabel(th, text="الكمية المراد إرجاعها", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", width=130).pack(side="right", padx=5)
        ctk.CTkLabel(th, text="إجراء الإرجاع", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1E293B", width=100).pack(side="left", padx=10)

        for sale_id, item_name, qty, total_price, dt in items:
            unit_price = total_price / qty if qty > 0 else 0.0

            row = ctk.CTkFrame(self.returns_scroll, fg_color="#FFFFFF", height=42, corner_radius=6, border_width=1, border_color="#CBD5E1")
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=item_name, font=ctk.CTkFont(size=11, weight="bold"), text_color="#0F172A", width=150).pack(side="right", padx=5)
            ctk.CTkLabel(row, text=str(qty), font=ctk.CTkFont(size=11), text_color="#334155", width=90).pack(side="right", padx=5)
            ctk.CTkLabel(row, text=f"${total_price:.2f}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10B981", width=100).pack(side="right", padx=5)

            ret_qty_ent = ctk.CTkEntry(row, width=70, height=28, justify="center")
            ret_qty_ent.insert(0, "1")
            ret_qty_ent.pack(side="right", padx=30)

            ret_btn = ctk.CTkButton(
                row, text="إرجاع المنتج 🔄", font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#DC2626", hover_color="#B91C1C", width=95, height=26, corner_radius=6,
                command=lambda s_id=sale_id, inv=inv_num, name=item_name, max_q=qty, u_p=unit_price, q_ent=ret_qty_ent: self.process_return(s_id, inv, name, max_q, u_p, q_ent)
            )
            ret_btn.pack(side="left", padx=10)

    def process_return(self, sale_id, inv_num, item_name, max_qty, unit_price, qty_entry):
        try:
            return_qty = int(qty_entry.get().strip())
        except ValueError:
            messagebox.showerror("خطأ", "يرجى كتابة كمية إرجاع صحيحة بالأرقام.")
            return

        if return_qty <= 0 or return_qty > max_qty:
            messagebox.showwarning("تنبيه", f"كمية الإرجاع يجب أن تكون بين 1 و {max_qty}")
            return

        refund_amt = return_qty * unit_price
        ret_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if messagebox.askyesno("تأكيد الإرجاع", f"هل تريد إرجاع عدد {return_qty} من ({item_name}) بقيمة ${refund_amt:.2f}؟"):
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "INSERT INTO returns (invoice_num, item_name, returned_qty, refund_amount, return_date) VALUES (?, ?, ?, ?, ?)",
                    (inv_num, item_name, return_qty, refund_amt, ret_date)
                )

                cursor.execute("UPDATE products SET stock = stock + ? WHERE name = ?", (return_qty, item_name))

                if return_qty == max_qty:
                    cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
                else:
                    new_qty = max_qty - return_qty
                    new_total = new_qty * unit_price
                    cursor.execute("UPDATE sales SET quantity = ?, total_price = ? WHERE id = ?", (new_qty, new_total, sale_id))

            messagebox.showinfo("نجاح", "تمت عملية الإرجاع وتحديث المخزون بنجاح!")
            self.search_invoice_for_return()

    # ⚡ تم إلغاء خيار/شريط البحث بالتاريخ وتنظيف الواجهة لعرض كل الفواتير مباشرة
    def show_today_invoices(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("سجلات الفواتير 📑")

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT invoice_num, MIN(date_time), SUM(total_price), COUNT(item_name)
                FROM sales 
                WHERE is_reset = 0
                GROUP BY invoice_num
                ORDER BY MIN(date_time) DESC
            """)
            invoices = cursor.fetchall()

        self.invoices_scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        self.invoices_scroll.pack(fill="both", expand=True, padx=15, pady=10)

        if not invoices:
            ctk.CTkLabel(self.invoices_scroll, text="لا توجد فواتير مسجلة حالياً!", font=ctk.CTkFont(size=14), text_color="#64748B").pack(pady=50)
            return

        for inv_num, dt, total, items_count in invoices:
            f = ctk.CTkFrame(self.invoices_scroll, fg_color="#FFFFFF", height=45, corner_radius=8, border_width=1, border_color="#CBD5E1")
            f.pack(fill="x", pady=4)
            f.pack_propagate(False)

            ent_inv = ctk.CTkEntry(f, width=150, height=28, fg_color="transparent", border_width=0, font=ctk.CTkFont(size=12, weight="bold"), justify="right")
            ent_inv.insert(0, f"#{inv_num}")
            ent_inv.configure(state="readonly")
            ent_inv.pack(side="right", padx=15)

            ctk.CTkLabel(f, text=f"التاريخ والوقت: {dt}", font=ctk.CTkFont(size=11), text_color="#475569").pack(side="right", padx=20)
            ctk.CTkLabel(f, text=f"عدد الأصناف: {items_count}", font=ctk.CTkFont(size=11), text_color="#475569").pack(side="right", padx=20)
            ctk.CTkLabel(f, text=f"الإجمالي: ${total:.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981").pack(side="left", padx=20)

    def show_today_revenue_details(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("تفاصيل إيراد المنتجات المباعة اليوم 📊")
        today_date = datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_name, SUM(quantity), SUM(total_price)
                FROM sales 
                WHERE date(date_time) = date(?) AND is_reset = 0
                GROUP BY item_name
            """, (today_date,))
            products_sold = cursor.fetchall()

        if not products_sold:
            ctk.CTkLabel(self.content_area, text="لم يتم بيع أي منتجات اليوم حتى الآن", font=ctk.CTkFont(size=14), text_color="#64748B").pack(pady=50)
            return

        scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        for item_name, qty, total_p in products_sold:
            f = ctk.CTkFrame(scroll, fg_color="#FFFFFF", height=40, corner_radius=8, border_width=1, border_color="#CBD5E1")
            f.pack(fill="x", pady=3)
            f.pack_propagate(False)

            ctk.CTkLabel(f, text=f"المنتج: {item_name}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#0F172A").pack(side="right", padx=15)
            ctk.CTkLabel(f, text=f"إجمالي الكمية المباعة: {qty}", font=ctk.CTkFont(size=11), text_color="#334155").pack(side="right", padx=30)
            ctk.CTkLabel(f, text=f"إجمالي المبيعات: ${total_p:.2f}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#2563EB").pack(side="left", padx=15)

    def show_today_profit_details(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("تفاصيل صافي الأرباح اليومية 💵")

        current_month = datetime.now().strftime("%Y-%m")
        
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date(s.date_time) as sale_date, 
                       SUM(s.total_price) as total_revenue,
                       SUM(s.total_price - (s.quantity * COALESCE(s.cost_price, p.cost_price, 0))) as real_profit
                FROM sales s
                LEFT JOIN products p ON s.item_name = p.name
                WHERE strftime('%Y-%m', s.date_time) = ?
                GROUP BY sale_date
                ORDER BY sale_date DESC
            """, (current_month,))
            rows = cursor.fetchall()

        if not rows:
            ctk.CTkLabel(self.content_area, text="لا توجد بيانات مبيعات لهذا الشهر بعد", font=ctk.CTkFont(size=14), text_color="#64748B").pack(pady=50)
            return

        th_frame = ctk.CTkFrame(self.content_area, fg_color="#CBE5F6", height=35, corner_radius=4)
        th_frame.pack(fill="x", padx=15, pady=(10, 5))
        th_frame.pack_propagate(False)

        ctk.CTkLabel(th_frame, text="التاريخ", font=ctk.CTkFont(size=12, weight="bold"), text_color="#0F172A", width=200).pack(side="right", padx=15)
        ctk.CTkLabel(th_frame, text="إجمالي المبيعات ($)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#0F172A", width=200).pack(side="right", padx=15)
        ctk.CTkLabel(th_frame, text="صافي الربح الفعلي ($)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#0F172A", width=200).pack(side="left", padx=15)

        scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for sale_date, revenue, profit in rows:
            revenue = revenue or 0.0
            profit = profit or 0.0
            r_frame = ctk.CTkFrame(scroll, fg_color="#FFFFFF", height=38, corner_radius=6, border_width=1, border_color="#CBD5E1")
            r_frame.pack(fill="x", pady=2)
            r_frame.pack_propagate(False)

            ctk.CTkLabel(r_frame, text=sale_date, font=ctk.CTkFont(size=11, weight="bold"), text_color="#334155", width=200).pack(side="right", padx=15)
            ctk.CTkLabel(r_frame, text=f"${revenue:,.2f}", font=ctk.CTkFont(size=11), text_color="#0F172A", width=200).pack(side="right", padx=15)
            ctk.CTkLabel(r_frame, text=f"${profit:,.2f}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981", width=200).pack(side="left", padx=15)

    def get_treasury_balance(self):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = 'treasury_balance'")
            row = cursor.fetchone()
        try:
            return float(row[0]) if row else 0.0
        except (TypeError, ValueError):
            return 0.0

    def set_treasury_balance(self, amount):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO system_state (key, value) VALUES ('treasury_balance', ?)",
                           (str(float(amount)),))

    def show_treasury_management(self):
        if self.current_user_role != "admin":
            return
        self.create_screen_base("إدارة الخزنة والترحيل 💵")
        today_date = datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(total_price), 0) FROM sales WHERE date(date_time) = date(?) AND is_reset = 0",
                           (today_date,))
            today_rev = cursor.fetchone()[0] or 0.0

        treasury_balance = self.get_treasury_balance()

        card = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=15,
                            border_width=1, border_color="#CBD5E1", width=560, height=430)
        card.place(relx=0.5, rely=0.4, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="حالة الخزنة والتدفق النقدي",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#0F172A").pack(pady=15)

        p_frame = ctk.CTkFrame(card, fg_color="#E6F4EA", corner_radius=8)
        p_frame.pack(fill="x", padx=30, pady=8)
        ctk.CTkLabel(p_frame, text="رصيد الخزنة الحالي:",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#137333").pack(side="right", padx=15, pady=12)
        ctk.CTkLabel(p_frame, text=f"${treasury_balance:,.2f}",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#137333").pack(side="left", padx=15)

        t_frame = ctk.CTkFrame(card, fg_color="#EFF6FF", corner_radius=8)
        t_frame.pack(fill="x", padx=30, pady=8)
        ctk.CTkLabel(t_frame, text="إيراد اليوم الحالي المعلق:",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#1E293B").pack(side="right", padx=15, pady=12)
        ctk.CTkLabel(t_frame, text=f"${today_rev:,.2f}",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color="#2563EB").pack(side="left", padx=15)

        ctk.CTkButton(card, text="تصفير إيراد اليوم وترحيله إلى الخزنة 🔄",
                      font=ctk.CTkFont(size=12, weight="bold"), fg_color="#DC2626",
                      hover_color="#B91C1C", height=42, command=self.reset_today_revenue).pack(fill="x", padx=30, pady=(15, 7))
        ctk.CTkButton(card, text="تصفير الخزنة بالكامل 🧹",
                      font=ctk.CTkFont(size=12, weight="bold"), fg_color="#7C3AED",
                      hover_color="#6D28D9", height=42, command=self.reset_treasury).pack(fill="x", padx=30, pady=(7, 15))
        ctk.CTkLabel(card, text="تصفير الخزنة لا يمسح إيراد اليوم المعلق ولا يحذف سجلات المبيعات.",
                     font=ctk.CTkFont(size=9), text_color="#64748B").pack(pady=(0, 5))

    def reset_today_revenue(self):
        if messagebox.askyesno("تأكيد الترحيل",
                               "هل أنت متأكد من تصفير إيراد اليوم وتحويله إلى رصيد الخزنة؟"):
            today_date = datetime.now().strftime("%Y-%m-%d")
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(SUM(total_price), 0) FROM sales WHERE date(date_time) = date(?) AND is_reset = 0",
                               (today_date,))
                today_rev = cursor.fetchone()[0] or 0.0
                if today_rev > 0:
                    current_treasury = self.get_treasury_balance()
                    cursor.execute("INSERT OR REPLACE INTO system_state (key, value) VALUES ('treasury_balance', ?)",
                                   (str(current_treasury + today_rev),))
                    cursor.execute("UPDATE sales SET is_reset = 1 WHERE date(date_time) = date(?) AND is_reset = 0",
                                   (today_date,))
            messagebox.showinfo("تم بنجاح", f"تم تصفير إيراد اليوم وترحيل ${today_rev:,.2f} إلى الخزنة.")
            self.show_treasury_management()

    def reset_treasury(self):
        if messagebox.askyesno("تأكيد تصفير الخزنة",
                               "سيتم جعل رصيد الخزنة = 0.\nلن يتم حذف المبيعات أو إيراد اليوم المعلق.\n\nهل تريد المتابعة؟"):
            self.set_treasury_balance(0.0)
            messagebox.showinfo("تم بنجاح", "تم تصفير الخزنة بالكامل.")
            self.show_treasury_management()

    def show_sales_log(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("سجل المبيعات الشامل 📋")

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT invoice_num, date_time, item_name, quantity, total_price FROM sales ORDER BY id DESC")
            all_sales = cursor.fetchall()

        if not all_sales:
            ctk.CTkLabel(self.content_area, text="لا توجد عمليات بيع مسجلة حتى الآن", font=ctk.CTkFont(size=14), text_color="#64748B").pack(pady=50)
            return

        scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=10)

        for inv_num, dt, item_name, qty, total in all_sales:
            f = ctk.CTkFrame(scroll, fg_color="#FFFFFF", height=38, corner_radius=6, border_width=1, border_color="#CBD5E1")
            f.pack(fill="x", pady=2)
            f.pack_propagate(False)

            ent_inv = ctk.CTkEntry(f, width=110, height=26, fg_color="transparent", border_width=0, font=ctk.CTkFont(size=11, weight="bold"), justify="right")
            ent_inv.insert(0, f"#{inv_num}")
            ent_inv.configure(state="readonly")
            ent_inv.pack(side="right", padx=5)

            ctk.CTkLabel(f, text=dt, font=ctk.CTkFont(size=10), text_color="#475569", width=140).pack(side="right", padx=10)
            ctk.CTkLabel(f, text=item_name, font=ctk.CTkFont(size=11), text_color="#0F172A", width=150).pack(side="right", padx=10)
            ctk.CTkLabel(f, text=f"الكمية: {qty}", font=ctk.CTkFont(size=11), text_color="#334155", width=80).pack(side="right", padx=10)
            ctk.CTkLabel(f, text=f"${total:.2f}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981").pack(side="left", padx=15)

    # ====================================================
    # 🛍️ إدارة المشتريات وصافي ربح الشهر
    # ====================================================
    def show_purchases_screen(self):
        if self.current_user_role != "admin":
            return

        self.create_screen_base("إدارة المشتريات 🛍️")

        top = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=12, border_width=1, border_color="#CBD5E1")
        top.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(top, text="إضافة عملية شراء جديدة",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#0F172A").pack(anchor="e", padx=15, pady=(12, 8))

        fields = ctk.CTkFrame(top, fg_color="transparent")
        fields.pack(fill="x", padx=15, pady=(0, 8))
        self.purchase_name = ctk.CTkEntry(fields, placeholder_text="اسم المنتج", height=36, justify="right")
        self.purchase_name.pack(side="right", fill="x", expand=True, padx=4)
        self.purchase_cost = ctk.CTkEntry(fields, placeholder_text="سعر الشراء للوحدة", height=36, justify="right")
        self.purchase_cost.pack(side="right", fill="x", expand=True, padx=4)
        self.purchase_qty = ctk.CTkEntry(fields, placeholder_text="الكمية", height=36, justify="right")
        self.purchase_qty.pack(side="right", fill="x", expand=True, padx=4)

        ctk.CTkButton(fields, text="تسجيل المشتريات ➕", font=ctk.CTkFont(size=11, weight="bold"),
                      fg_color="#10B981", hover_color="#059669", height=36, width=150,
                      command=self.add_purchase).pack(side="left", padx=4)

        summary = ctk.CTkFrame(top, fg_color="#EFF6FF", corner_radius=8)
        summary.pack(fill="x", padx=15, pady=(0, 12))
        monthly_profit = self.calculate_monthly_profit()
        purchases_total = self.get_month_purchases_total()
        ctk.CTkLabel(summary, text=f"إجمالي مشتريات الشهر: ${purchases_total:,.2f}",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#DC2626").pack(side="right", padx=20, pady=10)
        ctk.CTkLabel(summary, text=f"صافي ربح الشهر: ${monthly_profit:,.2f}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#10B981" if monthly_profit >= 0 else "#DC2626").pack(side="left", padx=20, pady=10)
        ctk.CTkButton(summary, text="تصفير الشهر والبدء من جديد 🔄",
                      font=ctk.CTkFont(size=11, weight="bold"),
                      fg_color="#DC2626", hover_color="#B91C1C", height=32,
                      command=self.reset_monthly_profit).pack(side="left", padx=10, pady=6)

        ctk.CTkLabel(self.content_area, text="سجل المشتريات",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color="#0F172A").pack(anchor="e", padx=15, pady=(3, 5))
        scroll = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT item_name, unit_cost, quantity, total_cost, purchase_date FROM purchases ORDER BY id DESC")
            purchases = cursor.fetchall()

        if not purchases:
            ctk.CTkLabel(scroll, text="لا توجد مشتريات مسجلة حتى الآن.",
                         font=ctk.CTkFont(size=13), text_color="#64748B").pack(pady=30)
            return

        for item_name, unit_cost, qty, total_cost, purchase_date in purchases:
            row = ctk.CTkFrame(scroll, fg_color="#FFFFFF", height=42, corner_radius=7,
                               border_width=1, border_color="#CBD5E1")
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=item_name, font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="#0F172A", width=180).pack(side="right", padx=8)
            ctk.CTkLabel(row, text=f"سعر الوحدة: ${unit_cost:.2f}",
                         font=ctk.CTkFont(size=10), text_color="#334155", width=130).pack(side="right", padx=8)
            ctk.CTkLabel(row, text=f"الكمية: {qty}",
                         font=ctk.CTkFont(size=10), text_color="#334155", width=90).pack(side="right", padx=8)
            ctk.CTkLabel(row, text=f"الإجمالي: ${total_cost:.2f}",
                         font=ctk.CTkFont(size=11, weight="bold"), text_color="#DC2626", width=120).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=purchase_date,
                         font=ctk.CTkFont(size=10), text_color="#64748B", width=145).pack(side="left", padx=8)

    def add_purchase(self):
        name = self.purchase_name.get().strip()
        cost_text = self.purchase_cost.get().strip()
        qty_text = self.purchase_qty.get().strip()
        if not name or not cost_text or not qty_text:
            messagebox.showwarning("تنبيه", "يرجى إدخال اسم المنتج وسعر الشراء والكمية.")
            return

        try:
            unit_cost = float(cost_text)
            qty = int(qty_text)
            if unit_cost < 0 or qty <= 0:
                raise ValueError
            total_cost = unit_cost * qty
            purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, stock, cost_price FROM products WHERE name = ?", (name,))
                product = cursor.fetchone()
                if not product:
                    messagebox.showwarning("المنتج غير موجود",
                                           "المنتج غير موجود في إدارة المنتجات. أضفه أولاً ثم سجّل المشتريات.")
                    return

                product_id, old_stock, old_cost = product
                old_stock = int(old_stock or 0)
                old_cost = float(old_cost or 0.0)
                new_stock = old_stock + qty
                weighted_cost = ((old_stock * old_cost) + (qty * unit_cost)) / new_stock
                cursor.execute("UPDATE products SET stock = ?, cost_price = ? WHERE id = ?",
                               (new_stock, weighted_cost, product_id))
                cursor.execute("INSERT INTO purchases (item_name, unit_cost, quantity, total_cost, purchase_date) VALUES (?, ?, ?, ?, ?)",
                               (name, unit_cost, qty, total_cost, purchase_date))

            messagebox.showinfo("تم بنجاح",
                                f"تم تسجيل الشراء بقيمة ${total_cost:.2f}.\n"
                                "تمت إضافة الكمية للمخزون وخصم التكلفة من صافي ربح الشهر.")
            self.purchase_name.delete(0, "end")
            self.purchase_cost.delete(0, "end")
            self.purchase_qty.delete(0, "end")
            self.show_purchases_screen()
        except ValueError:
            messagebox.showerror("خطأ", "سعر الشراء رقم صحيح، والكمية عدد صحيح أكبر من صفر.")
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر تسجيل المشتريات: {e}")

    def get_monthly_start(self):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = 'monthly_start'")
            row = cursor.fetchone()
        return row[0] if row and row[0] else datetime.now().strftime("%Y-%m-01 00:00:00")

    def calculate_monthly_sales_profit(self):
        monthly_start = self.get_monthly_start()
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(s.total_price - (s.quantity * COALESCE(s.cost_price, p.cost_price, 0))), 0) FROM sales s LEFT JOIN products p ON s.item_name = p.name WHERE datetime(s.date_time) >= datetime(?)",
                           (monthly_start,))
            return float(cursor.fetchone()[0] or 0.0)

    def get_month_purchases_total(self):
        monthly_start = self.get_monthly_start()
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(SUM(total_cost), 0) FROM purchases WHERE datetime(purchase_date) >= datetime(?)",
                           (monthly_start,))
            return float(cursor.fetchone()[0] or 0.0)

    def calculate_monthly_profit(self):
        return self.calculate_monthly_sales_profit() - self.get_month_purchases_total()

    def show_monthly_profit_details(self):
        if self.current_user_role != "admin":
            return
        self.create_screen_base("صافي ربح الشهر 📅💰")
        monthly_start = self.get_monthly_start()
        sales_profit = self.calculate_monthly_sales_profit()
        purchases = self.get_month_purchases_total()
        net_profit = sales_profit - purchases

        card = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=15,
                            border_width=1, border_color="#CBD5E1", width=620, height=360)
        card.place(relx=0.5, rely=0.42, anchor="center")
        card.pack_propagate(False)
        ctk.CTkLabel(card, text="ملخص صافي ربح دورة الشهر",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color="#0F172A").pack(pady=(20, 8))
        ctk.CTkLabel(card, text=f"بداية الدورة الحالية: {monthly_start}",
                     font=ctk.CTkFont(size=10), text_color="#64748B").pack(pady=(0, 15))

        def row(title, value, color):
            frame = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=8)
            frame.pack(fill="x", padx=35, pady=5)
            ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#334155").pack(side="right", padx=15, pady=9)
            ctk.CTkLabel(frame, text=f"${value:,.2f}", font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=color).pack(side="left", padx=15)

        row("أرباح المبيعات قبل المشتريات:", sales_profit, "#10B981")
        row("إجمالي المشتريات:", purchases, "#DC2626")
        row("صافي الربح بعد خصم المشتريات:", net_profit, "#10B981" if net_profit >= 0 else "#DC2626")
        ctk.CTkButton(card, text="تصفير الشهر والبدء من جديد 🔄",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#DC2626", hover_color="#B91C1C", height=40,
                      command=self.reset_monthly_profit).pack(fill="x", padx=35, pady=15)

    def reset_monthly_profit(self):
        if self.current_user_role != "admin":
            return
        if messagebox.askyesno("تأكيد تصفير الشهر",
                               "سيتم بدء دورة ربح جديدة من الآن.\n"
                               "لن يتم حذف المبيعات أو المشتريات القديمة من السجل.\n\n"
                               "هل تريد المتابعة؟"):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO system_state (key, value) VALUES ('monthly_start', ?)", (now,))
            messagebox.showinfo("تم بنجاح", "تم تصفير صافي ربح الشهر وبدء دورة جديدة.")
            self.show_monthly_profit_details()

    def show_cash_flow(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("تقرير التدفق النقدي 💸")

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total_price), COUNT(DISTINCT invoice_num) FROM sales")
            res = cursor.fetchone()
            total_sales_sum = res[0] if res[0] else 0.0
            total_invoices_cnt = res[1] if res[1] else 0
            treasury_balance = self.get_treasury_balance()
            monthly_purchases = self.get_month_purchases_total()

        avg_ticket = (total_sales_sum / total_invoices_cnt) if total_invoices_cnt > 0 else 0.0

        card = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=15, border_width=1, border_color="#CBD5E1", width=520, height=320)
        card.place(relx=0.5, rely=0.4, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="مؤشرات التدفق النقدي التراكمية", font=ctk.CTkFont(size=16, weight="bold"), text_color="#0F172A").pack(pady=20)

        f1 = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=8)
        f1.pack(fill="x", padx=25, pady=6)
        ctk.CTkLabel(f1, text="إجمالي جميع المبيعات التاريخية:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").pack(side="right", padx=15, pady=8)
        ctk.CTkLabel(f1, text=f"${total_sales_sum:.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981").pack(side="left", padx=15)

        f2 = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=8)
        f2.pack(fill="x", padx=25, pady=6)
        ctk.CTkLabel(f2, text="إجمالي عدد الفواتير الصادرة:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").pack(side="right", padx=15, pady=8)
        ctk.CTkLabel(f2, text=str(total_invoices_cnt), font=ctk.CTkFont(size=13, weight="bold"), text_color="#2563EB").pack(side="left", padx=15)

        f3 = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=8)
        f3.pack(fill="x", padx=25, pady=6)
        ctk.CTkLabel(f3, text="متوسط قيمة الفاتورة الواحدة:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").pack(side="right", padx=15, pady=8)
        ctk.CTkLabel(f3, text=f"${avg_ticket:.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#7C3AED").pack(side="left", padx=15)

        f4 = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=8)
        f4.pack(fill="x", padx=25, pady=6)
        ctk.CTkLabel(f4, text="رصيد الخزنة الحالي:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").pack(side="right", padx=15, pady=8)
        ctk.CTkLabel(f4, text=f"${treasury_balance:,.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#137333").pack(side="left", padx=15)

        f5 = ctk.CTkFrame(card, fg_color="#F8FAFC", corner_radius=8)
        f5.pack(fill="x", padx=25, pady=6)
        ctk.CTkLabel(f5, text="مشتريات دورة الشهر الحالية:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#334155").pack(side="right", padx=15, pady=8)
        ctk.CTkLabel(f5, text=f"${monthly_purchases:,.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#DC2626").pack(side="left", padx=15)

    def show_system_settings(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("إعدادات النظام وطابعة الفواتير ⚙️")

        card = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=15, border_width=1, border_color="#CBD5E1", width=500, height=360)
        card.place(relx=0.5, rely=0.4, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="تفضيلات النظام والكاشير", font=ctk.CTkFont(size=16, weight="bold"), text_color="#0F172A").pack(pady=15)

        ctk.CTkEntry(card, placeholder_text="اسم السوبرماركت (للطباعة)", height=38, justify="right").pack(fill="x", padx=30, pady=8)
        ctk.CTkEntry(card, placeholder_text="عنوان الفرع ورقم الهاتف", height=38, justify="right").pack(fill="x", padx=30, pady=8)
        ctk.CTkEntry(card, placeholder_text="العملة الرسمية (مثال: $ أو EGP)", height=38, justify="right").pack(fill="x", padx=30, pady=8)

        ctk.CTkButton(card, text="حفظ الإعدادات 💾", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#10B981", hover_color="#059669", height=38, command=lambda: messagebox.showinfo("تم", "تم حفظ الإعدادات بنجاح!")).pack(fill="x", padx=30, pady=15)

    # ====================================================
    # 🛒 6. إدارة المنتجات والمخزون
    # ====================================================
    def show_inventory_screen(self):
        if self.current_user_role != "admin": return
        self.create_screen_base("إدارة المنتجات والمخزون 🛒")

        left_frame = ctk.CTkFrame(self.content_area, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#CBD5E1")
        left_frame.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)

        right_frame = ctk.CTkFrame(self.content_area, fg_color="#F8FAFC", width=320, corner_radius=10, border_width=1, border_color="#CBD5E1")
        right_frame.pack(side="right", fill="y", padx=(5, 10), pady=10)
        right_frame.pack_propagate(False)

        ctk.CTkLabel(right_frame, text="بيانات المنتج", font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A").pack(pady=(12, 6))

        self.p_barcode = ctk.CTkEntry(right_frame, placeholder_text="الباركود (Barcode)", height=32, justify="right")
        self.p_barcode.pack(fill="x", padx=15, pady=3)

        self.p_name = ctk.CTkEntry(right_frame, placeholder_text="اسم المنتج", height=32, justify="right")
        self.p_name.pack(fill="x", padx=15, pady=3)

        self.p_category = ctk.CTkEntry(right_frame, placeholder_text="القسم", height=32, justify="right")
        self.p_category.pack(fill="x", padx=15, pady=3)

        self.p_cost = ctk.CTkEntry(right_frame, placeholder_text="سعر الشراء ($)", height=32, justify="right")
        self.p_cost.pack(fill="x", padx=15, pady=3)

        self.p_price = ctk.CTkEntry(right_frame, placeholder_text="سعر البيع ($)", height=32, justify="right")
        self.p_price.pack(fill="x", padx=15, pady=3)

        self.p_stock = ctk.CTkEntry(right_frame, placeholder_text="الكمية في المخزن", height=32, justify="right")
        self.p_stock.pack(fill="x", padx=15, pady=3)

        btn_box = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkButton(btn_box, text="إضافة منتج ➕", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#10B981", hover_color="#059669", height=30, command=self.add_product).pack(fill="x", pady=2)
        ctk.CTkButton(btn_box, text="حفظ التعديل ✏️", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#3B82F6", hover_color="#2563EB", height=30, command=self.update_product).pack(fill="x", pady=2)
        ctk.CTkButton(btn_box, text="حذف المنتج 🗑️", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#EF4444", hover_color="#DC2626", height=30, command=self.delete_product).pack(fill="x", pady=2)
        ctk.CTkButton(btn_box, text="مسح الخانات 🔄", font=ctk.CTkFont(size=10), fg_color="#64748B", hover_color="#475569", height=24, command=self.clear_product_inputs).pack(fill="x", pady=3)

        ctk.CTkLabel(left_frame, text="قائمة المنتجات المسجلة في قاعدة البيانات", font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A").pack(anchor="e", padx=15, pady=(10, 5))

        self.inv_scroll = ctk.CTkScrollableFrame(left_frame, fg_color="transparent")
        self.inv_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.load_products_to_table()

    # ====================================================
    # 🛠️ 7. معالجات الدخول والدعم الأمني والمنتجات
    # ====================================================
    def handle_login(self):
        username = self.user_ent.get().strip()
        password = self.pass_ent.get().strip()

        if not username or not password:
            messagebox.showwarning("تنبيه", "يرجى إدخال اسم المستخدم وكلمة المرور.")
            return

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, role, is_blocked FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()

        if user:
            if user[2] == 1:
                messagebox.showerror("حساب محظور 🚫", "عذراً، هذا الحساب تم حظره من قبل مالك النظام!")
                return

            self.current_user = user[0]
            self.current_user_role = user[1]
            messagebox.showinfo("مرحباً", f"أهلاً بك يا {user[0]}!\nتم تسجيل الدخول بصلاحية: {'أدمن' if user[1] == 'admin' else 'كاشير'}")
            self.show_dashboard_screen()
        else:
            messagebox.showerror("خطأ", "اسم المستخدم أو كلمة المرور غير صحيحة!")

    def handle_register(self):
        user = self.reg_user.get().strip()
        p1 = self.reg_pass.get().strip()
        q = self.reg_question.get().strip()
        ans = self.reg_answer.get().strip()

        if not user or not p1 or not q or not ans:
            messagebox.showwarning("تنبيه", "يرجى ملء كافة البيانات بما فيها سؤال الأمان!")
            return

        try:
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password, sec_question, sec_answer, role, is_blocked) VALUES (?, ?, ?, ?, 'user', 0)", (user, p1, q, ans))
            messagebox.showinfo("نجاح", "تم إنشاء الحساب بنجاح كـ (كاشير)! يتطلب ترقيته من الأدمن.")
            self.show_login_screen()
        except sqlite3.IntegrityError:
            messagebox.showerror("خطأ", "اسم المستخدم هذا مُسجّل بالفعل!")

    def handle_reset_password(self):
        user = self.fp_user.get().strip()
        ans = self.fp_answer.get().strip()
        new_p = self.fp_new_pass.get().strip()

        if not user or not ans or not new_p:
            messagebox.showwarning("تنبيه", "يرجى ملء كافة الحقول المطلوب!")
            return

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? AND sec_answer = ?", (user, ans))
            row = cursor.fetchone()

            if row:
                cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_p, user))
                messagebox.showinfo("نجاح", "تم تحديث كلمة المرور بنجاح!")
                self.show_login_screen()
            else:
                messagebox.showerror("خطأ", "إجابة سؤال الأمان أو اسم المستخدم غير صحيح!")

    def add_product(self):
        barcode = self.p_barcode.get().strip()
        name = self.p_name.get().strip()
        category = self.p_category.get().strip()
        cost_price = self.p_cost.get().strip()
        price = self.p_price.get().strip()
        stock = self.p_stock.get().strip()

        if not barcode or not name or not price or not stock or not cost_price:
            messagebox.showwarning("تنبيه", "يرجى ملء جميع بيانات المنتج بما فيها سعر الشراء!")
            return

        try:
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO products (barcode, name, category, cost_price, price, stock) VALUES (?, ?, ?, ?, ?, ?)",
                               (barcode, name, category, float(cost_price), float(price), int(stock)))
            messagebox.showinfo("نجاح", "تمت إضافة المنتج بنجاح!")
            self.clear_product_inputs()
            self.load_products_to_table()
        except sqlite3.IntegrityError:
            messagebox.showerror("خطأ", "هذا الباركود مُسجل مسبقاً لمنتج آخر!")
        except ValueError:
            messagebox.showerror("خطأ", "يرجى كتابة الأسعار والكمية بأرقام صحيحة.")

    def update_product(self):
        if not self.selected_product_id:
            messagebox.showwarning("تنبيه", "حدد منتجاً أولاً للتعديل.")
            return

        try:
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE products 
                    SET barcode = ?, name = ?, category = ?, cost_price = ?, price = ?, stock = ? 
                    WHERE id = ?
                """, (self.p_barcode.get().strip(), self.p_name.get().strip(), self.p_category.get().strip(), 
                      float(self.p_cost.get().strip()), float(self.p_price.get().strip()), int(self.p_stock.get().strip()), self.selected_product_id))

            messagebox.showinfo("نجاح", "تم تعديل المنتج بنجاح!")
            self.clear_product_inputs()
            self.load_products_to_table()
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر التعديل: {e}")

    def delete_product(self):
        if not self.selected_product_id:
            messagebox.showwarning("تنبيه", "حدد منتجاً للحذف.")
            return

        if messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من حذف المنتج؟"):
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM products WHERE id = ?", (self.selected_product_id,))

            messagebox.showinfo("نجاح", "تم حذف المنتج بنجاح!")
            self.clear_product_inputs()
            self.load_products_to_table()

    def select_inv_item(self, row_data):
        self.selected_product_id = row_data[0]
        self.clear_product_inputs_only()

        self.p_barcode.insert(0, str(row_data[1]))
        self.p_name.insert(0, str(row_data[2]))
        self.p_category.insert(0, str(row_data[3]))
        self.p_cost.insert(0, str(row_data[4]))
        self.p_price.insert(0, str(row_data[5]))
        self.p_stock.insert(0, str(row_data[6]))

    def load_products_to_table(self):
        for item in self.inv_scroll.winfo_children():
            item.destroy()

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, barcode, name, category, cost_price, price, stock FROM products")
            rows = cursor.fetchall()

        for row in rows:
            r_frame = ctk.CTkFrame(self.inv_scroll, fg_color="#F8FAFC", corner_radius=6, height=35, border_width=1, border_color="#CBD5E1")
            r_frame.pack(fill="x", pady=2)
            r_frame.pack_propagate(False)

            ctk.CTkButton(
                r_frame, 
                text="تحديد ✏️", 
                font=ctk.CTkFont(size=10, weight="bold"), 
                width=60, 
                height=24, 
                fg_color="#3B82F6", 
                command=lambda item_data=row: self.select_inv_item(item_data)
            ).pack(side="left", padx=5)

            ent_prod_info = ctk.CTkEntry(r_frame, fg_color="transparent", border_width=0, font=ctk.CTkFont(size=11, weight="bold"), justify="right")
            ent_prod_info.insert(0, f"الباركود: {row[1]} | {row[2]} | {row[3]} | شراء: ${row[4]:.2f} | بيع: ${row[5]:.2f} | المخزون: {row[6]}")
            ent_prod_info.configure(state="readonly")
            ent_prod_info.pack(side="right", fill="x", expand=True, padx=10)

    def clear_product_inputs(self):
        self.selected_product_id = None
        self.clear_product_inputs_only()

    def clear_product_inputs_only(self):
        self.p_barcode.delete(0, 'end')
        self.p_name.delete(0, 'end')
        self.p_category.delete(0, 'end')
        self.p_cost.delete(0, 'end')
        self.p_price.delete(0, 'end')
        self.p_stock.delete(0, 'end')

    def get_live_statistics(self):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products")
            total_products = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM products WHERE stock <= 5")
            low_stock = cursor.fetchone()[0]

            today_date = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("SELECT COUNT(DISTINCT invoice_num), COALESCE(SUM(total_price), 0) FROM sales WHERE date(date_time) = date(?) AND is_reset = 0",
                           (today_date,))
            today_data = cursor.fetchone()

            cursor.execute("SELECT COALESCE(SUM(s.total_price - (s.quantity * COALESCE(s.cost_price, p.cost_price, 0))), 0) FROM sales s LEFT JOIN products p ON s.item_name = p.name WHERE date(s.date_time) = date(?) AND s.is_reset = 0",
                           (today_date,))
            today_profit = cursor.fetchone()[0] or 0.0

        return {
            "total_products": total_products,
            "low_stock": low_stock,
            "today_invoices": today_data[0] or 0,
            "today_revenue": today_data[1] or 0.0,
            "today_profit": float(today_profit),
            "monthly_profit": float(self.calculate_monthly_profit()),
            "treasury": float(self.get_treasury_balance())
        }

    def get_recent_sales(self):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT invoice_num, date_time, item_name, quantity, total_price FROM sales ORDER BY id DESC LIMIT 5")
            rows = cursor.fetchall()
        return rows

    def create_screen_base(self, title_text):
        for widget in self.winfo_children():
            widget.destroy()

        main_box = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=15, border_width=1, border_color="#CBD5E1")
        main_box.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.96, relheight=0.94)

        header = ctk.CTkFrame(main_box, fg_color="#BAE6FD", corner_radius=10, height=55)
        header.pack(fill="x", padx=15, pady=10)
        header.pack_propagate(False)

        ctk.CTkButton(header, text="الرئيسية 🏠", font=ctk.CTkFont(size=11, weight="bold"), fg_color="#1E293B", hover_color="#334155", width=80, height=32, command=self.show_dashboard_screen).pack(side="left", padx=10)
        ctk.CTkLabel(header, text=title_text, font=ctk.CTkFont(size=16, weight="bold"), text_color="#0F172A").pack(side="right", padx=15)

        self.content_area = ctk.CTkFrame(main_box, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True)

    def load_logo(self, parent, image_name="images.jpeg", size=(85, 85), pady=(20, 5)):
        if os.path.exists(image_name):
            try:
                raw_img = Image.open(image_name)
                logo_image = ctk.CTkImage(light_image=raw_img, dark_image=raw_img, size=size)
                ctk.CTkLabel(parent, image=logo_image, text="").pack(pady=pady)
            except Exception:
                self.draw_default_logo(parent)
        else:
            self.draw_default_logo(parent)

    def draw_default_logo(self, parent):
        logo_frame = ctk.CTkFrame(parent, width=70, height=70, corner_radius=35, fg_color="#43A047")
        logo_frame.pack(pady=(15, 5))
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(logo_frame, text="🛒", font=ctk.CTkFont(size=28), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")

if __name__ == "__main__":
    app = SupermarketPOSApp()
    app.mainloop()