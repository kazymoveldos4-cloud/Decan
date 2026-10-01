"""
Тестируем несколько вариантов подключения к MSSQL,
чтобы найти рабочий. Запуск: py -3.12 test_connection.py
"""
import pyodbc

drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
print("Установленные ODBC-драйверы для SQL Server:")
for d in drivers:
    print("  -", d)
print()

if not drivers:
    print("!!! Нет установленных драйверов ODBC для SQL Server.")
    exit()

driver = drivers[0]
print("Использую драйвер:", driver)
print()

candidates = [
    r"LAPTOP-J8OA4RNS\SQLEXPRESS",
    r".\SQLEXPRESS",
    r"localhost\SQLEXPRESS",
    r"(local)\SQLEXPRESS",
    r"127.0.0.1\SQLEXPRESS",
    r"localhost,1433",
    r"127.0.0.1,1433",
]

for server in candidates:
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str, timeout=3)
        print(f"[OK]   {server}  <-- РАБОТАЕТ!")
        conn.close()
    except Exception as e:
        msg = str(e).split(";")[0][:80]
        print(f"[FAIL] {server}  ({msg})")