from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QStackedWidget,
    QMessageBox, QStatusBar, QMenuBar, QMenu, QToolBar, QStatusBar
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QFont, QColor, QPalette
from datetime import datetime, date
import sys

from schedule_module import ScheduleModule
from cycle_module import CycleModule
from queue_module import QueueModule
from reminder_module import ReminderModule
from database import (
    db, chair_manager, patient_manager, cycle_rule_manager,
    schedule_manager, queue_manager, priority_rule_manager
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("口腔正畸复诊管理系统")
        self.resize(1280, 800)
        
        self.init_ui()
        self.init_sample_data()
        self.update_status_bar()
        
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(1000)
    
    def init_ui(self):
        self.create_menu()
        self.create_toolbar()
        self.create_central_widget()
        self.create_statusbar()
    
    def create_menu(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("文件(&F)")
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        system_menu = menubar.addMenu("系统(&S)")
        
        init_data_action = QAction("初始化示例数据", self)
        init_data_action.triggered.connect(self.init_sample_data)
        system_menu.addAction(init_data_action)
        
        clear_data_action = QAction("清空所有数据", self)
        clear_data_action.triggered.connect(self.clear_all_data)
        system_menu.addAction(clear_data_action)
        
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        schedule_action = QAction("复诊排期", self)
        schedule_action.triggered.connect(lambda: self.switch_module(0))
        toolbar.addAction(schedule_action)
        
        cycle_action = QAction("周期生成", self)
        cycle_action.triggered.connect(lambda: self.switch_module(1))
        toolbar.addAction(cycle_action)
        
        queue_action = QAction("排队叫号", self)
        queue_action.triggered.connect(lambda: self.switch_module(2))
        toolbar.addAction(queue_action)
        
        reminder_action = QAction("复诊提醒", self)
        reminder_action.triggered.connect(lambda: self.switch_module(3))
        toolbar.addAction(reminder_action)
        
        toolbar.addSeparator()
        
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_current_module)
        toolbar.addAction(refresh_action)
    
    def create_central_widget(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setIconSize(QSize(24, 24))
        self.nav_list.setFont(QFont("Arial", 10))
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: none;
                border-right: 1px solid #ddd;
            }
            QListWidget::item {
                padding: 12px;
                padding-left: 20px;
                border-bottom: 1px solid #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #1976D2;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #e3f2fd;
            }
        """)
        
        modules = [
            ("📅 复诊排期", "管理诊疗椅、周期规则和排期"),
            ("🔄 周期生成", "按周期批量生成排期和患者周期排期"),
            ("📢 排队叫号", "患者取号、叫号和优先插队处理"),
            ("🔔 复诊提醒", "提醒生成、发送和设置"),
        ]
        
        for name, desc in modules:
            item = QListWidgetItem(name)
            item.setToolTip(desc)
            item.setTextAlignment(Qt.AlignVCenter)
            self.nav_list.addItem(item)
        
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.switch_module)
        
        self.stack = QStackedWidget()
        
        self.schedule_module = ScheduleModule()
        self.cycle_module = CycleModule()
        self.queue_module = QueueModule()
        self.reminder_module = ReminderModule()
        
        self.stack.addWidget(self.schedule_module)
        self.stack.addWidget(self.cycle_module)
        self.stack.addWidget(self.queue_module)
        self.stack.addWidget(self.reminder_module)
        
        main_layout.addWidget(self.nav_list)
        main_layout.addWidget(self.stack, 1)
        
        self.setCentralWidget(central_widget)
    
    def create_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        self.time_label = QLabel()
        self.statusbar.addPermanentWidget(self.time_label)
        
        self.stats_label = QLabel()
        self.statusbar.addPermanentWidget(self.stats_label, 1)
    
    def update_status_bar(self):
        now = datetime.now()
        self.time_label.setText(now.strftime("%Y-%m-%d %H:%M:%S"))
        
        today = date.today()
        schedules = schedule_manager.get_schedules_by_date(today)
        booked = len([s for s in schedules if s['status'] == 'booked'])
        waiting = len(queue_manager.get_waiting_queue())
        
        today_queue = queue_manager.get_today_queue()
        completed = len([q for q in today_queue if q['status'] == 'completed'])
        
        self.stats_label.setText(
            f"今日预约: {booked} 人 | 等待中: {waiting} 人 | 已完成: {completed} 人"
        )
    
    def switch_module(self, index):
        self.nav_list.blockSignals(True)
        self.nav_list.setCurrentRow(index)
        self.nav_list.blockSignals(False)
        self.stack.setCurrentIndex(index)
        self.refresh_current_module()
    
    def refresh_current_module(self):
        current_index = self.stack.currentIndex()
        if current_index == 0:
            self.schedule_module.load_data()
        elif current_index == 1:
            self.cycle_module.load_data()
        elif current_index == 2:
            self.queue_module.load_data()
        elif current_index == 3:
            self.reminder_module.load_data()
    
    def init_sample_data(self):
        reply = QMessageBox.question(self, "初始化数据", 
            "是否初始化示例数据？\n\n这将创建一些示例的诊疗椅、患者、周期规则等数据，方便您体验系统功能。",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        try:
            cursor = db.execute("SELECT COUNT(*) FROM chairs")
            if cursor.fetchone()[0] > 0:
                QMessageBox.information(self, "提示", "数据已存在，跳过初始化")
                return
            
            chairs = [
                ("诊疗椅1", "正畸科1号椅"),
                ("诊疗椅2", "正畸科2号椅"),
                ("诊疗椅3", "正畸科3号椅"),
                ("VIP诊疗室", "VIP专属诊疗室"),
            ]
            
            for name, desc in chairs:
                chair_manager.add_chair(name, desc)
            
            patients = [
                ("张三", "13800138001", "normal", "矫治初期"),
                ("李四", "13800138002", "normal", "矫治中期"),
                ("王五", "13800138003", "priority", "矫治后期"),
                ("赵六", "13800138004", "vip", "VIP会员"),
                ("钱七", "13800138005", "emergency", "急诊患者"),
                ("孙八", "13800138006", "normal", "保持期"),
                ("周九", "13800138007", "vip", "VIP会员"),
                ("吴十", "13800138008", "normal", "矫治初期"),
            ]
            
            for name, phone, ptype, stage in patients:
                patient_manager.add_patient(name, phone, ptype, stage)
            
            chairs_list = chair_manager.get_all_chairs()
            chair_map = {c['name']: c['id'] for c in chairs_list}
            
            rules = [
                ("周一上午常规", chair_map["诊疗椅1"], 0, "08:00", "12:00", 30, "normal"),
                ("周一下午常规", chair_map["诊疗椅1"], 0, "14:00", "17:30", 30, "normal"),
                ("周二上午常规", chair_map["诊疗椅2"], 1, "08:00", "12:00", 30, "normal"),
                ("周三VIP专场", chair_map["VIP诊疗室"], 2, "09:00", "12:00", 45, "vip"),
                ("周四上午常规", chair_map["诊疗椅3"], 3, "08:00", "12:00", 30, "normal"),
                ("周四下午优先", chair_map["诊疗椅3"], 3, "14:00", "17:30", 30, "priority"),
                ("周五上午常规", chair_map["诊疗椅1"], 4, "08:00", "12:00", 30, "normal"),
                ("周六上午综合", None, 5, "08:30", "12:00", 30, "normal"),
            ]
            
            for name, chair_id, day, start, end, interval, ptype in rules:
                cycle_rule_manager.add_rule(name, chair_id, day, start, end, interval, ptype)
            
            today = date.today()
            next_30 = today + __import__('datetime').timedelta(days=30)
            
            for rule in cycle_rule_manager.get_all_rules():
                schedule_manager.generate_cycle_schedules(
                    rule['id'], today, next_30
                )
            
            patients_list = patient_manager.get_all_patients()
            schedules = schedule_manager.get_upcoming_schedules(days=7)
            
            if schedules and patients_list:
                for i, sched in enumerate(schedules[:10]):
                    patient = patients_list[i % len(patients_list)]
                    schedule_manager.book_schedule(
                        sched['id'], patient['id'], patient['patient_type']
                    )
            
            QMessageBox.information(self, "成功", 
                "示例数据初始化完成！\n\n已创建：\n- 4 台诊疗椅\n- 8 位示例患者\n- 8 条周期规则\n- 未来30天的排期时段\n- 部分已预约的复诊")
            
            self.refresh_current_module()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化数据失败: {str(e)}")
    
    def clear_all_data(self):
        reply = QMessageBox.question(self, "确认", 
            "确定要清空所有数据吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        reply2 = QMessageBox.question(self, "再次确认", 
            "真的要清空所有数据吗？\n\n所有诊疗椅、患者、排期、队列等数据都将被删除！",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply2 != QMessageBox.Yes:
            return
        
        try:
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row['name'] for row in cursor.fetchall()]
            
            for table in tables:
                db.execute(f"DELETE FROM {table}")
                db.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            
            db.commit()
            db._init_default_data()
            
            QMessageBox.information(self, "成功", "所有数据已清空")
            self.refresh_current_module()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清空数据失败: {str(e)}")
    
    def show_about(self):
        QMessageBox.about(self, "关于",
            """<h2>口腔正畸复诊管理系统</h2>
            <p>版本: 1.0.0</p>
            <p>功能模块：</p>
            <ul>
            <li><b>复诊排期</b> - 诊疗椅管理、周期规则设定、排期管理</li>
            <li><b>周期生成</b> - 按周期批量生成排期、患者周期排期</li>
            <li><b>排队叫号</b> - 患者取号、优先级队列、叫号、VIP/急诊插队</li>
            <li><b>复诊提醒</b> - 自动提醒、批量发送、提醒设置</li>
            </ul>
            <p>技术栈: Python + PySide6 + SQLite</p>
            """)
    
    def closeEvent(self, event):
        reply = QMessageBox.question(self, "退出", "确定要退出系统吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            db.close()
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(250, 250, 250))
    palette.setColor(QPalette.WindowText, QColor(33, 33, 33))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(33, 33, 33))
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, QColor(33, 33, 33))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(25, 118, 210))
    palette.setColor(QPalette.Highlight, QColor(25, 118, 210))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
