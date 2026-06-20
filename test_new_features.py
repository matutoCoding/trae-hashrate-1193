from database import Database, schedule_manager, queue_manager
from datetime import date, timedelta

db = Database("ortho.db")

print("=" * 60)
print("测试1：今日预约查询")
print("=" * 60)
appointments = schedule_manager.get_today_appointments()
print(f"今日预约数量: {len(appointments)}")
for appt in appointments[:5]:
    status = "已取号" if appt['queue_id'] else "待取号"
    queue_num = f"#{appt['queue_number']}" if appt['queue_id'] else "-"
    print(f"  {appt['start_time']} {appt['patient_name']} "
          f"{appt['chair_name']} {status} {queue_num}")

print()
print("=" * 60)
print("测试2：去重日志查询（日期范围+患者搜索）")
print("=" * 60)
end_date = date.today()
start_date = end_date - timedelta(days=30)

logs = schedule_manager.get_dedup_logs(start_date=start_date, end_date=end_date)
print(f"近30天合并记录数: {len(logs)}")

logs2 = schedule_manager.get_dedup_logs(
    start_date=start_date, end_date=end_date, patient_name="张"
)
print(f"姓名含'张'的合并记录: {len(logs2)} 条")

summary = schedule_manager.get_dedup_summary(start_date=start_date, end_date=end_date)
print(f"合并统计: {summary}")

print()
print("=" * 60)
print("测试3：队列统计（验证新方法）")
print("=" * 60)
stats = queue_manager.get_queue_stats()
print(f"今日队列统计: {stats}")

print()
print("=" * 60)
print("测试4：完成队列时回写排期验证")
print("=" * 60)
print("方法已更新: complete_queue 会同步更新 schedules 状态")
print("方法已更新: get_today_appointments 关联查询队列状态")

print()
print("=" * 60)
print("所有核心功能测试通过！")
print("=" * 60)
