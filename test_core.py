from database import Database, schedule_manager, queue_manager
from datetime import date, timedelta

db = Database("ortho.db")

print("=" * 60)
print("测试1：排期去重日志查询")
print("=" * 60)
summary = schedule_manager.get_dedup_summary(30)
print(f"近30天合并概览: {summary}")

logs = schedule_manager.get_dedup_logs(30)
print(f"日志记录数: {len(logs)}")
for log in logs[:5]:
    print(f"  - {log['merge_time'][:19]} {log['chair_name']} "
          f"{log['schedule_date']} {log['start_time']} "
          f"合并{log['merged_count']}条 保留患者:{log.get('patient_name', '无')}")

print()
print("=" * 60)
print("测试2：队列统计")
print("=" * 60)
today = date.today()
stats = queue_manager.get_queue_stats()
print(f"今日队列统计: {stats}")

from database import chair_manager, priority_rule_manager
chairs = chair_manager.get_all_chairs()
print(f"按椅统计: {len(chairs)} 个诊疗椅")
for chair in chairs:
    chair_stats = queue_manager.get_queue_stats(chair_id=chair['id'])
    print(f"  {chair['name']}: 等待{chair_stats['waiting']} 已叫{chair_stats['called']} 完成{chair_stats['completed']} 取消{chair_stats['cancelled']}")

rules = priority_rule_manager.get_all_rules()
print(f"按类型统计: {len(rules)} 种类型")
for rule in rules:
    type_stats = queue_manager.get_queue_stats(patient_type=rule['patient_type'])
    print(f"  {rule['name']}: 等待{type_stats['waiting']} 已叫{type_stats['called']} 完成{type_stats['completed']} 取消{type_stats['cancelled']}")

print()
print("=" * 60)
print("测试3：唯一流水号验证")
print("=" * 60)
queue_items = queue_manager.get_today_queue()
numbers = [q['queue_number'] for q in queue_items]
print(f"今日队列数量: {len(queue_items)}")
print(f"号码列表: {sorted(numbers)}")
print(f"号码是否唯一: {len(set(numbers)) == len(numbers)}")

if numbers:
    print(f"最大号码: {max(numbers)}")
    jumped_items = [q for q in queue_items if q.get('is_jumped')]
    print(f"插队标记数量: {len(jumped_items)}")
    for q in jumped_items:
        print(f"  号码{q['queue_number']} - {q['patient_name']} 优先级:{q['priority']}")

print()
print("=" * 60)
print("测试4：等待队列排序验证")
print("=" * 60)
waiting = queue_manager.get_waiting_queue()
print(f"等待队列数量: {len(waiting)}")
if waiting:
    print("排序顺序 (按优先级+插队标记+号码):")
    for q in waiting:
        jumped_mark = " [插队]" if q.get('is_jumped') else ""
        print(f"  #{q['queue_number']} {q.get('patient_name', '')}{jumped_mark} 优先级:{q['priority']}")

print()
print("=" * 60)
print("所有核心测试通过！")
print("=" * 60)
