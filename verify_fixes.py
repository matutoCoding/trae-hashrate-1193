"""验证脚本：只加载 database 模块测试迁移，不启动 GUI"""
from database import Database, ScheduleManager, chair_manager
from datetime import date

print("正在加载 database 模块（会触发迁移）...\n")

db = Database()
schedule_mgr = ScheduleManager(db)

# 检查迁移后的状态
print("=== 迁移后检查 ===")
cursor = db.execute("SELECT COUNT(*) as cnt FROM schedules")
print(f"schedules 总数: {cursor.fetchone()['cnt']}")

print("\n所有时段（应该只剩3条，不重复）:")
cursor = db.execute('''
    SELECT s.*, p.name as patient_name
    FROM schedules s LEFT JOIN patients p ON s.patient_id = p.id
    ORDER BY s.start_time
''')
for row in cursor.fetchall():
    print(f"  {row['start_time']}-{row['end_time']} | {row['status']} | {row['patient_name'] or '无'} | patient_type={row['patient_type']}")

print("\n检查是否还有重复:")
cursor = db.execute('''
    SELECT chair_id, schedule_date, start_time, COUNT(*) as cnt
    FROM schedules GROUP BY chair_id, schedule_date, start_time HAVING COUNT(*) > 1
''')
dups = cursor.fetchall()
if dups:
    print("  ❌ 仍有重复！")
    for d in dups:
        print(f"    椅{d['chair_id']} {d['schedule_date']} {d['start_time']} → {d['cnt']} 条")
else:
    print("  ✅ 无重复时段")

# 检查 09:00 是否正确保留了李四的 booked
print("\n检查 09:00 时段（应为李四 booked VIP）:")
cursor = db.execute('''
    SELECT s.*, p.name as patient_name
    FROM schedules s LEFT JOIN patients p ON s.patient_id = p.id
    WHERE s.start_time = '09:00'
''')
row = cursor.fetchone()
if row:
    ok = row['status'] == 'booked' and row['patient_name'] == '李四' and row['patient_type'] == 'vip'
    print(f"  {'✅' if ok else '❌'} status={row['status']}, patient={row['patient_name']}, type={row['patient_type']}")

# 检查 reminders 是否正确转移
print("\n检查 reminders 关联:")
cursor = db.execute('''
    SELECT r.id, r.schedule_id, s.start_time, s.status
    FROM reminders r LEFT JOIN schedules s ON r.schedule_id = s.id
''')
for row in cursor.fetchall():
    print(f"  reminder#{row['id']} → schedule#{row['schedule_id']} ({row['start_time']} {row['status']})")

# --- 测试 1: 插队号码唯一性 ---
print("\n\n=== 测试 1: 插队号码唯一性 ===")
from database import queue_manager, patient_manager

patients = patient_manager.get_all_patients()
for p in patients:
    print(f"  患者 {p['id']}: {p['name']} ({p['patient_type']})")

# 加3个普通患者
q1 = queue_manager.add_to_queue(1, None, None, 'normal', False)
print(f"  普通患者取号 → 号码: {q1['queue_number']}")

q2 = queue_manager.add_to_queue(1, None, None, 'normal', False)
print(f"  普通患者取号 → 号码: {q2['queue_number']}")

q3 = queue_manager.add_to_queue(1, None, None, 'normal', False)
print(f"  普通患者取号 → 号码: {q3['queue_number']}")

# VIP 插队
q_vip = queue_manager.add_to_queue(2, None, None, 'vip', True)
print(f"  VIP 插队 → 号码: {q_vip['queue_number']}")

# 查看等待队列
print("\n  插队后等待队列（按顺序）:")
waiting = queue_manager.get_waiting_queue()
for q in waiting:
    print(f"    #{q['queue_number']} {q['patient_name']} ({q['patient_type']}) priority={q['priority']}")

# 检查号码是否唯一
nums = [q['queue_number'] for q in waiting]
print(f"  号码列表: {nums}")
print(f"  {'✅ 号码全部唯一' if len(nums) == len(set(nums)) else '❌ 号码重复！'}")

# --- 测试 2: 重复生成排期 ---
print("\n\n=== 测试 2: 重复生成排期统计 ===")
# 先造一条周期规则
from database import cycle_rule_manager
rule_id = cycle_rule_manager.add_rule(
    name="测试周一上午",
    chair_id=1,
    day_of_week=0,
    start_time="08:00",
    end_time="09:00",
    interval_minutes=30,
    patient_type="normal"
)
print(f"  创建周期规则 ID={rule_id}")

from datetime import date, timedelta
today = date.today()
# 找下一个周一
next_monday = today + timedelta(days=(0 - today.weekday() + 7) % 7)
end = next_monday + timedelta(days=7)  # 覆盖2个周一

# 第一次生成
added1, total1 = schedule_mgr.generate_cycle_schedules(rule_id, next_monday, end, None)
print(f"  第1次生成: 新增={added1}, 总数={total1}, 跳过={total1-added1}")

# 第二次生成（相同参数）
added2, total2 = schedule_mgr.generate_cycle_schedules(rule_id, next_monday, end, None)
print(f"  第2次生成: 新增={added2}, 总数={total2}, 跳过={total2-added2}")

if added2 == 0 and total2 == total1:
    print("  ✅ 第二次生成新增为0，正确识别已存在的时段")
else:
    print("  ❌ 第二次生成结果不正确")

print("\n=== 所有测试完成 ===")
db.close()
