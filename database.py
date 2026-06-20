import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import json


class Database:
    def __init__(self, db_path: str = "orthodontics.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_tables()
        self._migrate_add_missing_columns()
        self._migrate_deduplicate_schedules()
        self._ensure_schedules_unique_index()
        self._init_default_data()

    def _migrate_add_missing_columns(self):
        """迁移：为旧版本数据库补齐缺失的列，避免后续报错"""
        EXPECTED_COLUMNS = {
            'chairs': ['id', 'name', 'description', 'is_active', 'created_at'],
            'patients': ['id', 'name', 'phone', 'patient_type', 'stage', 'notes', 'created_at'],
            'cycle_rules': ['id', 'name', 'chair_id', 'day_of_week', 'start_time', 'end_time',
                            'interval_minutes', 'patient_type', 'is_active', 'created_at'],
            'schedules': ['id', 'chair_id', 'patient_id', 'schedule_date', 'start_time',
                          'end_time', 'status', 'patient_type', 'priority', 'cycle_rule_id',
                          'notes', 'created_at'],
            'queue': ['id', 'patient_id', 'schedule_id', 'queue_number', 'priority',
                      'patient_type', 'status', 'chair_id', 'checkin_time', 'called_time',
                      'completed_time', 'is_jumped'],
            'priority_rules': ['id', 'name', 'patient_type', 'priority_level', 'can_jump',
                               'description', 'created_at'],
            'reminders': ['id', 'schedule_id', 'patient_id', 'reminder_time', 'status',
                          'sent_time', 'message'],
            'settings': ['key', 'value', 'description'],
            'schedule_dedup_log': ['id', 'merge_time', 'chair_id', 'schedule_date', 
                                   'start_time', 'kept_schedule_id', 'merged_count', 
                                   'kept_patient_id', 'kept_status', 'detail'],
        }
        COLUMN_DEFS = {
            'is_active': 'INTEGER DEFAULT 1',
            'created_at': 'TEXT',
            'description': 'TEXT',
            'name': 'TEXT NOT NULL DEFAULT \'\'',
            'phone': 'TEXT',
            'patient_type': 'TEXT DEFAULT \'normal\'',
            'stage': 'TEXT',
            'notes': 'TEXT',
            'chair_id': 'INTEGER',
            'day_of_week': 'INTEGER NOT NULL DEFAULT 0',
            'start_time': 'TEXT NOT NULL DEFAULT \'00:00\'',
            'end_time': 'TEXT NOT NULL DEFAULT \'00:00\'',
            'interval_minutes': 'INTEGER DEFAULT 30',
            'patient_id': 'INTEGER',
            'schedule_date': 'TEXT NOT NULL DEFAULT \'\'',
            'status': 'TEXT DEFAULT \'available\'',
            'priority': 'INTEGER DEFAULT 0',
            'cycle_rule_id': 'INTEGER',
            'schedule_id': 'INTEGER',
            'queue_number': 'INTEGER NOT NULL DEFAULT 0',
            'priority_level': 'INTEGER DEFAULT 0',
            'can_jump': 'INTEGER DEFAULT 0',
            'reminder_time': 'TEXT NOT NULL DEFAULT \'\'',
            'sent_time': 'TEXT',
            'message': 'TEXT',
            'value': 'TEXT',
            'checkin_time': 'TEXT',
            'called_time': 'TEXT',
            'completed_time': 'TEXT',
            'is_jumped': 'INTEGER DEFAULT 0',
            'merge_time': 'TEXT',
            'kept_schedule_id': 'INTEGER',
            'merged_count': 'INTEGER DEFAULT 0',
            'kept_patient_id': 'INTEGER',
            'kept_status': 'TEXT',
            'detail': 'TEXT',
        }
        try:
            for table, expected_cols in EXPECTED_COLUMNS.items():
                try:
                    cursor = self.conn.execute(f"PRAGMA table_info({table})")
                    existing = {row['name'] for row in cursor.fetchall()}
                except Exception:
                    continue
                for col in expected_cols:
                    if col not in existing and col in COLUMN_DEFS:
                        try:
                            self.conn.execute(
                                f"ALTER TABLE {table} ADD COLUMN {col} {COLUMN_DEFS[col]}"
                            )
                            print(f"[数据库迁移] 表 {table} 已新增列: {col}")
                        except Exception as e:
                            print(f"[数据库迁移] 表 {table} 新增列 {col} 失败: {e}")
            self.conn.commit()
        except Exception as e:
            print(f"[数据库迁移] 补齐缺失列出错（已跳过）: {e}")
            self.conn.rollback()

    def _migrate_deduplicate_schedules(self):
        """迁移：合并 schedules 表中的重复时段，保留患者预约信息"""
        try:
            # 检查是否有重复数据
            cursor = self.conn.execute('''
                SELECT chair_id, schedule_date, start_time, COUNT(*) as cnt
                FROM schedules
                GROUP BY chair_id, schedule_date, start_time
                HAVING COUNT(*) > 1
            ''')
            duplicates = cursor.fetchall()
            
            if not duplicates:
                return
            
            status_rank = {
                'booked': 4,
                'completed': 3,
                'available': 2,
                'cancelled': 1,
            }
            
            total_merged = 0
            
            for dup in duplicates:
                chair_id = dup['chair_id']
                schedule_date = dup['schedule_date']
                start_time = dup['start_time']
                
                # 取出该组所有重复记录
                cursor = self.conn.execute('''
                    SELECT * FROM schedules
                    WHERE chair_id=? AND schedule_date=? AND start_time=?
                    ORDER BY id
                ''', (chair_id, schedule_date, start_time))
                rows = cursor.fetchall()
                
                # 选一条要保留的：优先级最高的那条
                def row_score(r):
                    return (
                        status_rank.get(r['status'], 0),
                        1 if r['patient_id'] else 0,
                        -r['id']  # 其他条件相同选 id 最大的
                    )
                
                rows_sorted = sorted(rows, key=row_score, reverse=True)
                keep_row = rows_sorted[0]
                delete_rows = rows_sorted[1:]
                
                # 合并信息到 keep_row：patient_id, priority, patient_type, notes, cycle_rule_id
                # 用 row.keys() 检查列是否存在，兼容旧版本数据库
                keep_cols = keep_row.keys()
                def safe_get(row, key, default=None):
                    return row[key] if key in row.keys() else default
                
                keep_updates = {}
                if not safe_get(keep_row, 'patient_id'):
                    for r in delete_rows:
                        if safe_get(r, 'patient_id'):
                            keep_updates['patient_id'] = safe_get(r, 'patient_id')
                            if safe_get(r, 'status') in ('booked', 'completed'):
                                keep_updates['status'] = safe_get(r, 'status')
                            pt = safe_get(r, 'patient_type')
                            if pt and pt != 'normal':
                                keep_updates['patient_type'] = pt
                            pr = safe_get(r, 'priority')
                            if pr and pr > 0:
                                keep_updates['priority'] = pr
                            break
                if not safe_get(keep_row, 'cycle_rule_id') and 'cycle_rule_id' in keep_cols:
                    for r in delete_rows:
                        if safe_get(r, 'cycle_rule_id'):
                            keep_updates['cycle_rule_id'] = safe_get(r, 'cycle_rule_id')
                            break
                if not safe_get(keep_row, 'notes') and 'notes' in keep_cols:
                    for r in delete_rows:
                        if safe_get(r, 'notes'):
                            keep_updates['notes'] = safe_get(r, 'notes')
                            break
                
                # 如果有需要合并的字段，更新保留行
                if keep_updates:
                    sets = ", ".join(f"{k}=?" for k in keep_updates.keys())
                    params = list(keep_updates.values()) + [keep_row['id']]
                    self.conn.execute(f"UPDATE schedules SET {sets} WHERE id=?", params)
                
                # 删除其他重复行
                detail_parts = []
                for r in delete_rows:
                    # 如果被删行有关联的 reminders，转移到 keep_row
                    self.conn.execute('''
                        UPDATE reminders SET schedule_id=? WHERE schedule_id=?
                    ''', (keep_row['id'], r['id']))
                    # 如果被删行有关联的 queue，schedule_id 置空
                    self.conn.execute('''
                        UPDATE queue SET schedule_id=NULL WHERE schedule_id=?
                    ''', (r['id'],))
                    # 记录详情
                    r_patient = safe_get(r, 'patient_id')
                    r_status = safe_get(r, 'status')
                    detail_parts.append(f"删除id={r['id']}(患者={r_patient},状态={r_status})")
                    self.conn.execute("DELETE FROM schedules WHERE id=?", (r['id'],))
                    total_merged += 1
                
                # 记录合并日志
                self.conn.execute('''
                    INSERT INTO schedule_dedup_log 
                    (chair_id, schedule_date, start_time, kept_schedule_id, merged_count,
                     kept_patient_id, kept_status, detail)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    safe_get(keep_row, 'chair_id'),
                    safe_get(keep_row, 'schedule_date'),
                    safe_get(keep_row, 'start_time'),
                    keep_row['id'],
                    len(delete_rows),
                    safe_get(keep_row, 'patient_id'),
                    safe_get(keep_row, 'status'),
                    "; ".join(detail_parts)
                ))
            
            if total_merged > 0:
                self.conn.commit()
                print(f"[数据库迁移] 已合并 {total_merged} 条重复排期记录")
        except Exception as e:
            print(f"[数据库迁移] 合并重复排期出错（已跳过）: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _ensure_schedules_unique_index(self):
        """在去重完成后，安全地创建 schedules 唯一索引"""
        try:
            # 先确认没有重复
            cursor = self.conn.execute('''
                SELECT COUNT(*) as cnt FROM (
                    SELECT chair_id, schedule_date, start_time
                    FROM schedules
                    GROUP BY chair_id, schedule_date, start_time
                    HAVING COUNT(*) > 1
                )
            ''')
            if cursor.fetchone()['cnt'] > 0:
                print("[数据库] 警告：schedules 表仍存在重复数据，跳过创建唯一索引")
                return

            # 建唯一索引
            self.conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_schedules_unique 
                ON schedules(chair_id, schedule_date, start_time)
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"[数据库] 创建 schedules 唯一索引出错（已跳过）: {e}")
            self.conn.rollback()

    def _init_tables(self):
        cursor = self.conn.cursor()
        
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS chairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                patient_type TEXT DEFAULT 'normal',
                stage TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cycle_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                chair_id INTEGER,
                day_of_week INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                interval_minutes INTEGER DEFAULT 30,
                patient_type TEXT DEFAULT 'normal',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chair_id) REFERENCES chairs(id)
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
                cycle_rule_id INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chair_id) REFERENCES chairs(id),
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (cycle_rule_id) REFERENCES cycle_rules(id)
            );

            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                schedule_id INTEGER,
                queue_number INTEGER NOT NULL,
                priority INTEGER DEFAULT 0,
                patient_type TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'waiting',
                chair_id INTEGER,
                checkin_time TEXT DEFAULT CURRENT_TIMESTAMP,
                called_time TEXT,
                completed_time TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (schedule_id) REFERENCES schedules(id),
                FOREIGN KEY (chair_id) REFERENCES chairs(id)
            );

            CREATE TABLE IF NOT EXISTS priority_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                patient_type TEXT NOT NULL,
                priority_level INTEGER DEFAULT 0,
                can_jump INTEGER DEFAULT 0,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                reminder_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                sent_time TEXT,
                message TEXT,
                FOREIGN KEY (schedule_id) REFERENCES schedules(id),
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS schedule_dedup_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merge_time TEXT DEFAULT CURRENT_TIMESTAMP,
                chair_id INTEGER,
                schedule_date TEXT,
                start_time TEXT,
                kept_schedule_id INTEGER,
                merged_count INTEGER DEFAULT 0,
                kept_patient_id INTEGER,
                kept_status TEXT,
                detail TEXT
            );
        ''')
        
        self.conn.commit()

    def _init_default_data(self):
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM priority_rules")
        if cursor.fetchone()[0] == 0:
            rules = [
                ('急诊', 'emergency', 100, 1, '急诊患者，最高优先级，可直接插队到最前'),
                ('VIP贵宾', 'vip', 80, 1, 'VIP贵宾患者，高优先级，可插队到普通患者前'),
                ('复诊优先', 'priority', 50, 0, '优先复诊患者，中等优先级'),
                ('普通患者', 'normal', 0, 0, '普通复诊患者，正常优先级'),
            ]
            cursor.executemany('''
                INSERT INTO priority_rules (name, patient_type, priority_level, can_jump, description)
                VALUES (?, ?, ?, ?, ?)
            ''', rules)
        
        cursor.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] == 0:
            settings = [
                ('queue_display_count', '5', '叫号屏显示人数'),
                ('reminder_minutes_before', '30', '复诊提醒提前分钟数'),
                ('default_interval', '30', '默认复诊间隔分钟数'),
            ]
            cursor.executemany('''
                INSERT INTO settings (key, value, description) VALUES (?, ?, ?)
            ''', settings)
        
        self.conn.commit()

    def close(self):
        self.conn.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self.conn.commit()


class ChairManager:
    def __init__(self, db: Database):
        self.db = db

    def add_chair(self, name: str, description: str = "") -> int:
        cursor = self.db.execute(
            "INSERT INTO chairs (name, description) VALUES (?, ?)",
            (name, description)
        )
        self.db.commit()
        return cursor.lastrowid

    def update_chair(self, chair_id: int, name: str, description: str, is_active: bool):
        self.db.execute(
            "UPDATE chairs SET name=?, description=?, is_active=? WHERE id=?",
            (name, description, 1 if is_active else 0, chair_id)
        )
        self.db.commit()

    def delete_chair(self, chair_id: int):
        self.db.execute("DELETE FROM chairs WHERE id=?", (chair_id,))
        self.db.commit()

    def get_all_chairs(self, active_only: bool = True) -> List[Dict]:
        sql = "SELECT * FROM chairs"
        if active_only:
            sql += " WHERE is_active=1"
        sql += " ORDER BY name"
        cursor = self.db.execute(sql)
        return [dict(row) for row in cursor.fetchall()]

    def get_chair(self, chair_id: int) -> Optional[Dict]:
        cursor = self.db.execute("SELECT * FROM chairs WHERE id=?", (chair_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


class PatientManager:
    def __init__(self, db: Database):
        self.db = db

    def add_patient(self, name: str, phone: str = "", patient_type: str = "normal", 
                    stage: str = "", notes: str = "") -> int:
        cursor = self.db.execute(
            "INSERT INTO patients (name, phone, patient_type, stage, notes) VALUES (?, ?, ?, ?, ?)",
            (name, phone, patient_type, stage, notes)
        )
        self.db.commit()
        return cursor.lastrowid

    def update_patient(self, patient_id: int, **kwargs):
        fields = ", ".join(f"{k}=?" for k in kwargs.keys())
        params = list(kwargs.values()) + [patient_id]
        self.db.execute(f"UPDATE patients SET {fields} WHERE id=?", params)
        self.db.commit()

    def get_all_patients(self) -> List[Dict]:
        cursor = self.db.execute("SELECT * FROM patients ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def get_patient(self, patient_id: int) -> Optional[Dict]:
        cursor = self.db.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def search_patients(self, keyword: str) -> List[Dict]:
        cursor = self.db.execute(
            "SELECT * FROM patients WHERE name LIKE ? OR phone LIKE ? ORDER BY name",
            (f"%{keyword}%", f"%{keyword}%")
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_patients_by_type(self, patient_type: str) -> List[Dict]:
        cursor = self.db.execute(
            "SELECT * FROM patients WHERE patient_type=? ORDER BY name",
            (patient_type,)
        )
        return [dict(row) for row in cursor.fetchall()]


class CycleRuleManager:
    def __init__(self, db: Database):
        self.db = db

    def add_rule(self, name: str, chair_id: Optional[int], day_of_week: int,
                 start_time: str, end_time: str, interval_minutes: int = 30,
                 patient_type: str = "normal") -> int:
        cursor = self.db.execute('''
            INSERT INTO cycle_rules 
            (name, chair_id, day_of_week, start_time, end_time, interval_minutes, patient_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, chair_id, day_of_week, start_time, end_time, interval_minutes, patient_type))
        self.db.commit()
        return cursor.lastrowid

    def update_rule(self, rule_id: int, **kwargs):
        fields = ", ".join(f"{k}=?" for k in kwargs.keys())
        params = list(kwargs.values()) + [rule_id]
        self.db.execute(f"UPDATE cycle_rules SET {fields} WHERE id=?", params)
        self.db.commit()

    def delete_rule(self, rule_id: int):
        self.db.execute("UPDATE cycle_rules SET is_active=0 WHERE id=?", (rule_id,))
        self.db.commit()

    def get_all_rules(self, active_only: bool = True) -> List[Dict]:
        sql = '''
            SELECT cr.*, c.name as chair_name 
            FROM cycle_rules cr 
            LEFT JOIN chairs c ON cr.chair_id = c.id
        '''
        if active_only:
            sql += " WHERE cr.is_active=1"
        sql += " ORDER BY cr.day_of_week, cr.start_time"
        cursor = self.db.execute(sql)
        return [dict(row) for row in cursor.fetchall()]

    def get_rule(self, rule_id: int) -> Optional[Dict]:
        cursor = self.db.execute('''
            SELECT cr.*, c.name as chair_name 
            FROM cycle_rules cr 
            LEFT JOIN chairs c ON cr.chair_id = c.id
            WHERE cr.id=?
        ''', (rule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


class ScheduleManager:
    def __init__(self, db: Database):
        self.db = db

    def generate_cycle_schedules(self, rule_id: int, start_date: date, 
                                 end_date: date, patient_id: Optional[int] = None) -> Tuple[int, int]:
        rule = CycleRuleManager(self.db).get_rule(rule_id)
        if not rule:
            return (0, 0)

        added_count = 0
        total_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.weekday() == rule['day_of_week']:
                added, total = self._generate_daily_schedules(rule, current_date, patient_id)
                added_count += added
                total_count += total
            current_date += timedelta(days=1)
        
        self.db.commit()
        return (added_count, total_count)

    def _generate_daily_schedules(self, rule: Dict, schedule_date: date, 
                                   patient_id: Optional[int]) -> Tuple[int, int]:
        start = datetime.strptime(rule['start_time'], '%H:%M')
        end = datetime.strptime(rule['end_time'], '%H:%M')
        interval = timedelta(minutes=rule['interval_minutes'])
        
        added_count = 0
        total_count = 0
        current = start
        while current < end:
            slot_end = current + interval
            status = 'booked' if patient_id else 'available'
            total_count += 1
            
            cursor = self.db.execute('''
                INSERT OR IGNORE INTO schedules 
                (chair_id, patient_id, schedule_date, start_time, end_time, 
                 status, patient_type, priority, cycle_rule_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule['chair_id'],
                patient_id,
                schedule_date.isoformat(),
                current.strftime('%H:%M'),
                slot_end.strftime('%H:%M'),
                status,
                rule['patient_type'],
                self._get_priority(rule['patient_type']),
                rule['id']
            ))
            if cursor.rowcount > 0:
                added_count += 1
            current = slot_end
        return (added_count, total_count)

    def _get_priority(self, patient_type: str) -> int:
        cursor = self.db.execute(
            "SELECT priority_level FROM priority_rules WHERE patient_type=?",
            (patient_type,)
        )
        row = cursor.fetchone()
        return row['priority_level'] if row else 0

    def generate_batch_schedules(self, chair_id: int, start_date: date, 
                                  end_date: date, day_of_week: int,
                                  start_time: str, end_time: str,
                                  interval_minutes: int = 30) -> Tuple[int, int]:
        added_count = 0
        total_count = 0
        current_date = start_date
        
        while current_date <= end_date:
            if current_date.weekday() == day_of_week:
                added, total = self._generate_day_slots(chair_id, current_date, start_time, 
                                                          end_time, interval_minutes)
                added_count += added
                total_count += total
            current_date += timedelta(days=1)
        
        self.db.commit()
        return (added_count, total_count)

    def _generate_day_slots(self, chair_id: int, schedule_date: date,
                            start_time: str, end_time: str, interval_minutes: int) -> Tuple[int, int]:
        start = datetime.strptime(start_time, '%H:%M')
        end = datetime.strptime(end_time, '%H:%M')
        interval = timedelta(minutes=interval_minutes)
        
        added_count = 0
        total_count = 0
        current = start
        while current < end:
            slot_end = current + interval
            total_count += 1
            cursor = self.db.execute('''
                INSERT OR IGNORE INTO schedules 
                (chair_id, schedule_date, start_time, end_time, status)
                VALUES (?, ?, ?, ?, 'available')
            ''', (
                chair_id,
                schedule_date.isoformat(),
                current.strftime('%H:%M'),
                slot_end.strftime('%H:%M')
            ))
            if cursor.rowcount > 0:
                added_count += 1
            current = slot_end
        return (added_count, total_count)

    def book_schedule(self, schedule_id: int, patient_id: int, 
                      patient_type: str = "normal") -> bool:
        priority = self._get_priority(patient_type)
        cursor = self.db.execute('''
            UPDATE schedules 
            SET patient_id=?, status='booked', patient_type=?, priority=?
            WHERE id=? AND status='available'
        ''', (patient_id, patient_type, priority, schedule_id))
        self.db.commit()
        return cursor.rowcount > 0

    def update_schedule(self, schedule_id: int, **kwargs):
        if 'patient_type' in kwargs:
            kwargs['priority'] = self._get_priority(kwargs['patient_type'])
        fields = ", ".join(f"{k}=?" for k in kwargs.keys())
        params = list(kwargs.values()) + [schedule_id]
        self.db.execute(f"UPDATE schedules SET {fields} WHERE id=?", params)
        self.db.commit()

    def cancel_schedule(self, schedule_id: int):
        self.db.execute('''
            UPDATE schedules 
            SET patient_id=NULL, status='available', patient_type='normal', priority=0
            WHERE id=?
        ''', (schedule_id,))
        self.db.commit()

    def delete_schedule(self, schedule_id: int):
        self.db.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        self.db.commit()

    def get_schedules_by_date(self, schedule_date: date, chair_id: Optional[int] = None) -> List[Dict]:
        sql = '''
            SELECT s.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM schedules s
            LEFT JOIN patients p ON s.patient_id = p.id
            LEFT JOIN chairs c ON s.chair_id = c.id
            WHERE s.schedule_date=?
        '''
        params = [schedule_date.isoformat()]
        
        if chair_id:
            sql += " AND s.chair_id=?"
            params.append(chair_id)
        
        sql += " ORDER BY s.chair_id, s.start_time"
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_schedule(self, schedule_id: int) -> Optional[Dict]:
        cursor = self.db.execute('''
            SELECT s.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM schedules s
            LEFT JOIN patients p ON s.patient_id = p.id
            LEFT JOIN chairs c ON s.chair_id = c.id
            WHERE s.id=?
        ''', (schedule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_available_slots(self, schedule_date: date, chair_id: Optional[int] = None) -> List[Dict]:
        sql = '''
            SELECT s.*, c.name as chair_name
            FROM schedules s
            LEFT JOIN chairs c ON s.chair_id = c.id
            WHERE s.schedule_date=? AND s.status='available'
        '''
        params = [schedule_date.isoformat()]
        
        if chair_id:
            sql += " AND s.chair_id=?"
            params.append(chair_id)
        
        sql += " ORDER BY s.chair_id, s.start_time"
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_upcoming_schedules(self, days: int = 7) -> List[Dict]:
        today = date.today()
        end_date = today + timedelta(days=days)
        
        cursor = self.db.execute('''
            SELECT s.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM schedules s
            LEFT JOIN patients p ON s.patient_id = p.id
            LEFT JOIN chairs c ON s.chair_id = c.id
            WHERE s.schedule_date BETWEEN ? AND ? AND s.status='booked'
            ORDER BY s.schedule_date, s.start_time
        ''', (today.isoformat(), end_date.isoformat()))
        return [dict(row) for row in cursor.fetchall()]

    def get_dedup_logs(self, days: int = 30, chair_id: Optional[int] = None) -> List[Dict]:
        """获取去重合并日志记录"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        sql = '''
            SELECT l.*, c.name as chair_name, p.name as patient_name
            FROM schedule_dedup_log l
            LEFT JOIN chairs c ON l.chair_id = c.id
            LEFT JOIN patients p ON l.kept_patient_id = p.id
            WHERE l.merge_time >= ?
        '''
        params = [start_date.isoformat()]
        
        if chair_id:
            sql += " AND l.chair_id = ?"
            params.append(chair_id)
        
        sql += " ORDER BY l.merge_time DESC, l.id DESC"
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_dedup_summary(self, days: int = 30) -> Dict:
        """获取去重合并统计摘要"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        cursor = self.db.execute('''
            SELECT 
                COUNT(*) as merge_count,
                COALESCE(SUM(merged_count), 0) as total_merged,
                COALESCE(SUM(CASE WHEN kept_patient_id IS NOT NULL THEN 1 ELSE 0 END), 0) as kept_patient_count
            FROM schedule_dedup_log
            WHERE merge_time >= ?
        ''', (start_date.isoformat(),))
        result = dict(cursor.fetchone())
        result['days'] = days
        return result


class QueueManager:
    def __init__(self, db: Database):
        self.db = db

    def add_to_queue(self, patient_id: int, schedule_id: Optional[int] = None,
                     chair_id: Optional[int] = None, patient_type: str = "normal",
                     is_jump: bool = False) -> Dict:
        priority = self._get_priority(patient_type)
        can_jump = self._can_jump(patient_type)
        
        if is_jump and not can_jump:
            raise ValueError(f"患者类型 {patient_type} 不允许插队")
        
        queue_number = self._get_next_queue_number()
        is_jumped = 1 if is_jump else 0
        
        cursor = self.db.execute('''
            INSERT INTO queue 
            (patient_id, schedule_id, queue_number, priority, patient_type, 
             status, chair_id, is_jumped)
            VALUES (?, ?, ?, ?, ?, 'waiting', ?, ?)
        ''', (patient_id, schedule_id, queue_number, priority, 
              patient_type, chair_id, is_jumped))
        self.db.commit()
        
        return self.get_queue_item(cursor.lastrowid)

    def _get_next_queue_number(self) -> int:
        today = date.today().isoformat()
        cursor = self.db.execute('''
            SELECT COALESCE(MAX(queue_number), 0) + 1 as next_num
            FROM queue
            WHERE DATE(checkin_time) = ?
        ''', (today,))
        return cursor.fetchone()['next_num']

    def _get_priority(self, patient_type: str) -> int:
        cursor = self.db.execute(
            "SELECT priority_level FROM priority_rules WHERE patient_type=?",
            (patient_type,)
        )
        row = cursor.fetchone()
        return row['priority_level'] if row else 0

    def _can_jump(self, patient_type: str) -> bool:
        cursor = self.db.execute(
            "SELECT can_jump FROM priority_rules WHERE patient_type=?",
            (patient_type,)
        )
        row = cursor.fetchone()
        return row['can_jump'] == 1 if row else False

    def call_next(self, chair_id: Optional[int] = None) -> Optional[Dict]:
        sql = '''
            SELECT q.*, p.name as patient_name, p.phone as patient_phone
            FROM queue q
            LEFT JOIN patients p ON q.patient_id = p.id
            WHERE q.status='waiting'
        '''
        params = []
        
        if chair_id:
            sql += " AND (q.chair_id=? OR q.chair_id IS NULL)"
            params.append(chair_id)
        
        sql += " ORDER BY q.priority DESC, q.is_jumped DESC, q.queue_number ASC LIMIT 1"
        
        cursor = self.db.execute(sql, params)
        row = cursor.fetchone()
        
        if row:
            queue_id = row['id']
            self.db.execute('''
                UPDATE queue 
                SET status='called', called_time=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (queue_id,))
            self.db.commit()
            return dict(row)
        return None

    def complete_queue(self, queue_id: int):
        self.db.execute('''
            UPDATE queue 
            SET status='completed', completed_time=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (queue_id,))
        self.db.commit()

    def cancel_queue(self, queue_id: int):
        self.db.execute("UPDATE queue SET status='cancelled' WHERE id=?", (queue_id,))
        self.db.commit()

    def get_waiting_queue(self, chair_id: Optional[int] = None) -> List[Dict]:
        sql = '''
            SELECT q.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM queue q
            LEFT JOIN patients p ON q.patient_id = p.id
            LEFT JOIN chairs c ON q.chair_id = c.id
            WHERE q.status='waiting'
        '''
        params = []
        
        if chair_id:
            sql += " AND (q.chair_id=? OR q.chair_id IS NULL)"
            params.append(chair_id)
        
        sql += " ORDER BY q.priority DESC, q.is_jumped DESC, q.queue_number ASC"
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_queue_item(self, queue_id: int) -> Optional[Dict]:
        cursor = self.db.execute('''
            SELECT q.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM queue q
            LEFT JOIN patients p ON q.patient_id = p.id
            LEFT JOIN chairs c ON q.chair_id = c.id
            WHERE q.id=?
        ''', (queue_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_today_queue(self) -> List[Dict]:
        today = date.today().isoformat()
        cursor = self.db.execute('''
            SELECT q.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM queue q
            LEFT JOIN patients p ON q.patient_id = p.id
            LEFT JOIN chairs c ON q.chair_id = c.id
            WHERE DATE(q.checkin_time) = ?
            ORDER BY q.priority DESC, q.is_jumped DESC, q.queue_number ASC
        ''', (today,))
        return [dict(row) for row in cursor.fetchall()]

    def jump_queue(self, queue_id: int) -> bool:
        queue_item = self.get_queue_item(queue_id)
        if not queue_item:
            return False
        
        if not self._can_jump(queue_item['patient_type']):
            raise ValueError("该患者类型不允许插队")
        
        if queue_item['status'] != 'waiting':
            raise ValueError("只有等待中的患者才能插队")
        
        # 号码保持不变，设置 is_jumped=1 使其在同优先级中排最前
        self.db.execute(
            "UPDATE queue SET is_jumped = 1 WHERE id = ?",
            (queue_id,)
        )
        self.db.commit()
        return True

    def get_queue_stats(self, chair_id: Optional[int] = None, 
                        patient_type: Optional[str] = None) -> Dict[str, int]:
        """获取队列统计：等待、已叫、完成、取消数量"""
        sql = "SELECT status, COUNT(*) as cnt FROM queue WHERE DATE(checkin_time) = DATE('now')"
        params = []
        
        if chair_id:
            sql += " AND chair_id = ?"
            params.append(chair_id)
        if patient_type:
            sql += " AND patient_type = ?"
            params.append(patient_type)
        
        sql += " GROUP BY status"
        cursor = self.db.execute(sql, params)
        
        stats = {'waiting': 0, 'called': 0, 'completed': 0, 'cancelled': 0, 'total': 0}
        for row in cursor.fetchall():
            stats[row['status']] = row['cnt']
            stats['total'] += row['cnt']
        return stats

    def get_queue_by_status(self, status: str, chair_id: Optional[int] = None,
                            patient_type: Optional[str] = None) -> List[Dict]:
        """按状态+椅+类型筛选队列记录"""
        sql = '''
            SELECT q.*, p.name as patient_name, p.phone as patient_phone,
                   c.name as chair_name
            FROM queue q
            LEFT JOIN patients p ON q.patient_id = p.id
            LEFT JOIN chairs c ON q.chair_id = c.id
            WHERE DATE(q.checkin_time) = DATE('now') AND q.status = ?
        '''
        params = [status]
        
        if chair_id:
            sql += " AND q.chair_id = ?"
            params.append(chair_id)
        if patient_type:
            sql += " AND q.patient_type = ?"
            params.append(patient_type)
        
        sql += " ORDER BY q.priority DESC, q.is_jumped DESC, q.queue_number ASC"
        cursor = self.db.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


class ReminderManager:
    def __init__(self, db: Database):
        self.db = db

    def create_reminder(self, schedule_id: int, patient_id: int, 
                        reminder_time: datetime, message: str = "") -> int:
        cursor = self.db.execute('''
            INSERT INTO reminders (schedule_id, patient_id, reminder_time, message)
            VALUES (?, ?, ?, ?)
        ''', (schedule_id, patient_id, reminder_time.isoformat(), message))
        self.db.commit()
        return cursor.lastrowid

    def generate_reminders_for_schedule(self, schedule_id: int) -> int:
        schedule = ScheduleManager(self.db).get_schedule(schedule_id)
        if not schedule or not schedule['patient_id']:
            return 0
        
        schedule_dt = datetime.fromisoformat(
            f"{schedule['schedule_date']} {schedule['start_time']}"
        )
        minutes_before = self._get_reminder_minutes()
        reminder_time = schedule_dt - timedelta(minutes=minutes_before)
        
        message = f"复诊提醒：您的复诊时间是 {schedule['schedule_date']} {schedule['start_time']}，请准时到达。"
        
        return self.create_reminder(schedule_id, schedule['patient_id'], 
                                     reminder_time, message)

    def generate_batch_reminders(self, days: int = 1) -> int:
        schedules = ScheduleManager(self.db).get_upcoming_schedules(days)
        count = 0
        for schedule in schedules:
            if schedule['patient_id']:
                self.generate_reminders_for_schedule(schedule['id'])
                count += 1
        return count

    def _get_reminder_minutes(self) -> int:
        cursor = self.db.execute(
            "SELECT value FROM settings WHERE key='reminder_minutes_before'"
        )
        row = cursor.fetchone()
        return int(row['value']) if row else 30

    def get_pending_reminders(self) -> List[Dict]:
        now = datetime.now().isoformat()
        cursor = self.db.execute('''
            SELECT r.*, p.name as patient_name, p.phone as patient_phone,
                   s.schedule_date, s.start_time, c.name as chair_name
            FROM reminders r
            LEFT JOIN patients p ON r.patient_id = p.id
            LEFT JOIN schedules s ON r.schedule_id = s.id
            LEFT JOIN chairs c ON s.chair_id = c.id
            WHERE r.status='pending' AND r.reminder_time <= ?
            ORDER BY r.reminder_time
        ''', (now,))
        return [dict(row) for row in cursor.fetchall()]

    def mark_reminder_sent(self, reminder_id: int):
        self.db.execute('''
            UPDATE reminders SET status='sent', sent_time=CURRENT_TIMESTAMP WHERE id=?
        ''', (reminder_id,))
        self.db.commit()

    def get_all_reminders(self, limit: int = 100) -> List[Dict]:
        cursor = self.db.execute('''
            SELECT r.*, p.name as patient_name, p.phone as patient_phone,
                   s.schedule_date, s.start_time, c.name as chair_name
            FROM reminders r
            LEFT JOIN patients p ON r.patient_id = p.id
            LEFT JOIN schedules s ON r.schedule_id = s.id
            LEFT JOIN chairs c ON s.chair_id = c.id
            ORDER BY r.reminder_time DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]


class PriorityRuleManager:
    def __init__(self, db: Database):
        self.db = db

    def get_all_rules(self) -> List[Dict]:
        cursor = self.db.execute(
            "SELECT * FROM priority_rules ORDER BY priority_level DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_rule(self, rule_id: int) -> Optional[Dict]:
        cursor = self.db.execute("SELECT * FROM priority_rules WHERE id=?", (rule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_rule_by_type(self, patient_type: str) -> Optional[Dict]:
        cursor = self.db.execute(
            "SELECT * FROM priority_rules WHERE patient_type=?", (patient_type,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


db = Database()
chair_manager = ChairManager(db)
patient_manager = PatientManager(db)
cycle_rule_manager = CycleRuleManager(db)
schedule_manager = ScheduleManager(db)
queue_manager = QueueManager(db)
reminder_manager = ReminderManager(db)
priority_rule_manager = PriorityRuleManager(db)
