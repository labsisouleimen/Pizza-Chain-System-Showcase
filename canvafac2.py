import customtkinter as ctk
import tkinter as tk
import time
import threading
import tkinter.messagebox as msg
from datetime import datetime, timedelta
from customtkinter import CTkImage
from PIL import Image, ImageTk
from tkinter import messagebox, ttk
from escpos.printer import Usb
from escpos.exceptions import USBNotFoundError, DeviceNotFoundError
# from stockk import stock1------
from tkcalendar import DateEntry
from session import Session
import firebase_admin
import os
from firebase_admin import credentials, db
import sqlite3
from souliref import ref_stock1
from charg import cgs
# from soulistock import stock2 ,get_all_categories,get_products_by_category
# from facture import stock2 ,get_all_categories,get_products_by_category,create_db_table,ensure_default_categories_exist
from firebase_config import stock2, get_all_categories, get_products_by_category, create_db_table, ensure_default_categories_exist
# from statis import stat
from statis2 import stat
######################################
charges_initialized = False
stock_initialized = False
ref_initialized = False
statistique_initialized = False

# ملف لحفظ إعدادات الطابعة
PRINTER_SETTINGS_FILE = "printer_settings.txt"

def load_printer_settings():
    """تحميل إعدادات الطابعة من ملف نصي"""
    try:
        if os.path.exists(PRINTER_SETTINGS_FILE):
            with open(PRINTER_SETTINGS_FILE, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
                if len(lines) >= 2:
                    return {
                        "vendor": lines[0].strip(),
                        "product": lines[1].strip()
                    }
    except:
        pass
    return {"vendor": "0x04B8", "product": "0x0202"}  # إعدادات افتراضية

def save_printer_settings(vendor, product):
    """حفظ إعدادات الطابعة في ملف نصي"""
    try:
        with open(PRINTER_SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write(f"{vendor}\n{product}")
        return True
    except:
        return False

def init_firebase():
    global firebase_initialized
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate("pizzalala-7f831-firebase-adminsdk-fbsvc-d4dc3603c1.json")
            firebase_admin.initialize_app(cred, {
                "databaseURL": "https://pizzalala-7f831-default-rtdb.europe-west1.firebasedatabase.app/"
            })
            firebase_initialized = True
            print("✅ Firebase initialized successfully")
    except Exception as e:
        messagebox.showerror("Firebase Error", f"فشل الاتصال بـ Firebase:\n{e}")
        print("Firebase init error:", e)

################################################################           حفظ التواتال         ##################        

def save_totale():
    """إنشاء جداول لحفظ الإجماليات والكميات"""
    conn = sqlite3.connect("sales_totale_3.db")
    c = conn.cursor()
    
    # جدول الإجمالي اليومي المالي
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_totals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            store_name TEXT,
            total_sales INTEGER DEFAULT 0,
            last_updated TEXT,
            UNIQUE(date, store_name)  
        )                 
    """)
    
    # جدول الكميات اليومية للمنتجات
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            store_name TEXT,
            product_name TEXT,
            quantity INTEGER DEFAULT 0,
            last_updated TEXT,
            UNIQUE(date, store_name, product_name)
        )
    """)
    
    conn.commit()
    conn.close()

def update_daily_total_local(sale_amount, store_name, cart_items=None):
    """تحديث الإجماليات والكميات اليومية"""
    try: 
        conn = sqlite3.connect("sales_totale_3.db")
        c = conn.cursor()
        date_only = datetime.now().strftime("%Y-%m-%d")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 🔥 تحديث الإجمالي المالي
        c.execute("SELECT total_sales FROM daily_totals WHERE date=? AND store_name=?", 
                 (date_only, store_name))
        result = c.fetchone()
        
        if result:
            new_total = result[0] + sale_amount
            c.execute("""
                UPDATE daily_totals 
                SET total_sales=?, last_updated=? 
                WHERE date=? AND store_name=?
            """, (new_total, current_time, date_only, store_name))
        else:
            c.execute("""
                INSERT INTO daily_totals (date, store_name, total_sales, last_updated) 
                VALUES(?, ?, ?, ?)
            """, (date_only, store_name, sale_amount, current_time))
        
        # 🔥 تحديث كميات المنتجات إذا تم تمريرها
        if cart_items:
            for item in cart_items:
                product_name = item["name"]
                quantity = item["qty"]
                
                # التحقق إذا كان المنتج موجوداً في هذا اليوم والمتجر
                c.execute("""
                    SELECT quantity FROM daily_products 
                    WHERE date=? AND store_name=? AND product_name=?
                """, (date_only, store_name, product_name))
                
                prod_result = c.fetchone()
                
                if prod_result:
                    # تحديث الكمية
                    new_qty = prod_result[0] + quantity
                    c.execute("""
                        UPDATE daily_products 
                        SET quantity=?, last_updated=? 
                        WHERE date=? AND store_name=? AND product_name=?
                    """, (new_qty, current_time, date_only, store_name, product_name))
                else:
                    # إضافة منتج جديد
                    c.execute("""
                        INSERT INTO daily_products (date, store_name, product_name, quantity, last_updated) 
                        VALUES(?, ?, ?, ?, ?)
                    """, (date_only, store_name, product_name, quantity, current_time))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ خطأ في تحديث التوتال المحلي: {e}")
        return False

def get_daily_total_local(store_name):
    """جلب الإجمالي المالي ليوم معين"""
    try:
        conn = sqlite3.connect("sales_totale_3.db")
        c = conn.cursor()
        date_only = datetime.now().strftime("%Y-%m-%d")
        
        c.execute("SELECT total_sales FROM daily_totals WHERE date=? AND store_name=?", 
                 (date_only, store_name))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        print(f"❌ خطأ في جلب التوتال المحلي: {e}")
        return 0

def get_daily_products_local(store_name, date=None):
    """جلب كميات المنتجات المباعة ليوم معين"""
    try:
        conn = sqlite3.connect("sales_totale_3.db")
        c = conn.cursor()
        
        if not date:
            date_only = datetime.now().strftime("%Y-%m-%d")
        else:
            date_only = date
        
        c.execute("""
            SELECT product_name, quantity 
            FROM daily_products 
            WHERE date=? AND store_name=?
            ORDER BY quantity DESC
        """, (date_only, store_name))
        
        results = c.fetchall()
        conn.close()
        
        # تحويل النتائج إلى قاموس
        products_dict = {}
        for product_name, quantity in results:
            products_dict[product_name] = quantity
            
        return products_dict
    except Exception as e:
        print(f"❌ خطأ في جلب كميات المنتجات: {e}")
        return {}

#################################     الحفظ   ############################    
def init_db():
    """إنشاء قاعدة بيانات المبيعات"""
    conn = sqlite3.connect("sales_22.db")
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            total INTEGER,
            store_name TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_name TEXT,
            quantity INTEGER,
            price INTEGER,
            total INTEGER,
            FOREIGN KEY (sale_id) REFERENCES sales(id)
        )
    """)

    conn.commit()
    conn.close()

#############################################################search##########################
def open_advanced_search_window():
    """نافذة بحث متقدمة تشمل الوقت والمنتجات"""
    adv_window = ctk.CTkToplevel()
    adv_window.title("البحث المتقدم في المبيعات")
    adv_window.geometry("1200x800")
    adv_window.configure(fg_color="#1E1E1E")

    # تبويبات
    tabview = ctk.CTkTabview(adv_window, fg_color="#2B2B2B")
    tabview.pack(fill="both", expand=True, padx=10, pady=10)
    
    # تبويب البحث حسب الوقت
    time_tab = tabview.add("⏰ البحث حسب الوقت")
    
    # تبويب البحث حسب المنتجات
    products_tab = tabview.add("📊 البحث حسب المنتجات")
    
    # تبويب الإحصائيات
    stats_tab = tabview.add("📈 إحصائيات المبيعات")
    
    # ===== تبويب البحث حسب الوقت =====
    time_frame = ctk.CTkFrame(time_tab, fg_color="#2B2B2B")
    time_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # ===== إطار المجموع الكلي في الأعلى =====
    top_total_frame = ctk.CTkFrame(time_frame, fg_color="#3B3B3B", height=40, corner_radius=8)
    top_total_frame.pack(fill="x", padx=10, pady=(0, 10))
    
    top_total_label = ctk.CTkLabel(
        top_total_frame, 
        text="المجموع الكلي: 0 ", 
        text_color="#FFA500", 
        font=("Arial", 16, "bold")
    )
    top_total_label.pack(pady=5)
    
    # إطار التحكم
    control_frame = ctk.CTkFrame(time_frame, fg_color="#3B3B3B", corner_radius=10)
    control_frame.pack(fill="x", padx=10, pady=10)
    
    # تاريخ البداية
    start_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    start_frame.grid(row=0, column=0, padx=10, pady=10)
    ctk.CTkLabel(start_frame, text="من تاريخ:", text_color="white").pack()
    start_date_time = DateEntry(start_frame, date_pattern='yyyy-mm-dd', width=15)
    start_date_time.pack()
    start_time_entry = ctk.CTkEntry(start_frame, placeholder_text="00:00", width=80)
    start_time_entry.pack(pady=5)
    
    # تاريخ النهاية
    end_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    end_frame.grid(row=0, column=1, padx=10, pady=10)
    ctk.CTkLabel(end_frame, text="إلى تاريخ:", text_color="white").pack()
    end_date_time = DateEntry(end_frame, date_pattern='yyyy-mm-dd', width=15)
    end_date_time.pack()
    end_time_entry = ctk.CTkEntry(end_frame, placeholder_text="23:59", width=80)
    end_time_entry.pack(pady=5)
    
    # خيارات سريعة
    quick_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    quick_frame.grid(row=0, column=2, padx=10, pady=10)
    ctk.CTkLabel(quick_frame, text="فترات سريعة:", text_color="white").pack()
    
    def set_today():
        today = datetime.now().strftime("%Y-%m-%d")
        start_date_time.set_date(today)
        end_date_time.set_date(today)
        start_time_entry.delete(0, "end")
        end_time_entry.delete(0, "end")
    
    def set_yesterday():
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date_time.set_date(yesterday)
        end_date_time.set_date(yesterday)
        start_time_entry.delete(0, "end")
        end_time_entry.delete(0, "end")
    
    def set_this_week():
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        start_date_time.set_date(start_of_week.strftime("%Y-%m-%d"))
        end_date_time.set_date(today.strftime("%Y-%m-%d"))
        start_time_entry.delete(0, "end")
        end_time_entry.delete(0, "end")
    
    def set_this_month():
        today = datetime.now()
        start_of_month = today.replace(day=1)
        start_date_time.set_date(start_of_month.strftime("%Y-%m-%d"))
        end_date_time.set_date(today.strftime("%Y-%m-%d"))
        start_time_entry.delete(0, "end")
        end_time_entry.delete(0, "end")
    
    quick_btns_frame = ctk.CTkFrame(quick_frame, fg_color="transparent")
    quick_btns_frame.pack()
    
    ctk.CTkButton(quick_btns_frame, text="اليوم", width=70, command=set_today, 
                  fg_color="#2196F3", height=25).grid(row=0, column=0, padx=2)
    ctk.CTkButton(quick_btns_frame, text="أمس", width=70, command=set_yesterday,
                  fg_color="#2196F3", height=25).grid(row=0, column=1, padx=2)
    ctk.CTkButton(quick_btns_frame, text="هذا الأسبوع", width=70, command=set_this_week,
                  fg_color="#2196F3", height=25).grid(row=1, column=0, padx=2, pady=2)
    ctk.CTkButton(quick_btns_frame, text="هذا الشهر", width=70, command=set_this_month,
                  fg_color="#2196F3", height=25).grid(row=1, column=1, padx=2, pady=2)
    
    # زر البحث
    def search_by_time():
        start_dt = f"{start_date_time.get()} {start_time_entry.get() or '00:00'}"
        end_dt = f"{end_date_time.get()} {end_time_entry.get() or '23:59'}"
        
        conn = sqlite3.connect("sales_22.db")
        c = conn.cursor()
        
        query = """
            SELECT 
                sales.id,
                sales.date,
                sale_items.product_name,
                sale_items.quantity,
                sale_items.price,
                sale_items.total
            FROM sales
            JOIN sale_items ON sales.id = sale_items.sale_id
            WHERE sales.date BETWEEN ? AND ?
            AND sales.store_name = ?
            ORDER BY sales.date DESC
        """
        
        c.execute(query, (start_dt, end_dt, store_name))
        rows = c.fetchall()
        conn.close()
        
        # مسح الجدول القديم
        for i in time_tree.get_children():
            time_tree.delete(i)
        
        total_sum = 0
        invoice_count = 0
        current_invoice = None
        
        for row in rows:
            time_tree.insert("", "end", values=row)
            total_sum += row[5]
            if row[0] != current_invoice:
                invoice_count += 1
                current_invoice = row[0]
        
        time_total_label.configure(text=f"💰 إجمالي المبيعات: {total_sum}  | 📄 عدد الفواتير: {invoice_count} | 📦 عدد المنتجات: {len(rows)}")
        
        # تحديث المجموع الكلي في الأعلى
        top_total_label.configure(text=f"المجموع الكلي: {total_sum} ")
    
    search_btn = ctk.CTkButton(control_frame, text="🔍 بحث", command=search_by_time,
                               fg_color="#FF8C00", width=100, height=35, font=("Arial", 12, "bold"))
    search_btn.grid(row=0, column=3, padx=20)
    
    # جدول النتائج
    time_tree_frame = ctk.CTkFrame(time_frame, fg_color="#2B2B2B")
    time_tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    time_columns = ("id", "date", "product", "qty", "price", "total")
    time_tree = ttk.Treeview(time_tree_frame, columns=time_columns, show="headings", height=20)
    
    for col, title in zip(time_columns, ["رقم الفاتورة", "التاريخ", "المنتج", "الكمية", "السعر", "المجموع"]):
        time_tree.heading(col, text=title)
        time_tree.column(col, width=150, anchor="center")
    
    time_scroll = ttk.Scrollbar(time_tree_frame, orient="vertical", command=time_tree.yview)
    time_tree.configure(yscrollcommand=time_scroll.set)
    time_scroll.pack(side="right", fill="y")
    time_tree.pack(fill="both", expand=True)
    
    time_total_label = ctk.CTkLabel(time_frame, text="💰 إجمالي المبيعات: 0 ", 
                                    text_color="white", font=("Arial", 14, "bold"))
    time_total_label.pack(pady=5)
    
    # ===== تبويب البحث حسب المنتجات =====
    products_frame = ctk.CTkFrame(products_tab, fg_color="#2B2B2B")
    products_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # إطار التحكم في تبويب المنتجات
    prod_control_frame = ctk.CTkFrame(products_frame, fg_color="#3B3B3B", corner_radius=10)
    prod_control_frame.pack(fill="x", padx=10, pady=10)
    
    # تاريخ البداية للمنتجات
    prod_start_frame = ctk.CTkFrame(prod_control_frame, fg_color="transparent")
    prod_start_frame.grid(row=0, column=0, padx=10, pady=10)
    ctk.CTkLabel(prod_start_frame, text="من تاريخ:", text_color="white").pack()
    prod_start_date = DateEntry(prod_start_frame, date_pattern='yyyy-mm-dd', width=15)
    prod_start_date.pack()
    
    # تاريخ النهاية للمنتجات
    prod_end_frame = ctk.CTkFrame(prod_control_frame, fg_color="transparent")
    prod_end_frame.grid(row=0, column=1, padx=10, pady=10)
    ctk.CTkLabel(prod_end_frame, text="إلى تاريخ:", text_color="white").pack()
    prod_end_date = DateEntry(prod_end_frame, date_pattern='yyyy-mm-dd', width=15)
    prod_end_date.pack()
    
    # قائمة المنتجات
    prod_list_frame = ctk.CTkFrame(prod_control_frame, fg_color="transparent")
    prod_list_frame.grid(row=0, column=2, padx=10, pady=10)
    ctk.CTkLabel(prod_list_frame, text="المنتج:", text_color="white").pack()
    
    # جلب قائمة المنتجات
    product_list = []
    try:
        conn = sqlite3.connect("sales_22.db")
        c = conn.cursor()
        c.execute("SELECT DISTINCT product_name FROM sale_items ORDER BY product_name")
        product_list = [row[0] for row in c.fetchall()]
        conn.close()
    except:
        pass
    
    prod_combo = ctk.CTkComboBox(prod_list_frame, values=["جميع المنتجات"] + product_list,
                                width=180, state="readonly")
    prod_combo.set("جميع المنتجات")
    prod_combo.pack()
    
    # زر البحث في المنتجات
    def search_products_tab():
        start_dt = f"{prod_start_date.get()} 00:00"
        end_dt = f"{prod_end_date.get()} 23:59"
        selected_prod = prod_combo.get()
        
        conn = sqlite3.connect("sales_22.db")
        c = conn.cursor()
        
        if selected_prod == "جميع المنتجات":
            query = """
                SELECT 
                    sale_items.product_name,
                    SUM(sale_items.quantity) as total_qty,
                    SUM(sale_items.total) as total_amount,
                    COUNT(DISTINCT sales.id) as invoice_count,
                    sale_items.price
                FROM sales
                JOIN sale_items ON sales.id = sale_items.sale_id
                WHERE sales.date BETWEEN ? AND ?
                AND sales.store_name = ?
                GROUP BY sale_items.product_name
                ORDER BY total_qty DESC
            """
            params = (start_dt, end_dt, store_name)
        else:
            query = """
                SELECT 
                    sale_items.product_name,
                    SUM(sale_items.quantity) as total_qty,
                    SUM(sale_items.total) as total_amount,
                    COUNT(DISTINCT sales.id) as invoice_count,
                    sale_items.price,
                    MIN(sales.date) as first_sale,
                    MAX(sales.date) as last_sale
                FROM sales
                JOIN sale_items ON sales.id = sale_items.sale_id
                WHERE sales.date BETWEEN ? AND ?
                AND sales.store_name = ?
                AND sale_items.product_name = ?
                GROUP BY sale_items.product_name
            """
            params = (start_dt, end_dt, store_name, selected_prod)
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        # مسح الجدول القديم
        for i in prod_tree.get_children():
            prod_tree.delete(i)
        
        # إضافة البيانات الجديدة
        grand_total_qty = 0
        grand_total_amount = 0
        
        for row in rows:
            if selected_prod == "جميع المنتجات":
                product_name, qty, amount, invoices, avg_price = row
                prod_tree.insert("", "end", values=(
                    product_name,
                    f"{qty}",
                    f"{avg_price}",
                    f"{amount} ",
                    f"{invoices}"
                ))
                grand_total_qty += qty
                grand_total_amount += amount
            else:
                product_name, qty, amount, invoices, avg_price, first_sale, last_sale = row
                prod_tree.insert("", "end", values=(
                    product_name,
                    f"{qty}",
                    f"{avg_price} ",
                    f"{amount} ",
                    f"{invoices}",
                    first_sale[:16] if first_sale else "",
                    last_sale[:16] if last_sale else ""
                ))
                grand_total_qty = qty
                grand_total_amount = amount
        
        if selected_prod == "جميع المنتجات":
            prod_summary_label.configure(text=f"📈 عدد المنتجات: {len(rows)} | إجمالي الكمية: {grand_total_qty} | إجمالي المبلغ: {grand_total_amount} ")
        else:
            prod_summary_label.configure(text=f"📊 المنتج: {selected_prod} | الكمية المباعة: {grand_total_qty} | إجمالي المبلغ: {grand_total_amount} ")
    
    prod_search_btn = ctk.CTkButton(prod_control_frame, text="🔍 بحث", command=search_products_tab,
                                   fg_color="#FF8C00", width=100, height=35)
    prod_search_btn.grid(row=0, column=3, padx=20)
    
    # جدول نتائج المنتجات
    prod_tree_frame = ctk.CTkFrame(products_frame, fg_color="#2B2B2B")
    prod_tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    prod_columns = ("product", "qty", "price", "amount", "invoices", "first_sale", "last_sale")
    prod_tree = ttk.Treeview(prod_tree_frame, columns=prod_columns, show="headings", height=15)
    
    # تعيين العناوين الافتراضية
    prod_tree.heading("product", text="المنتج")
    prod_tree.heading("qty", text="الكمية")
    prod_tree.heading("price", text="السعر المتوسط")
    prod_tree.heading("amount", text="المبلغ الإجمالي")
    prod_tree.heading("invoices", text="عدد الفواتير")
    
    prod_tree.column("product", width=200, anchor="center")
    prod_tree.column("qty", width=100, anchor="center")
    prod_tree.column("price", width=120, anchor="center")
    prod_tree.column("amount", width=150, anchor="center")
    prod_tree.column("invoices", width=100, anchor="center")
    
    # إخفاء الأعمدة الإضافية مؤقتاً
    prod_tree["displaycolumns"] = ("product", "qty", "price", "amount", "invoices")
    
    prod_scroll = ttk.Scrollbar(prod_tree_frame, orient="vertical", command=prod_tree.yview)
    prod_tree.configure(yscrollcommand=prod_scroll.set)
    prod_scroll.pack(side="right", fill="y")
    prod_tree.pack(fill="both", expand=True)
    
    prod_summary_label = ctk.CTkLabel(products_frame, text="حدد الفترة والمنتج للبحث",
                                     text_color="white", font=("Arial", 14))
    prod_summary_label.pack(pady=5)
    
    # ===== تبويب الإحصائيات =====
    stats_frame = ctk.CTkFrame(stats_tab, fg_color="#2B2B2B")
    stats_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    def load_statistics():
        """تحميل إحصائيات المبيعات"""
        try:
            conn = sqlite3.connect("sales_22.db")
            c = conn.cursor()
            
            # اليوم
            today = datetime.now().strftime("%Y-%m-%d")
            c.execute("""
                SELECT SUM(total) FROM sales 
                WHERE DATE(date) = ? AND store_name = ?
            """, (today, store_name))
            today_sales = c.fetchone()[0] or 0
            
            # الأسبوع
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            c.execute("""
                SELECT SUM(total) FROM sales 
                WHERE DATE(date) >= ? AND store_name = ?
            """, (week_ago, store_name))
            week_sales = c.fetchone()[0] or 0
            
            # الشهر
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            c.execute("""
                SELECT SUM(total) FROM sales 
                WHERE DATE(date) >= ? AND store_name = ?
            """, (month_ago, store_name))
            month_sales = c.fetchone()[0] or 0
            
            # العام
            year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            c.execute("""
                SELECT SUM(total) FROM sales 
                WHERE DATE(date) >= ? AND store_name = ?
            """, (year_ago, store_name))
            year_sales = c.fetchone()[0] or 0
            
            # المنتجات الأكثر مبيعاً
            c.execute("""
                SELECT product_name, SUM(quantity) as total_qty
                FROM sale_items
                JOIN sales ON sale_items.sale_id = sales.id
                WHERE sales.store_name = ?
                GROUP BY product_name
                ORDER BY total_qty DESC
                LIMIT 10
            """, (store_name,))
            top_products = c.fetchall()
            
            # أفضل أيام المبيعات
            c.execute("""
                SELECT DATE(date), SUM(total) as daily_total
                FROM sales
                WHERE store_name = ?
                GROUP BY DATE(date)
                ORDER BY daily_total DESC
                LIMIT 10
            """, (store_name,))
            best_days = c.fetchall()
            
            conn.close()
            
            # تحديث العناوين
            today_label.configure(text=today_sales)
            week_label.configure(text=week_sales)
            month_label.configure(text=f"{month_sales} ")
            year_label.configure(text=f"{year_sales} ")
            
            # تحديث جدول المنتجات
            for i in top_tree.get_children():
                top_tree.delete(i)
            
            for product, qty in top_products:
                top_tree.insert("", "end", values=(product, qty))
            
            # تحديث جدول الأيام
            for i in days_tree.get_children():
                days_tree.delete(i)
            
            for date_str, daily_total in best_days:
                days_tree.insert("", "end", values=(date_str, f"{daily_total}"))
                
        except Exception as e:
            print(f"خطأ في تحميل الإحصائيات: {e}")
    
    # بطاقات الإحصائيات
    stats_cards = ctk.CTkFrame(stats_frame, fg_color="transparent")
    stats_cards.pack(fill="x", padx=10, pady=10)
    
    # بطاقة اليوم
    today_card = ctk.CTkFrame(stats_cards, fg_color="#4CAF50", corner_radius=10, width=180, height=100)
    today_card.pack(side="left", padx=10, pady=10)
    ctk.CTkLabel(today_card, text="💰 مبيعات اليوم", text_color="white", 
                 font=("Arial", 14, "bold")).pack(pady=10)
    today_label = ctk.CTkLabel(today_card, text="0 ", text_color="white", 
                               font=("Arial", 20, "bold"))
    today_label.pack(pady=5)
    
    # بطاقة الأسبوع
    week_card = ctk.CTkFrame(stats_cards, fg_color="#2196F3", corner_radius=10, width=180, height=100)
    week_card.pack(side="left", padx=10, pady=10)
    ctk.CTkLabel(week_card, text="📅 مبيعات الأسبوع", text_color="white", 
                 font=("Arial", 14, "bold")).pack(pady=10)
    week_label = ctk.CTkLabel(week_card, text="0 ", text_color="white", 
                              font=("Arial", 20, "bold"))
    week_label.pack(pady=5)
    
    # بطاقة الشهر
    month_card = ctk.CTkFrame(stats_cards, fg_color="#FF9800", corner_radius=10, width=180, height=100)
    month_card.pack(side="left", padx=10, pady=10)
    ctk.CTkLabel(month_card, text="📆 مبيعات الشهر", text_color="white", 
                 font=("Arial", 14, "bold")).pack(pady=10)
    month_label = ctk.CTkLabel(month_card, text="0 ", text_color="white", 
                               font=("Arial", 20, "bold"))
    month_label.pack(pady=5)
    
    # بطاقة العام
    year_card = ctk.CTkFrame(stats_cards, fg_color="#9C27B0", corner_radius=10, width=180, height=100)
    year_card.pack(side="left", padx=10, pady=10)
    ctk.CTkLabel(year_card, text="📊 مبيعات العام", text_color="white", 
                 font=("Arial", 14, "bold")).pack(pady=10)
    year_label = ctk.CTkLabel(year_card, text="0 ", text_color="white", 
                              font=("Arial", 20, "bold"))
    year_label.pack(pady=5)
    
    # إطار المنتجات والأيام
    tables_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
    tables_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # المنتجات الأكثر مبيعاً
    top_frame = ctk.CTkFrame(tables_frame, fg_color="#3B3B3B", corner_radius=10)
    top_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    
    ctk.CTkLabel(top_frame, text="🏆 المنتجات الأكثر مبيعاً", 
                 text_color="white", font=("Arial", 16, "bold")).pack(pady=10)
    
    top_tree = ttk.Treeview(top_frame, columns=("product", "quantity"), show="headings", height=12)
    top_tree.heading("product", text="المنتج")
    top_tree.heading("quantity", text="الكمية المباعة")
    top_tree.column("product", width=250, anchor="center")
    top_tree.column("quantity", width=150, anchor="center")
    top_tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # أفضل أيام المبيعات
    days_frame = ctk.CTkFrame(tables_frame, fg_color="#3B3B3B", corner_radius=10)
    days_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)
    
    ctk.CTkLabel(days_frame, text="📅 أفضل أيام المبيعات", 
                 text_color="white", font=("Arial", 16, "bold")).pack(pady=10)
    
    days_tree = ttk.Treeview(days_frame, columns=("date", "total"), show="headings", height=12)
    days_tree.heading("date", text="التاريخ")
    days_tree.heading("total", text="إجمالي المبيعات")
    days_tree.column("date", width=150, anchor="center")
    days_tree.column("total", width=150, anchor="center")
    days_tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    # زر تحديث الإحصائيات
    refresh_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
    refresh_frame.pack(pady=10)
    
    refresh_btn = ctk.CTkButton(refresh_frame, text="🔄 تحديث الإحصائيات", 
                                command=load_statistics, fg_color="#9C27B0",
                                width=200, height=40, font=("Arial", 14, "bold"))
    refresh_btn.pack()
    
    # تحميل الإحصائيات عند فتح النافذة
    adv_window.after(100, load_statistics)
#---------- الأعدادات و تصميم ألوان الواجهة -------------------------------#
ctk.set_appearance_mode("light")
BG_COLOR = "#063C66"
ACCENT_COLOR = "#FFA500"

#------- Login Window ------------------------------------------------#
Login = ctk.CTk("#EF5726")
Login.title("Restaurant Login")
Login.geometry("400x500")

#--------------- Logo Login ---------------------------------------------------#
icon_image = ctk.CTkImage(
    light_image=Image.open("imglog/photo_2025-11-30_21-49-13.jpg"),
    dark_image=Image.open("imglog/photo_2025-11-30_21-49-13.jpg"),
    size=(150, 150)
)
icon_frame = ctk.CTkFrame(Login, fg_color="#EF5726")
icon_frame.pack(pady=40)
icon_label = ctk.CTkLabel(icon_frame, image=icon_image, text="")
icon_label.pack()

#-------------------------------------------------------------------------------------------#

# حقل البريد الإلكتروني
admin_entry = ctk.CTkEntry(Login, placeholder_text="Admin Name", width=260, height=40, text_color="black", corner_radius=50, font=("Arial", 13))
admin_entry.pack(pady=15)

adminicon = ctk.CTkImage(light_image=Image.open("imglog/user22.png"), size=(30, 30))
adminicon1 = ctk.CTkLabel(Login, image=adminicon, text="")
adminicon1.place(x=26, y=250)

# حقل كلمة المرور
password_entry = ctk.CTkEntry(Login, placeholder_text="Password", show="•", width=260, height=40, text_color="black", corner_radius=50, font=("Arial", 13))
password_entry.pack(pady=15)

passwordicon = ctk.CTkImage(light_image=Image.open("imglog/padlock.png"), size=(30, 30))
passwordicon1 = ctk.CTkLabel(Login, image=passwordicon, text="")
passwordicon1.place(x=26, y=320)

#----------------- Page Principale -------------------------------------------------------------------#
active_target = None  # "display1" أو "table_qte"
selected_item = None
previous_item = None

def pageprinc():
    global active_target, selected_item, previous_item, charges_initialized, store_name
    global category_title_frame, category_image_label, category_title_label
    global current_category_title, current_category_image
    
    
    ctk.set_appearance_mode("light")
    pageprincipale = ctk.CTk("#E5E5E5")
    
    pageprincipale.title("Admin")
    screen_width = pageprincipale.winfo_screenwidth()
    screen_height = pageprincipale.winfo_screenheight()
    pageprincipale.geometry(f"{screen_width}x{screen_height}")

    # تهيئة المتغيرات العالمية للعنوان
    category_title_frame = None
    category_image_label = None
    category_title_label = None

    #------------------- Frame List ---------------------------------------------------------#
    framelist = ctk.CTkFrame(master=pageprincipale, width=120, fg_color="#FFA500", corner_radius=0)
    framelist.pack(side="left", fill="y")
    
    # 🔥 دالة جديدة مركزية لإخفاء جميع الإطارات
    def hide_all_frames():
        """إخفاء جميع الإطارات الرئيسية"""
        frames_to_hide = [
            Framecatégorie, Frame, frameliste, frameliste1, frameliste2,
            framelistecharges, framechargestableau, frameliststock, 
            frmaetableaustock, framelabletotal,
            frmaetableaustock, framelabletotal, framestati
        ]
        
        for frame in frames_to_hide:
            try:
                frame.pack_forget()
            except:
                pass
        
        # إخفاء إطار العنوان
        if category_title_frame:
            category_title_frame.place_forget()
    
    def show_category_title():
        """عرض عنوان الكاتيغوري مع الصورة"""
        global category_title_frame, category_image_label, category_title_label
        
        # إخفاء الإطار الحالي إذا كان موجوداً
        if category_title_frame:
            category_title_frame.place_forget()
        
        # إنشاء إطار للعنوان والصورة
        category_title_frame = ctk.CTkFrame(
            pageprincipale, 
            fg_color="transparent", 
            height=60,
            width=screen_width-160  # تمرير العرض في المنشئ
        )
        category_title_frame.place(x=140, y=5)
        
        # صورة رمز الكاتيغوري (بحجم أكبر)
        category_image = ctk.CTkImage(
            light_image=Image.open("imglog/photo_2025-11-30_21-49-13.jpg"),
            dark_image=Image.open("imglog/photo_2025-11-30_21-49-13.jpg"),
            size=(90, 80)  # حجم أكبر
        )
        
        # وضع الصورة
        category_image_label = ctk.CTkLabel(category_title_frame, image=category_image, text="")
        category_image_label.pack(side="left", padx=(0, 18))
        
        # وضع العنوان
        category_title_label = ctk.CTkLabel(
            category_title_frame, 
            text="Catégorie", 
            text_color="black", 
            font=ctk.CTkFont(family="Arial", size=28, weight="bold")  # حجم خط أكبر
        )
        category_title_label.pack(side="left")
    def update_category_title(title,image_path=None):
         
         """تحديث نص العنوان فقط"""
         global category_title_label, current_category_title
         global current_category_image
         if image_path:

            current_category_image = image_path
         else:
            current_category_image = "imglog/photo_2025-11-30_21-49-13.jpg"
    
         current_category_title = title
         if category_title_label:
            category_title_label.configure(text=current_category_title)  
         if category_image_label:
              
              try:
                  
                  if os.path.exists(current_category_image):

                    new_image = ctk.CTkImage(
                    light_image=Image.open(current_category_image),
                    dark_image=Image.open(current_category_image),
                    size=(90, 80)
                     )
                  else:
                    new_image = ctk.CTkImage(
                    light_image=Image.open("imglog/catering.png"),
                    dark_image=Image.open("imglog/catering.png"),
                    size=(90, 80)
                )
                  category_image_label.configure(image=new_image)
              except:

              
            # في حالة خطأ، استخدم الصورة الافتراضية
                default_image = ctk.CTkImage(
                     light_image=Image.open("imglog/catering.png"),
                dark_image=Image.open("imglog/catering.png"),
                size=(90, 80)     )
                category_image_label.configure(image=default_image)
    
    def vente():
        hide_all_frames()
        show_category_title()  # عرض العنوان أولاً
        update_category_title("Catégorie","imglog/photo_2025-11-30_21-49-13.jpg")
        Framecatégorie.pack(side="left", fill="both", padx=8, pady=90)
        Frame.pack(side="left", fill="both", padx=10, pady=0)

    frameliste = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=75)
    frameliste1 = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=75)
    frameliste2 = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=75)
    
    #scroll_yt2 = ctk.CTkScrollbar(frameliste2, width=22)
    #scroll_yt2.pack(side="right", fill="y")
    
    colum = ("Num", "Désignation", "Prix de vente","Catégorie")
    style2 = ttk.Style()
    style2.theme_use("clam")
    style2.configure("Treeview2.Treeview",
                    background="#f8f9fa",
                    foreground="black",
                    rowheight=40,
                    fieldbackground="#f8f9fa",
                    font=("Arial", 12))
    style2.map("Treeview2.Treeview", background=[("selected", "#b0c4de")])
    tabl = ttk.Treeview(frameliste2, columns=colum, show="headings", height=10, style="Treeview2.Treeview")
    for cl in colum:
        tabl.heading(cl, text=cl)
        tabl.column(cl, anchor="center")
    tabl.column("Num", width=10)
    tabl.column("Désignation", width=290)
    tabl.column("Catégorie", width=200)
    tabl.column("Prix de vente", width=100)
    
    
    tabl.tag_configure("oddrow", background="#ffffff")
    tabl.tag_configure("evenrow", background="#e6e6e6")
    
    #scroll_yt2.configure(command=tabl.yview)
    
    def stock():
        global stock_initialized
        hide_all_frames()
      
        if not stock_initialized:
            stock2(screen_width, frameliste, frameliste1, frameliste2, tabl)
            stock_initialized = True
            
        frameliste.pack(side="top", fill="x", padx=10, pady=15)
        frameliste1.pack(side="top", fill="x", padx=10, pady=15)
        frameliste2.pack(side="top", fill="both", expand=True, padx=10, pady=15)
        tabl.pack(side="top", fill="both", expand=True, padx=5, pady=5)
    
    #--------------------------------- Ref stock --------------------------------------#
    frameliststock = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=70)
    frmaetableaustock = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=70)
    framelabletotal = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=75)
    
    #------------------ جدول الخاص ب charges --------------------------------------------------#
    #scroll_yt4 = ctk.CTkScrollbar(frmaetableaustock)
    #scroll_yt4.pack(side="right", fill="y")
    
    colum2 = ("اسم المنتج", "الكمية", "السعر")
    style4 = ttk.Style()
    style4.theme_use("clam")
    style4.configure("Treeview4.Treeview",
                    background="#f8f9fa",
                    foreground="black",
                    rowheight=40,
                    fieldbackground="#f8f9fa",
                    font=("Arial", 12))
    style4.map("Treeview4.Treeview", background=[("selected", "#b0c4de")])
    tablrefcharg = ttk.Treeview(frmaetableaustock, columns=colum2, show="headings", height=10, style="Treeview4.Treeview")
    for cll1 in colum2:
        tablrefcharg.heading(cll1, text=cll1)
        tablrefcharg.column(cll1, anchor="center")
    
    tablrefcharg.column("اسم المنتج", width=290)
    tablrefcharg.column("السعر", width=100)
    tablrefcharg.column("الكمية", width=100)
    
    tablrefcharg.tag_configure("oddrow", background="#ffffff")
    tablrefcharg.tag_configure("evenrow", background="#e6e6e6")
    
    #croll_yt4.configure(command=tablrefcharg.yview)
    
    def ref_stock():
        global ref_initialized
        hide_all_frames()
    
        if not ref_initialized:
            ref_stock1(screen_width, frameliststock, frmaetableaustock, tablrefcharg, framelabletotal)
            ref_initialized = True
    
        frameliststock.pack(side="top", fill="x", padx=10, pady=15)
        frmaetableaustock.pack(side="top", fill="x", padx=10, pady=15)
        tablrefcharg.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        framelabletotal.pack(side="top", fill="x", padx=10, pady=15)
    
    ############################خاص بالنفقات charges
    framelistecharges = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=85)
    framechargestableau = ctk.CTkFrame(master=pageprincipale, fg_color="#B3B3B3", height=65)

    #scroll_yt3 = ctk.CTkScrollbar(framechargestableau)
    #scroll_yt3.pack(side="right", fill="y")
    
    colum1 = ("اسم النفقة", "السعر", "الكمية")
    style3 = ttk.Style()
    style3.theme_use("clam")
    style3.configure("Treeview3.Treeview",
                    background="#f8f9fa",
                    foreground="black",
                    rowheight=40,
                    fieldbackground="#f8f9fa",
                    font=("Arial", 12))
    style3.map("Treeview3.Treeview", background=[("selected", "#b0c4de")])
    tablcharg = ttk.Treeview(framechargestableau, columns=colum1, show="headings", height=15, style="Treeview3.Treeview")
    for cll in colum1:
        tablcharg.heading(cll, text=cll)
        tablcharg.column(cll, anchor="center")
    
    tablcharg.column("اسم النفقة", width=290)
    tablcharg.column("السعر", width=290)
    tablcharg.column("الكمية", width=100)
    
    tablcharg.tag_configure("oddrow", background="#ffffff")
    tablcharg.tag_configure("evenrow", background="#e6e6e6")
    
    #scroll_yt3.configure(command=tablcharg.yview)

    def charges():
        global charges_initialized
        hide_all_frames()
      
        if not charges_initialized:
            cgs(screen_width, framelistecharges, framechargestableau, tablcharg)
            charges_initialized = True
        framelistecharges.pack(side="top", fill="x", padx=10, pady=15)
        framechargestableau.pack(side="top", fill="x", padx=10, pady=15)
        tablcharg.pack(side="top", fill="both", expand=True, padx=5, pady=5)

    #############################
    #------------------------ Frame Statistique -----------------------------------------------#
    framestati = ctk.CTkFrame(master=pageprincipale, width=800, fg_color="#063C66", corner_radius=10)
    
    def stati():
        global statistique_initialized
        hide_all_frames()       
        if not statistique_initialized:
            stat(screen_width, framestati)
            statistique_initialized = True
        framestati.pack(side="left", fill="both", padx=10, pady=90)
    
    ListBut = [("Vente", "white", "white", "black", "imglog/vente.png", vente),
               ("Stock", "white", "white", "black", "imglog/stock.png", stock),
               ("Charges", "white", "white", "black", "imglog/charges.png", charges),
               ("Ref Stock", "white", "white", "black", "imglog/ref_stock.png", ref_stock),
               ("Statistique", "white", "white", "black", "imglog/stati.png", stati)]
    
    y_pos1 = 10
    for tex1, colr1, hovr1, txt_colr1, icon, cmd in ListBut:
        pil_list = Image.open(icon)
        imglist = CTkImage(light_image=pil_list, dark_image=pil_list, size=(50, 50))
        btn2 = ctk.CTkButton(framelist, text=tex1, image=imglist, compound="top", fg_color=colr1, hover_color=hovr1, text_color=txt_colr1, border_width=1, border_color="black", corner_radius=80//2, width=60, height=60, font=("Arial", 12, "bold"), command=cmd)
        btn2.place(y=y_pos1, x=5)
        y_pos1 += 150
    
    framelist.pack_propagate(False)

    #-------------------- Frame catégorie ---------------------------------------------------#
    Framecatégorie = ctk.CTkFrame(master=pageprincipale, width=380, fg_color="#063C66", corner_radius=10)

    #--------------------------------- Frame liste catégorie ---------------------------------------------------------------------------#
    Framelistecatégorie = ctk.CTkScrollableFrame(master=Framecatégorie, width=380, height=500, fg_color="transparent"
      )
    Framelistecatégorie._scrollbar.configure(width=20)
    Framelistecatégorie.pack(pady=25, fill="both", expand=True)
    Framecatégorie.pack_propagate(False)
    Framelistecatégorie.pack_propagate(False)

    #-------------------- Frame Table Vente  --------------------------------------------- #
    Frame = ctk.CTkFrame(master=pageprincipale, width=480, fg_color="#063C66")

    framet = ctk.CTkFrame(master=Frame, width=500, height=400, fg_color="transparent")
    framet.pack(fill="both", padx=3, pady=10)

    columnst = ("Désignation", "Prix de vente", "Qté", "Total")
    scroll_yt = ctk.CTkScrollbar(framet,width=20)
    scroll_yt.pack(side="right", fill="y")
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview",
                    background="#f8f9fa",
                    foreground="black",
                    rowheight=35,
                    fieldbackground="#f8f9fa",
                    font=("Arial", 12))
    style.map("Treeview", background=[("selected", "#b0c4de")])

    tablet = ttk.Treeview(framet, columns=columnst, yscrollcommand=scroll_yt.set, show="headings", height=10)
    for colt in columnst:
        tablet.heading(colt, text=colt)
        tablet.column(colt, anchor="center")
    tablet.column("Désignation", width=180)
    tablet.column("Prix de vente", width=80)
    tablet.column("Qté", width=40)
    tablet.column("Total", width=100)
    tablet.pack(side="top", fill="both", expand=True, padx=5, pady=5)

    tablet.tag_configure("oddrow", background="#ffffff")
    tablet.tag_configure("evenrow", background="#e6e6e6")

    scroll_yt.configure(command=tablet.yview)

    totallabel = ctk.CTkLabel(master=Frame, text="Total", text_color="#FFA500", font=ctk.CTkFont(family="Arial", size=20, weight="bold"))
    totallabel.place(x=17, y=400)

    displaytotal = ctk.CTkEntry(master=Frame, width=115, font=("Digital-7", 20, "bold"), justify="right", fg_color="#CCFFCC")
    displaytotal.place(x=160, y=400)

    Montant_paye = ctk.CTkLabel(master=Frame, text="Montant payé", text_color="#FFA500", font=ctk.CTkFont(family="Arial", size=20, weight="bold"))
    Montant_paye.place(x=17, y=440)
    
    Montant_reste = ctk.CTkLabel(master=Frame, text="Qui Reste", text_color="#FFA500", font=ctk.CTkFont(family="Arial", size=20, weight="bold"))
    Montant_reste.place(x=17, y=480)
    
    display1 = ctk.CTkEntry(master=Frame, width=115, font=("Digital-7", 20, "bold"), justify="right", fg_color="#CCFFCC")
    display1.place(x=160, y=440)

    display2 = ctk.CTkEntry(master=Frame, width=115, font=("Digital-7", 20, "bold"), justify="right", fg_color="#CCFFCC")
    display2.place(x=160, y=480)

    #------------------------------- Clavier -------------------------------------------------------------------#
    keypad_frame = ctk.CTkFrame(Frame, fg_color="#042B4D", corner_radius=10)
    keypad_frame.place(x=282, y=405)

    #------------------- التحكم في الإدخال عبر لوحة الأرقام -------------------#
    def set_active_target_display1(event=None):
        global active_target, selected_item
        active_target = "display1"
        if selected_item:
            tablet.tag_configure("highlight", background="")
            tablet.item(selected_item, tags=())
            selected_item = None

    def set_active_target_qte(event):
        """عند الضغط على خلية Qté فقط"""
        global active_target, selected_item, previous_item

        region = tablet.identify_region(event.x, event.y)
        column = tablet.identify_column(event.x)
        item = tablet.identify_row(event.y)
        
        if previous_item and previous_item not in tablet.get_children():
            previous_item = None
        
        if region == "cell" and column == "#3":
            active_target = "table_qte"
            if previous_item:
                vals = list(tablet.item(previous_item, "values"))
                index = tablet.get_children().index(previous_item)
                tag = "evenrow" if index % 2 == 0 else "oddrow"
                tablet.item(previous_item, tags=(tag,))
            selected_item = item
            tablet.tag_configure("highlight", background="#FFF7B0")
            tablet.item(selected_item, tags=("highlight",))
            previous_item = selected_item
            vals = list(tablet.item(selected_item, "values"))
            if vals[2] == "1":
                vals[2] = ""
                tablet.item(selected_item, values=vals)
        else:
            active_target = None
            if previous_item and previous_item in tablet.get_children():
                index = tablet.get_children().index(previous_item)
                tag = "evenrow" if index % 2 == 0 else "oddrow"
                tablet.item(previous_item, tags=(tag,))
            previous_item = None
            selected_item = None

    display1.bind("<FocusIn>", set_active_target_display1)
    tablet.bind("<Double-1>", set_active_target_qte)

    #########################################################################
    def upload_sale_to_firebase(cart_items, total_sum):
        """رفع بيانات البيع إلى Firebase"""
        try:
            if not firebase_admin._apps:
                return
            start_time = time.time()
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            date_only = datetime.now().strftime("%Y-%m-%d")
            daylaily_totale = get_daily_total_local(store_name)
        
            sales_ref = db.reference(f"sales/{store_name}")
            sales_ref.child(date_only).update({"totale": daylaily_totale})
            
            end_time = time.time()
            upload_time = round((end_time - start_time) * 1000, 2)
            print(f"✅ تم رفع التوتال: {daylaily_totale} دج | الوقت: {upload_time} ms")
        
        except Exception as e:
            pass
    def upload_sale_to_firebase_async(cart_items, total_sum):
        """رفع بيانات البيع إلى Firebase - من القاعدة المحلية فقط"""
        try:
            def firebase_worker():
                try:
                    if not firebase_admin._apps:
                       return
                
                    date_only = datetime.now().strftime("%Y-%m-%d")
                
                # 1. جلب التوتال من القاعدة المحلية
                    daylaily_totale = get_daily_total_local(store_name)
                
                # 2. جلب كميات المنتجات من القاعدة المحلية
                    products_from_local = get_daily_products_local(store_name, date_only)
                
                # 3. رفع إلى Firebase
                    sales_ref = db.reference(f"salesii/{store_name}/{date_only}")
                
                # رفع التوتال
                    sales_ref.child("totale").set(daylaily_totale)
                
                # رفع المنتجات
                    for product_name, quantity in products_from_local.items():
                        sales_ref.child(product_name).set(quantity)
                
                except Exception as e:
                   
                   print(f"⚠️ خطأ في رفع المبيعات: {e}")
        
            thread = threading.Thread(target=firebase_worker, daemon=True)
            thread.start()
        
        except Exception as e:
           
           print(f"❌ خطأ في تشغيل الخيط: {e}")
       
    #------------------- دوال الأزرار الرقمية -------------------#
    def add_number(num):
        global active_target, selected_item
        if active_target == "display1":
            display1.insert("end", num)
            display1.event_generate("<KeyRelease>")
        elif active_target == "table_qte" and selected_item:
            vals = list(tablet.item(selected_item, "values"))
            if len(vals) >= 3:
                current_qte = str(vals[2])
                if current_qte.isdigit():
                    new_qte = current_qte + str(num)
                else:
                    new_qte = str(num)
                vals[2] = new_qte
                price = int(str(vals[1]).replace("DA", "").strip() or 0)
                vals[3] = f"{price * int(new_qte)} "
                tablet.item(selected_item, values=vals)
                update_total_sum()

    def clear_display():
        global active_target, selected_item
        if active_target == "display1":
            display1.delete(0, "end")
        elif active_target == "table_qte" and selected_item:
            vals = list(tablet.item(selected_item, "values"))
            vals[2] = "0"
            vals[3] = "0 DA"
            tablet.item(selected_item, values=vals)
            update_total_sum()

    def delete_last():
        global active_target, selected_item
        if active_target == "display1":
            current_text = display1.get()
            display1.delete(0, "end")
            display1.insert(0, current_text[:-1])
            display1.event_generate("<KeyRelease>")
        elif active_target == "table_qte" and selected_item:
            vals = list(tablet.item(selected_item, "values"))
            current_qte = str(vals[2])
            new_qte = current_qte[:-1] if len(current_qte) > 0 else "0"
            vals[2] = new_qte
            price = int(str(vals[1]).replace("DA", "").strip() or 0)
            vals[3] = f"{price * int(new_qte or 0)} DA"
            tablet.item(selected_item, values=vals)
            update_total_sum()

    def update_total_sum():
        """تحديث المجموع الكلي للجدول"""
        total_sum = 0
        for child in tablet.get_children():
            vals = tablet.item(child)["values"]
            if len(vals) == 4:
                val = str(vals[3]).replace("DA", "").strip()
                try:
                    total_sum += int(val)
                except ValueError:
                    pass
        displaytotal.configure(state="normal")
        displaytotal.delete(0, "end")
        displaytotal.insert(0, f"{total_sum} ")
        displaytotal.configure(state="readonly")

    num = [
        ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
        ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
        ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
        ("C", 3, 0), ("0", 3, 1), ("⌫", 3, 2)
    ]

    for (text, row, col) in num:
        if text.isdigit():
            btn = ctk.CTkButton(keypad_frame, text=text, width=60, height=60, fg_color="#FFA500",
                                hover_color="#E67300", font=("Arial", 20, "bold"),
                                command=lambda t=text: add_number(t))
        elif text == "C":
            btn = ctk.CTkButton(keypad_frame, text=text, width=60, height=60, fg_color="#FF3333",
                                hover_color="#CC0000", font=("Arial", 20, "bold"),
                                command=clear_display)
        else:
            btn = ctk.CTkButton(keypad_frame, text=text, width=60, height=60, fg_color="#999999",
                                hover_color="#666666", font=("Arial", 20, "bold"),
                                command=delete_last)
        btn.grid(row=row, column=col, padx=5, pady=5)
    
    Frame.pack_propagate(False)
    
    def update_difference(event=None):
        try:
            total_text = displaytotal.get().replace("DA", "").strip()
            total = int(total_text) if total_text else 0
            val1_text = display1.get().strip()
            val1 = int(val1_text) if val1_text else 0
            result = val1 - total
            display2.configure(state="normal")
            display2.delete(0, "end")
            display2.insert(0, f"{result} ")
            display2.configure(state="readonly")
        except ValueError:
            pass
    
    display1.bind("<KeyRelease>", update_difference)

    #-------------------- Frame sup/.......................................................... #
    category_selected_item = None

    def on_category_click(event):
        global category_selected_item
        item = tablet.identify_row(event.y)
        column = tablet.identify_column(event.x)
        if item and column == "#1":
            category_selected_item = item

    def supprimer():
        global category_selected_item
        if category_selected_item:
            tablet.delete(category_selected_item)
            category_selected_item = None
            update_total_sum()
        else:
            messagebox.showwarning("تحذير", "الرجاء تحديد طلب للحذف")

    tablet.bind("<Button-1>", on_category_click)
    
    def vider():
        for item in tablet.get_children():
            tablet.delete(item)
        update_total_sum()
    
    def Nouv():
        init_db()
        save_totale()
        try:
            cart_items = []
            for child in tablet.get_children():
                values = tablet.item(child, "values")
                if len(values) >= 4:
                    qty = int(values[2]) if str(values[2]).isdigit() else 0
                    price = int(str(values[1]).replace("DA", "").strip() or 0)
                    total = int(str(values[3]).replace("DA", "").strip() or 0)
                    cart_items.append({
                        "name": values[0],
                        "qty": qty,
                        "price": price,
                        "total": total
                    })

            if not cart_items:
                messagebox.showwarning("تنبيه", "لم يتم إضافة أي منتجات!")
                return

            total_sum = sum(item["total"] for item in cart_items)

            conn = sqlite3.connect("sales_22.db")
            c = conn.cursor()
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute("INSERT INTO sales (date, total, store_name) VALUES (?, ?, ?)", 
                      (date_now, total_sum, store_name))
            sale_id = c.lastrowid

            for item in cart_items:
                c.execute("""
                    INSERT INTO sale_items (sale_id, product_name, quantity, price, total)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_id, item["name"], item["qty"], item["price"], item["total"]))

            conn.commit()
            conn.close()
            
            # 🔥 تحديث الإجماليات والكميات مع تمرير cart_items
            update_daily_total_local(total_sum, store_name, cart_items)
            upload_sale_to_firebase_async(cart_items, total_sum)

            #messagebox.showinfo("تم", "تم حفظ الفاتورة بنجاح ✅")

            for child in tablet.get_children():
                tablet.delete(child)
            update_total_sum()

        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ أثناء حفظ الفاتورة:\n{e}")

    def check():
        invoice_window = ctk.CTkToplevel()
        invoice_window.title("فاتورة العميل")
        invoice_window.geometry("400x500")
        invoice_window.configure(fg_color="white")
        title_label = ctk.CTkLabel(invoice_window, text="فاتورة مطعم مولى", 
                               font=("Arial", 20, "bold"), text_color="#FFA500")
        title_label.pack(pady=10)

        text_box = ctk.CTkTextbox(invoice_window, width=350, height=350, 
                             fg_color="white", text_color="black")
        text_box.pack(pady=10)
    
        text_box.insert("end", "=" * 40 + "\n")
        text_box.insert("end", "      PIZZA LALA MOUNI\n")
        text_box.insert("end", f"      {store_name}\n")
        text_box.insert("end", f"      {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        text_box.insert("end", "=" * 40 + "\n\n")
        original_items = []
        total_sum = 0
        for item in tablet.get_children():
            name, price, qty, total = tablet.item(item, "values")
            original_items.append({
                'name': name,
                'price': price,
                'qty': qty,
                'total': total
            })
            text_box.insert("end", f"{name} | {qty} × {price} = {total}\n")
            digits = "".join([ch for ch in total if ch.isdigit()])
            if digits:
                total_sum += int(digits)
        text_box.insert("end", "\n" + "-" * 40 + "\n")
        text_box.insert("end", f"الإجمالي: {total_sum} دج\n")
        text_box.insert("end", "=" * 40 + "\n")
        text_box.insert("end", "شكرًا لزيارتكم ❤️\n")
        
        def print_invoice_simple():
            """طباعة مباشرة باستخدام البيانات الأصلية"""
            try:
                settings = load_printer_settings()
                vendor = settings["vendor"]
                product = settings["product"]
            
                vendor_hex = int(vendor, 16) if vendor.startswith("0x") else int(vendor, 16)
                product_hex = int(product, 16) if product.startswith("0x") else int(product, 16)
            
                printer = Usb(vendor_hex, product_hex)
            
                printer.text("=" * 40 + "\n")
                printer.text("      PIZZA LALA MOUNI\n")
                printer.text(f"      {store_name}\n")
                printer.text(f"      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                printer.text("=" * 40 + "\n\n")
                
                for item in original_items:
                    name = item['name']
                    qty = item['qty']
                    price = item['price']
                    total = item['total']
                    
                    price_clean = str(price).replace("DA", "").strip()
                    total_clean = str(total).replace("DA", "").strip()
                
                    printer.text(f"{name}\n")
                    printer.text(f"  {qty} × {price_clean} = {total_clean}\n")
                
                printer.text("\n" + "-" * 40 + "\n")
                printer.text(f"الإجمالي: {total_sum} دج\n")
                printer.text("=" * 40 + "\n")
                printer.text("شكرًا لزيارتكم\n")
                printer.text("=" * 40 + "\n\n")
            
                printer.cut()
                printer.close()
            
                messagebox.showinfo("نجاح", "✅ تمت الطباعة بنجاح!")

            except Exception as e:
                messagebox.showerror("خطأ", f"❌ فشلت الطباعة: {str(e)}")
        
        print_btn = ctk.CTkButton(invoice_window, 
                             text="طباعة الفاتورة", 
                             fg_color="#FFA500", 
                             text_color="white",
                             command=print_invoice_simple)
        print_btn.pack(pady=10)
        
        invoice_window.after(100, Nouv)

    ##################################sherach#################################
    
    But_frame = ctk.CTkFrame(Frame, fg_color="#042B4D", corner_radius=10)
    But_frame.place(x=20, y=525)

    List_tablet = [
        ("imglog/search.png", "Search", open_advanced_search_window),  # غيرت النص هنا
        ("imglog/reject.png", "Vider", vider),
        ("imglog/remove.png", "Supprimer", supprimer),
        ("imglog/report_11472710 (1).png", "Check", check),
    ]

    buttonstot = []
    columnsk = 2
    for ik, (img_pathk, textk, cmdtot) in enumerate(List_tablet):
        imgk = ctk.CTkImage(light_image=Image.open(img_pathk), size=(25, 25))

        btntot = ctk.CTkButton(
            But_frame,
            image=imgk,
            text=textk,
            compound="left",
            fg_color="#1E1E1E",
            hover_color="#333333",
            text_color="white",
            font=("Arial", 13, "bold"),
            width=70,
            height=25,
            corner_radius=8,
            command=cmdtot
        )
        
        rowk = ik // columnsk
        columnk = ik % columnsk
        btntot.grid(row=rowk, column=columnk, padx=5, pady=10)
        buttonstot.append(btntot)

    #------------------ الصور والأسماء ------------------------------------------------------#
    def pizza_moula(name):
        Framelistecatégorie.pack_forget()
        category_image_path = "imglog/catering.png"  # افتراضي
        for cat_name, img_path in datamoula2:
            if cat_name == name:
                if img_path and os.path.exists(img_path):
                    category_image_path = img_path
                    break
        update_category_title(name,category_image_path)
        Framemoula = ctk.CTkScrollableFrame(Framecatégorie, width=400, height=500, fg_color="transparent")
        Framemoula.pack(pady=25, fill="both", expand=True)  
        columns = 2
        
        
        def add_to_table(cat, price):
            
            found_item = None
            global category_selected_item
            
            # التحقق من عدم تكرار المنتج
            for child in tablet.get_children():
                valu = tablet.item(child, "values")
                if valu and valu[0] == cat:
                    found_item=child
                    
                    break
            if found_item:
                valu = list(tablet.item(found_item, "values"))
                current_qty = int(valu[2]) if str(valu[2]).isdigit() else 0
                new_qty = current_qty + 1
                valu[2] = str(new_qty)
                price_int = int(str(valu[1]).replace("DA", "").strip() or 0)
                valu[3] = f"{price_int * new_qty}"
                category_selected_item=None
                tablet.item(found_item, values=valu)    
            else:    
                qte = 1
                total = int(price) * qte
                count = len(tablet.get_children())
                tag = "evenrow" if count % 2 == 0 else "oddrow"
                category_selected_item=None
                tablet.insert("", "end", values=(cat, price, qte, f"{total}"), tags=(tag,))
            update_total_sum()
        
        datamouli = get_products_by_category(name)
        
        for i1, (label1, price1) in enumerate(datamouli):
            btn1 = ctk.CTkButton(
                Framemoula,
               
                text=f"{label1}\n{price1}",
                compound="top",
                fg_color="#FF8000",
                hover_color="#E67300",
                text_color="white",
                font=ctk.CTkFont(family="Arial", size=18, weight="bold"),
                width=140,
                height=70,
                command=lambda c=label1, p=price1: add_to_table(c, p))
            row1 = i1 // columns
            col1 = i1 % columns
            btn1.grid(row=row1, column=col1, padx=10, pady=10)
        
        for c1 in range(columns):
            Framemoula.grid_columnconfigure(c1, weight=1)
        
        replay_img = CTkImage(light_image=Image.open("imglog/arrow.png"), size=(25, 25))
        
        def replay_btn():
            Framelistecatégorie.pack(pady=25)
            Framemoula.pack_forget()
            update_category_title("Catégorie","imglog/photo_2025-11-30_21-49-13.jpg")
            btn_replay.place_forget()
        
        btn_replay = ctk.CTkButton(master=Framecatégorie, image=replay_img, text="", width=30, height=30, fg_color="transparent", command=replay_btn)
        btn_replay.place(x=0, y=0)
    
    create_db_table()
    ensure_default_categories_exist()
    datamoula2 = get_all_categories()
    
    #------------------ إنشاء الأزرار ديناميكيًا ------------------------------------------#
    columns = 2
    for i, (name, img_path) in enumerate(datamoula2):
        try:
            if img_path and os.path.exists(img_path):
                pil_img = Image.open(img_path)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(180, 120))
            else:
                pil_img = Image.new('RGB', (180, 120), color='#808080')
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(180, 120))
        except Exception as e:
            pil_img = Image.new('RGB', (180, 120), color='#808080')
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(180, 120))

        btn = ctk.CTkButton(
            Framelistecatégorie,
            image=ctk_img,
            text=name,
            compound="top",
            fg_color="#FF8000",
            hover_color="#E67300",
            text_color="white",
            font=ctk.CTkFont(family="Arial", size=18, weight="bold"),
            width=120,
            height=140,
            command=lambda n=name: pizza_moula(n)
        )

        row = i // columns
        col = i % columns
        btn.grid(row=row, column=col, padx=15, pady=15)

    for c in range(columns):
        Framelistecatégorie.grid_columnconfigure(c, weight=1)
    
    # زر البحث المتقدم في مكان منفصل
   
    # تشغيل واجهة البيع تلقائياً عند الدخول
    vente()
    
    pageprincipale.mainloop()

#-------------------------- Function Open Page ----------------------------------------------------------#
def verify_login_in_firebase(username, password):
    """التحقق من اسم المستخدم وكلمة المرور في Firebase"""
    try:
        if not firebase_admin._apps:
            messagebox.showerror("خطأ", "Firebase غير مهيئ")
            return None
        
        ref = db.reference("store_accounts")
        user_data = ref.child(password).get()
        
        if user_data and user_data.get("password") == password:
            return {
                "store_name": user_data.get("store_name"),
                "costs": user_data.get("costs")
            }
        else:
            return None
            
    except Exception as e:
        print(f"❌ خطأ في التحقق من Firebase: {e}")
        return None

def open_printer_settings_simple():
    """نافذة إعدادات الطابعة البسيطة"""
    settings_window = ctk.CTkToplevel()
    settings_window.title("إعدادات الطابعة")
    settings_window.geometry("400x250")
    settings_window.configure(fg_color="white")
    
    current = load_printer_settings()
    
    vendor_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
    vendor_frame.pack(pady=15)
    ctk.CTkLabel(vendor_frame, text="Vendor ID:", font=("Arial", 14)).pack(side="left", padx=5)
    vendor_entry = ctk.CTkEntry(vendor_frame, width=200)
    vendor_entry.insert(0, current["vendor"])
    vendor_entry.pack(side="left", padx=5)
    
    product_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
    product_frame.pack(pady=10)
    ctk.CTkLabel(product_frame, text="Product ID:", font=("Arial", 14)).pack(side="left", padx=5)
    product_entry = ctk.CTkEntry(product_frame, width=200)
    product_entry.insert(0, current["product"])
    product_entry.pack(side="left", padx=5)
    
    def save_and_close():
        vendor = vendor_entry.get().strip()
        product = product_entry.get().strip()
        
        if vendor and product:
            save_printer_settings(vendor, product)
            settings_window.destroy()
        else:
            messagebox.showwarning("تحذير", "الرجاء ملء جميع الحقول")
    
    save_btn = ctk.CTkButton(settings_window, text="💾 حفظ", 
                           fg_color="#FFA500", text_color="white",
                           width=150, command=save_and_close)
    save_btn.pack(pady=20)

########################
def open_page():
    global store_name
    
    init_firebase()
    admin = admin_entry.get().strip()
    password = password_entry.get().strip()
    
    if not admin or not password:
        messagebox.showerror("خطأ", "الرجاء إدخال اسم المستخدم وكلمة المرور")
        return
    
    
    store_data = verify_login_in_firebase(admin, password)
    if store_data:
        Session.store_name = store_data["store_name"]
        Session.costs_data = store_data["costs"]
        store_name = Session.store_name
        cost = Session.costs_data
        messagebox.showinfo("نجاح", f"مرحباً بك في {store_name}")
        Login.destroy()
        pageprinc()
    else:
        messagebox.showerror("خطأ", "اسم المستخدم أو كلمة المرور غير صحيحة")

# زر تسجيل الدخول
login_button = ctk.CTkButton(Login, text="LOG IN", width=200, height=40, fg_color="white", hover_color="white", text_color="#EF5726", font=("Arial", 15, "bold"), corner_radius=10, command=open_page)
login_button.pack(pady=30)

settings_btn = ctk.CTkButton(
    Login,
    text="⚙️",
    width=40,
    height=40,
    fg_color="transparent",
    hover_color="#FF8C00",
    font=("Arial", 20, "bold"),
    command=open_printer_settings_simple
)
settings_btn.place(x=350, y=20)





Login.mainloop()  
