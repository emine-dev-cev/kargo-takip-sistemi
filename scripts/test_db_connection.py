"""
Database Connection & Health Diagnostic Script
------------------------------------------------
Tests the SQLite database connection, table integrity, read/write capabilities,
and provides a detailed status summary directly in the terminal.
"""

import os
import sys
import time
import sqlite3
from datetime import datetime

# ANSI Color Codes for beautiful terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(text: str):
    print(f"\n{MAGENTA}{BOLD}{'='*60}{RESET}")
    print(f"{CYAN}{BOLD}  {text}{RESET}")
    print(f"{MAGENTA}{BOLD}{'='*60}{RESET}")

def print_result(label: str, status: bool, detail: str = ""):
    icon = f"{GREEN}✔ [BAŞARILI]{RESET}" if status else f"{RED}✖ [HATA]{RESET}"
    detail_str = f" - {detail}" if detail else ""
    print(f"  {icon} {BOLD}{label}{RESET}{detail_str}")

def find_db_path() -> str:
    """Finds the most suitable database path for both container and local execution."""
    # Check environment variable
    env_path = os.getenv("DATABASE_PATH")
    if env_path and (os.path.exists(env_path) or os.path.exists(os.path.dirname(os.path.abspath(env_path)))):
        return env_path
    
    # Common candidate paths
    candidates = [
        "/app/data/cargo.db",
        "data/cargo.db",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cargo.db"),
        os.path.join(os.getcwd(), "data", "cargo.db"),
        "cargo.db"
    ]
    
    for path in candidates:
        if os.path.exists(path):
            return path
            
    # Default to data/cargo.db if none exists yet
    return candidates[1]

def run_db_diagnostic():
    print_header("📦 KARGO VERİTABANI BAĞLANTI & SAĞLIK TESTİ")
    print(f"  {BOLD}Çalışma Zamanı:{RESET} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    db_path = find_db_path()
    print(f"  {BOLD}Hedef DB Yolu:{RESET}  {YELLOW}{os.path.abspath(db_path)}{RESET}\n")

    overall_success = True
    start_total_time = time.perf_counter()

    # 1. Dosya Varlık & Dizin Kontrolü
    db_exists = os.path.exists(db_path)
    if db_exists:
        file_size_kb = os.path.getsize(db_path) / 1024
        print_result("Veritabanı Dosyası", True, f"Mevcut ({file_size_kb:.2f} KB)")
    else:
        print_result("Veritabanı Dosyası", False, "Dosya henüz oluşturulmamış, başlatma gerekebilir")
        overall_success = False

    # 2. Bağlantı Açma & Yanıt Süresi (Latency) Testi
    try:
        t0 = time.perf_counter()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        latency_ms = (time.perf_counter() - t0) * 1000
        print_result("SQLite Bağlantısı", True, f"Bağlantı kuruldu (Gecikme: {latency_ms:.2f} ms)")
    except Exception as e:
        print_result("SQLite Bağlantısı", False, f"Bağlantı hatası: {str(e)}")
        return False

    # 3. SQLite Motor & Sürüm Kontrolü
    try:
        cursor.execute("SELECT sqlite_version();")
        version = cursor.fetchone()[0]
        print_result("SQLite Motor Sürümü", True, f"v{version}")
    except Exception as e:
        print_result("SQLite Motor Sürümü", False, str(e))
        overall_success = False

    # 4. Tablo Şeması Doğrulama
    table_exists = False
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cargo';")
        row = cursor.fetchone()
        if row:
            table_exists = True
            cursor.execute("PRAGMA table_info(cargo);")
            columns = [c[1] for c in cursor.fetchall()]
            print_result("'cargo' Tablosu Şeması", True, f"Sütunlar: {', '.join(columns)}")
        else:
            print_result("'cargo' Tablosu", False, "Tablo bulunamadı! 'init_db' gerekebilir.")
            overall_success = False
    except Exception as e:
        print_result("'cargo' Tablosu", False, str(e))
        overall_success = False

    # 5. Okuma (READ) ve İstatistik Testi
    if table_exists:
        try:
            cursor.execute("SELECT COUNT(*) as total FROM cargo;")
            total_count = cursor.fetchone()["total"]
            
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM cargo 
                GROUP BY status 
                ORDER BY count DESC;
            """)
            status_counts = cursor.fetchall()
            status_summary = ", ".join([f"{r['status']}: {r['count']}" for r in status_counts]) or "Henüz kayıt yok"

            print_result("Okuma (SELECT) Testi", True, f"Toplam: {total_count} kargo ({status_summary})")
        except Exception as e:
            print_result("Okuma (SELECT) Testi", False, str(e))
            overall_success = False

    # 6. Yazma & Geri Alma (WRITE / TRANSACTION) Testi
    try:
        test_tracking = f"TEST-DIAG-{int(time.time())}"
        cursor.execute("""
            INSERT INTO cargo (tracking_number, sender, receiver, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (test_tracking, "DiagBot", "TestReceiver", "CREATED", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        
        test_id = cursor.lastrowid
        cursor.execute("DELETE FROM cargo WHERE id = ?", (test_id,))
        conn.commit()
        print_result("Yazma & İşlem (INSERT/DELETE)", True, "Kayıt ekleme ve silme işlemi doğrulandı")
    except Exception as e:
        conn.rollback()
        print_result("Yazma & İşlem (INSERT/DELETE)", False, f"Yazma izni hatası: {str(e)}")
        overall_success = False

    # 7. Bütünlük Kontrolü (PRAGMA integrity_check)
    try:
        cursor.execute("PRAGMA integrity_check;")
        check_result = cursor.fetchone()[0]
        if check_result.lower() == "ok":
            print_result("Veritabanı Bütünlüğü", True, "PRAGMA integrity_check = OK")
        else:
            print_result("Veritabanı Bütünlüğü", False, f"Bozukluk tespit edildi: {check_result}")
            overall_success = False
    except Exception as e:
        print_result("Veritabanı Bütünlüğü", False, str(e))
        overall_success = False

    conn.close()
    total_time_ms = (time.perf_counter() - start_total_time) * 1000

    # Özet Sonuç
    print(f"\n{MAGENTA}{'-'*60}{RESET}")
    if overall_success:
        print(f"  {GREEN}{BOLD}🎉 SONUÇ: Veritabanı bağlantısı sağlıklı ve sorunsuz çalışıyor!{RESET}")
    else:
        print(f"  {RED}{BOLD}⚠️ SONUÇ: Veritabanında bazı sorunlar tespit edildi!{RESET}")
    print(f"  {CYAN}Toplam Test Süresi:{RESET} {total_time_ms:.2f} ms")
    print(f"{MAGENTA}{'='*60}{RESET}\n")

    return overall_success

if __name__ == "__main__":
    success = run_db_diagnostic()
    sys.exit(0 if success else 1)
