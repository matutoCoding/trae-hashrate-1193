"""测试脚本：模拟旧系统生成重复排期，验证迁移合并"""
import sqlite3
from datetime import date, datetime, timedelta
import os

DB_PATH = "orthodontics.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"已删除旧数据库: {DB_PATH}")

# 1. 创建"旧版本"数据库（没有唯一约束，故意造重复数据）
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.executescript('''
    CREATE TABLE IF NOT EXISTS chairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        patient_type TEXT DEFAULT 'normal'
    );

    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chair_id INTEGER NOT NULL,
        patient_id INTEGER,
        schedule_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        status TEXT DEFAULT 'available',
        patient_type TEXT DEFAULT 'normal',
        priority INTEGER DEFAULT 0,
        cycle_rule_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        patient_id INTEGER NOT NULL,
        reminder_time TEXT NOT NULL,
        status TEXT DEFAULT 'pending'
    );

    CREATE TABLE IF NOT EXISTS queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        schedule_id INTEGER,
        queue_number INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS priority_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        patient_type TEXT NOT NULL,
        priority_level INTEGER DEFAULT 0,
        can_jump INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS cycle_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        chair_id INTEGER,
        day_of_week INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        description TEXT
    );
''')

# 插入基础数据
cursor.execute("INSERT INTO chairs (name) VALUES ('诊疗椅1'), ('诊疗椅2')")
cursor.execute("INSERT INTO patients (name, patient_type) VALUES ('张三', 'normal'), ('李四', 'vip')")
cursor.execute('''
    INSERT INTO priority_rules (name, patient_type, priority_level, can_jump) VALUES
    ('急诊', 'emergency', 100, 1),
    ('VIP贵宾', 'vip', 80, 1),
    ('复诊优先', 'priority', 50, 0),
    ('普通患者', 'normal', 0, 0)
''')
conn.commit()

# 故意插入重复排期：同一个椅子/日期/时间有多条
today = date.today().isoformat()

# 第1组：重复数据 - 一条 available + 一条 booked（李四预约了）
for i in range(3):
    cursor.execute('''
        INSERT INTO schedules (chair_id, patient_id, schedule_date, start_time, end_time, status)
        VALUES (1, NULL, ?, '09:00', '09:30', 'available')
    ''', (today,))
cursor.execute('''
    INSERT INTO schedules (chair_id, patient_id, schedule_date, start_time, end_time, status, patient_type, priority)
    VALUES (1, 2, ?, '09:00', '09:30', 'booked', 'vip', 80)
''', (today,))

# 第2组：重复数据 - 全部 available
for i in range(2):
    cursor.execute('''
        INSERT INTO schedules (chair_id, schedule_date, start_time, end_time, status)
        VALUES (1, ?, '09:30', '10:00', 'available')
    ''', (today,))

# 第3组：张三 booked 的重复
cursor.execute('''
    INSERT INTO schedules (chair_id, patient_id, schedule_date, start_time, end_time, status, patient_type)
    VALUES (1, 1, ?, '10:00', '10:30', 'booked', 'normal')
''', (today,))
cursor.execute('''
    INSERT INTO schedules (chair_id, schedule_date, start_time, end_time, status)
    VALUES (1, ?, '10:00', '10:30', 'available')
''', (today,))

# 给 booked 记录加提醒
cursor.execute("SELECT id FROM schedules WHERE status='booked'")
for row in cursor.fetchall():
    cursor.execute('''
        INSERT INTO reminders (schedule_id, patient_id, reminder_time)
        VALUES (?, 2, ?)
    ''', (row['id'], datetime.now().isoformat()))

conn.commit()

# 统计迁移前的数据
cursor.execute("SELECT COUNT(*) FROM schedules")
print(f"\n迁移前 schedules 总数: {cursor.fetchone()[0]}")

cursor.execute('''
    SELECT chair_id, schedule_date, start_time, COUNT(*) as cnt
    FROM schedules
    GROUP BY chair_id, schedule_date, start_time
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
''')
print("重复分组:")
for row in cursor.fetchall():
    print(f"  椅{row['chair_id']} {row['schedule_date']} {row['start_time']} → 重复 {row['cnt']} 条")

conn.close()

print("\n现在启动主程序，应该会自动迁移合并重复数据...")
print("验证点：")
print("  1. 程序能正常启动，不报错")
print("  2. 控制台输出 [数据库迁移] 已合并 X 条重复排期记录")
print("  3. 09:00 时段最终保留 booked（李四 VIP），不是 available")
print("  4. 所有重复时段合并后只剩一条")
