from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QTimeEdit, QDateEdit, QMessageBox, QLabel, QHeaderView,
    QTabWidget, QGroupBox, QTextEdit, QCheckBox, QListWidget, QListWidgetItem,
    QSplitter, QProgressDialog, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, QDate, QTime, QTimer
from PySide6.QtGui import QColor, QBrush, QFont
from datetime import date, datetime, timedelta
from database import (
    chair_manager, patient_manager, cycle_rule_manager, 
    schedule_manager, queue_manager, priority_rule_manager
)


class CycleGenerateDialog(QDialog):
    def __init__(self, parent=None, rule=None):
        super().__init__(parent)
        self.rule = rule
        self.setWindowTitle("批量生成排期")
        self.setModal(True)
        self.resize(500, 450)
        
        layout = QFormLayout()
        
        self.rule_combo = QComboBox()
        self.load_rules()
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        default_end = date.today() + timedelta(days=90)
        self.end_date.setDate(QDate(default_end.year, default_end.month, default_end.day))
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        
        self.patient_combo = QComboBox()
        self.patient_combo.setEditable(True)
        self.patient_combo.addItem("不指定患者（生成空时段）", None)
        self.load_patients()
        
        self.generate_reminder_check = QCheckBox("自动生成复诊提醒")
        self.generate_reminder_check.setChecked(True)
        
        layout.addRow("周期规则:", self.rule_combo)
        layout.addRow("开始日期:", self.start_date)
        layout.addRow("结束日期:", self.end_date)
        layout.addRow("指定患者:", self.patient_combo)
        layout.addRow("", self.generate_reminder_check)
        
        self.preview_btn = QPushButton("预览生成数量")
        layout.addRow("", self.preview_btn)
        
        self.preview_label = QLabel("预计生成: 0 个时段")
        self.preview_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addRow("", self.preview_label)
        
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.generate_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.preview_btn.clicked.connect(self.preview_generate)
        
        if rule:
            idx = self.rule_combo.findData(rule['id'])
            if idx >= 0:
                self.rule_combo.setCurrentIndex(idx)
    
    def load_rules(self):
        self.rule_combo.clear()
        rules = cycle_rule_manager.get_all_rules()
        for rule in rules:
            display = f"{rule['name']} - {self._get_day_name(rule['day_of_week'])} {rule['start_time']}-{rule['end_time']}"
            self.rule_combo.addItem(display, rule['id'])
    
    def _get_day_name(self, day_idx):
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return days[day_idx]
    
    def load_patients(self):
        patients = patient_manager.get_all_patients()
        for patient in patients:
            display = f"{patient['name']} ({patient['phone'] or '无电话'})"
            self.patient_combo.addItem(display, patient['id'])
    
    def preview_generate(self):
        rule_id = self.rule_combo.currentData()
        if not rule_id:
            QMessageBox.warning(self, "提示", "请选择周期规则")
            return
        
        rule = cycle_rule_manager.get_rule(rule_id)
        if not rule:
            return
        
        qstart = self.start_date.date()
        qend = self.end_date.date()
        
        start_date = date(qstart.year(), qstart.month(), qstart.day())
        end_date = date(qend.year(), qend.month(), qend.day())
        
        if end_date < start_date:
            QMessageBox.warning(self, "提示", "结束日期不能早于开始日期")
            return
        
        count = 0
        current = start_date
        while current <= end_date:
            if current.weekday() == rule['day_of_week']:
                start = datetime.strptime(rule['start_time'], '%H:%M')
                end = datetime.strptime(rule['end_time'], '%H:%M')
                interval = timedelta(minutes=rule['interval_minutes'])
                slots = 0
                current_time = start
                while current_time < end:
                    slots += 1
                    current_time += interval
                count += slots
            current += timedelta(days=1)
        
        self.preview_label.setText(f"预计生成: {count} 个时段 (覆盖 {self._count_weeks(start_date, end_date, rule['day_of_week'])} 周)")
    
    def _count_weeks(self, start, end, day_of_week):
        count = 0
        current = start
        while current <= end:
            if current.weekday() == day_of_week:
                count += 1
            current += timedelta(days=1)
        return count
    
    def get_data(self):
        return {
            'rule_id': self.rule_combo.currentData(),
            'start_date': date(self.start_date.date().year(), 
                              self.start_date.date().month(), 
                              self.start_date.date().day()),
            'end_date': date(self.end_date.date().year(), 
                            self.end_date.date().month(), 
                            self.end_date.date().day()),
            'patient_id': self.patient_combo.currentData(),
            'generate_reminder': self.generate_reminder_check.isChecked()
        }


class BatchGenerateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量生成空时段")
        self.setModal(True)
        self.resize(500, 450)
        
        layout = QFormLayout()
        
        self.chair_combo = QComboBox()
        self.load_chairs()
        
        self.day_combo = QComboBox()
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, day in enumerate(days):
            self.day_combo.addItem(day, i)
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        default_end = date.today() + timedelta(days=30)
        self.end_date.setDate(QDate(default_end.year, default_end.month, default_end.day))
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setTime(QTime(8, 0))
        
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        self.end_time.setTime(QTime(12, 0))
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 120)
        self.interval_spin.setSuffix(" 分钟")
        self.interval_spin.setValue(30)
        
        layout.addRow("诊疗椅:", self.chair_combo)
        layout.addRow("每周:", self.day_combo)
        layout.addRow("开始日期:", self.start_date)
        layout.addRow("结束日期:", self.end_date)
        layout.addRow("开始时间:", self.start_time)
        layout.addRow("结束时间:", self.end_time)
        layout.addRow("间隔:", self.interval_spin)
        
        self.preview_btn = QPushButton("预览生成数量")
        layout.addRow("", self.preview_btn)
        
        self.preview_label = QLabel("预计生成: 0 个时段")
        self.preview_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addRow("", self.preview_label)
        
        btn_layout = QHBoxLayout()
        self.generate_btn = QPushButton("生成")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.generate_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.preview_btn.clicked.connect(self.preview_generate)
    
    def load_chairs(self):
        self.chair_combo.clear()
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.chair_combo.addItem(chair['name'], chair['id'])
    
    def preview_generate(self):
        chair_id = self.chair_combo.currentData()
        if not chair_id:
            QMessageBox.warning(self, "提示", "请选择诊疗椅")
            return
        
        qstart = self.start_date.date()
        qend = self.end_date.date()
        day_of_week = self.day_combo.currentData()
        
        start_date = date(qstart.year(), qstart.month(), qstart.day())
        end_date = date(qend.year(), qend.month(), qend.day())
        
        if end_date < start_date:
            QMessageBox.warning(self, "提示", "结束日期不能早于开始日期")
            return
        
        start_time = self.start_time.time().toString("HH:mm")
        end_time = self.end_time.time().toString("HH:mm")
        interval = self.interval_spin.value()
        
        count = 0
        current = start_date
        while current <= end_date:
            if current.weekday() == day_of_week:
                start = datetime.strptime(start_time, '%H:%M')
                end = datetime.strptime(end_time, '%H:%M')
                interval_td = timedelta(minutes=interval)
                slots = 0
                current_time = start
                while current_time < end:
                    slots += 1
                    current_time += interval_td
                count += slots
            current += timedelta(days=1)
        
        weeks = self._count_weeks(start_date, end_date, day_of_week)
        self.preview_label.setText(f"预计生成: {count} 个时段 (覆盖 {weeks} 周)")
    
    def _count_weeks(self, start, end, day_of_week):
        count = 0
        current = start
        while current <= end:
            if current.weekday() == day_of_week:
                count += 1
            current += timedelta(days=1)
        return count
    
    def get_data(self):
        return {
            'chair_id': self.chair_combo.currentData(),
            'day_of_week': self.day_combo.currentData(),
            'start_date': date(self.start_date.date().year(), 
                              self.start_date.date().month(), 
                              self.start_date.date().day()),
            'end_date': date(self.end_date.date().year(), 
                            self.end_date.date().month(), 
                            self.end_date.date().day()),
            'start_time': self.start_time.time().toString("HH:mm"),
            'end_time': self.end_time.time().toString("HH:mm"),
            'interval_minutes': self.interval_spin.value()
        }


class PatientBatchAssignDialog(QDialog):
    def __init__(self, parent=None, patient=None):
        super().__init__(parent)
        self.patient = patient
        self.setWindowTitle("患者批量排期")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QFormLayout()
        
        self.patient_combo = QComboBox()
        self.patient_combo.setEditable(True)
        self.load_patients()
        
        self.rule_combo = QComboBox()
        self.load_rules()
        
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        default_end = date.today() + timedelta(days=180)
        self.end_date.setDate(QDate(default_end.year, default_end.month, default_end.day))
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        
        self.cycle_weeks_spin = QSpinBox()
        self.cycle_weeks_spin.setRange(1, 52)
        self.cycle_weeks_spin.setSuffix(" 周")
        self.cycle_weeks_spin.setValue(4)
        self.cycle_weeks_spin.setToolTip("每隔多少周复诊一次")
        
        layout.addRow("患者:", self.patient_combo)
        layout.addRow("周期规则:", self.rule_combo)
        layout.addRow("开始日期:", self.start_date)
        layout.addRow("结束日期:", self.end_date)
        layout.addRow("复诊周期:", self.cycle_weeks_spin)
        
        self.generate_reminder_check = QCheckBox("自动生成复诊提醒")
        self.generate_reminder_check.setChecked(True)
        layout.addRow("", self.generate_reminder_check)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        if patient:
            idx = self.patient_combo.findData(patient['id'])
            if idx >= 0:
                self.patient_combo.setCurrentIndex(idx)
    
    def load_patients(self):
        self.patient_combo.clear()
        patients = patient_manager.get_all_patients()
        for patient in patients:
            display = f"{patient['name']} ({patient['phone'] or '无电话'})"
            self.patient_combo.addItem(display, patient['id'])
    
    def load_rules(self):
        self.rule_combo.clear()
        rules = cycle_rule_manager.get_all_rules()
        for rule in rules:
            display = f"{rule['name']} - {self._get_day_name(rule['day_of_week'])} {rule['start_time']}-{rule['end_time']}"
            self.rule_combo.addItem(display, rule['id'])
    
    def _get_day_name(self, day_idx):
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return days[day_idx]
    
    def get_data(self):
        return {
            'patient_id': self.patient_combo.currentData(),
            'rule_id': self.rule_combo.currentData(),
            'start_date': date(self.start_date.date().year(), 
                              self.start_date.date().month(), 
                              self.start_date.date().day()),
            'end_date': date(self.end_date.date().year(), 
                            self.end_date.date().month(), 
                            self.end_date.date().day()),
            'cycle_weeks': self.cycle_weeks_spin.value(),
            'generate_reminder': self.generate_reminder_check.isChecked()
        }


class CycleModule(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_schedules)
        self.refresh_timer.start(30000)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_generate_tab(), "周期批量生成")
        self.tabs.addTab(self.create_batch_tab(), "批量生成空时段")
        self.tabs.addTab(self.create_patient_cycle_tab(), "患者周期排期")
        self.tabs.addTab(self.create_schedule_list_tab(), "排期列表")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def create_generate_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        left_panel = QGroupBox("周期规则列表")
        left_layout = QVBoxLayout()
        
        self.rule_list = QListWidget()
        self.rule_list.itemDoubleClicked.connect(self.generate_from_rule)
        left_layout.addWidget(self.rule_list)
        
        btn_layout = QHBoxLayout()
        self.generate_from_rule_btn = QPushButton("按规则生成")
        self.refresh_rule_btn = QPushButton("刷新")
        btn_layout.addWidget(self.generate_from_rule_btn)
        btn_layout.addWidget(self.refresh_rule_btn)
        left_layout.addLayout(btn_layout)
        
        left_panel.setLayout(left_layout)
        left_panel.setFixedWidth(350)
        
        right_panel = QGroupBox("生成预览")
        right_layout = QVBoxLayout()
        
        self.calendar_view = QTableWidget()
        self.calendar_view.setColumnCount(7)
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        self.calendar_view.setHorizontalHeaderLabels(days)
        self.calendar_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calendar_view.verticalHeader().setDefaultSectionSize(80)
        self.calendar_view.setEditTriggers(QTableWidget.NoEditTriggers)
        self.calendar_view.setSelectionMode(QTableWidget.SingleSelection)
        right_layout.addWidget(self.calendar_view)
        
        calendar_btn_layout = QHBoxLayout()
        self.prev_week_btn = QPushButton("<< 上一周")
        self.next_week_btn = QPushButton("下一周 >>")
        self.today_btn = QPushButton("今天")
        self.refresh_calendar_btn = QPushButton("刷新")
        calendar_btn_layout.addWidget(self.prev_week_btn)
        calendar_btn_layout.addWidget(self.today_btn)
        calendar_btn_layout.addWidget(self.next_week_btn)
        calendar_btn_layout.addStretch()
        calendar_btn_layout.addWidget(self.refresh_calendar_btn)
        right_layout.addLayout(calendar_btn_layout)
        
        right_panel.setLayout(right_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 800])
        
        main_layout.addWidget(splitter)
        widget.setLayout(main_layout)
        
        self.generate_from_rule_btn.clicked.connect(self.generate_from_rule)
        self.refresh_rule_btn.clicked.connect(self.load_rules)
        self.prev_week_btn.clicked.connect(self.prev_week)
        self.next_week_btn.clicked.connect(self.next_week)
        self.today_btn.clicked.connect(self.go_today)
        self.refresh_calendar_btn.clicked.connect(self.load_calendar)
        
        self.current_week_start = date.today() - timedelta(days=date.today().weekday())
        
        return widget
    
    def create_batch_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        btn_bar = QHBoxLayout()
        self.batch_generate_btn = QPushButton("批量生成空时段")
        self.refresh_batch_btn = QPushButton("刷新")
        btn_bar.addWidget(self.batch_generate_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self.refresh_batch_btn)
        layout.addLayout(btn_bar)
        
        info_group = QGroupBox("生成说明")
        info_layout = QVBoxLayout()
        info_label = QLabel("""
        <h3>批量生成空时段功能说明</h3>
        <p>1. 选择诊疗椅和每周的固定时间</p>
        <p>2. 设置日期范围和时间段</p>
        <p>3. 系统会自动按周生成所有可预约的空时段</p>
        <p>4. 生成的时段状态为"可用"，可以后续预约患者</p>
        <p style="color: #f44336;">注意：已存在的相同时段不会重复生成</p>
        """)
        info_label.setTextFormat(Qt.RichText)
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        self.batch_result_table = QTableWidget()
        self.batch_result_table.setColumnCount(6)
        self.batch_result_table.setHorizontalHeaderLabels([
            "ID", "诊疗椅", "日期", "时段", "状态", "患者"
        ])
        self.batch_result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.batch_result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.batch_result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.batch_result_table)
        
        widget.setLayout(layout)
        
        self.batch_generate_btn.clicked.connect(self.batch_generate)
        self.refresh_batch_btn.clicked.connect(self.load_batch_results)
        
        return widget
    
    def create_patient_cycle_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        btn_bar = QHBoxLayout()
        self.patient_cycle_btn = QPushButton("患者周期排期")
        self.refresh_patient_btn = QPushButton("刷新")
        btn_bar.addWidget(self.patient_cycle_btn)
        btn_bar.addStretch()
        btn_bar.addWidget(self.refresh_patient_btn)
        layout.addLayout(btn_bar)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("患者:"))
        self.patient_filter_combo = QComboBox()
        self.patient_filter_combo.setEditable(True)
        self.patient_filter_combo.addItem("全部", None)
        self.load_patients_to_combo()
        filter_layout.addWidget(self.patient_filter_combo)
        
        filter_layout.addWidget(QLabel("日期范围:"))
        self.patient_start_date = QDateEdit()
        self.patient_start_date.setCalendarPopup(True)
        self.patient_start_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.patient_start_date)
        filter_layout.addWidget(QLabel("至"))
        self.patient_end_date = QDateEdit()
        self.patient_end_date.setCalendarPopup(True)
        default_end = date.today() + timedelta(days=180)
        self.patient_end_date.setDate(QDate(default_end.year, default_end.month, default_end.day))
        filter_layout.addWidget(self.patient_end_date)
        
        self.apply_patient_filter_btn = QPushButton("查询")
        filter_layout.addWidget(self.apply_patient_filter_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        self.patient_schedule_table = QTableWidget()
        self.patient_schedule_table.setColumnCount(8)
        self.patient_schedule_table.setHorizontalHeaderLabels([
            "ID", "患者", "诊疗椅", "日期", "时段", "患者类型", "状态", "操作"
        ])
        self.patient_schedule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.patient_schedule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.patient_schedule_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.patient_schedule_table)
        
        widget.setLayout(layout)
        
        self.patient_cycle_btn.clicked.connect(self.patient_cycle_schedule)
        self.refresh_patient_btn.clicked.connect(self.load_patient_schedules)
        self.apply_patient_filter_btn.clicked.connect(self.load_patient_schedules)
        
        return widget
    
    def create_schedule_list_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("日期:"))
        self.list_date = QDateEdit()
        self.list_date.setCalendarPopup(True)
        self.list_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.list_date)
        
        filter_layout.addWidget(QLabel("诊疗椅:"))
        self.list_chair = QComboBox()
        self.list_chair.addItem("全部", None)
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.list_chair.addItem(chair['name'], chair['id'])
        filter_layout.addWidget(self.list_chair)
        
        filter_layout.addWidget(QLabel("状态:"))
        self.list_status = QComboBox()
        self.list_status.addItem("全部", None)
        self.list_status.addItem("可用", "available")
        self.list_status.addItem("已预约", "booked")
        self.list_status.addItem("已完成", "completed")
        self.list_status.addItem("已取消", "cancelled")
        filter_layout.addWidget(self.list_status)
        
        self.apply_list_filter_btn = QPushButton("查询")
        filter_layout.addWidget(self.apply_list_filter_btn)
        filter_layout.addStretch()
        
        self.edit_schedule_btn = QPushButton("编辑排期")
        self.delete_schedule_btn = QPushButton("删除排期")
        self.refresh_list_btn = QPushButton("刷新")
        filter_layout.addWidget(self.edit_schedule_btn)
        filter_layout.addWidget(self.delete_schedule_btn)
        filter_layout.addWidget(self.refresh_list_btn)
        
        layout.addLayout(filter_layout)
        
        self.schedule_list_table = QTableWidget()
        self.schedule_list_table.setColumnCount(8)
        self.schedule_list_table.setHorizontalHeaderLabels([
            "ID", "诊疗椅", "日期", "时段", "患者", "患者类型", "状态", "备注"
        ])
        self.schedule_list_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.schedule_list_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.schedule_list_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.schedule_list_table)
        
        widget.setLayout(layout)
        
        self.apply_list_filter_btn.clicked.connect(self.load_schedule_list)
        self.edit_schedule_btn.clicked.connect(self.edit_schedule_from_list)
        self.delete_schedule_btn.clicked.connect(self.delete_schedule_from_list)
        self.refresh_list_btn.clicked.connect(self.load_schedule_list)
        
        return widget
    
    def load_data(self):
        self.load_rules()
        self.load_calendar()
        self.load_batch_results()
        self.load_patient_schedules()
        self.load_schedule_list()
    
    def load_rules(self):
        self.rule_list.clear()
        rules = cycle_rule_manager.get_all_rules()
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        for rule in rules:
            chair_name = rule['chair_name'] or "不限"
            type_name = self._get_type_name(rule['patient_type'])
            display = f"{rule['name']}\n  {days[rule['day_of_week']]} {rule['start_time']}-{rule['end_time']}\n  {chair_name} | {type_name} | {rule['interval_minutes']}分钟"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, rule['id'])
            self.rule_list.addItem(item)
    
    def _get_type_name(self, type_key):
        rules = priority_rule_manager.get_all_rules()
        for r in rules:
            if r['patient_type'] == type_key:
                return r['name']
        return "普通患者"
    
    def load_calendar(self):
        self.calendar_view.setRowCount(0)
        self.calendar_view.setRowCount(1)
        
        week_start = self.current_week_start
        
        status_colors = {
            'available': QColor(255, 255, 255),
            'booked': QColor(173, 216, 230),
            'completed': QColor(144, 238, 144),
            'cancelled': QColor(255, 182, 193),
        }
        
        for col in range(7):
            current_date = week_start + timedelta(days=col)
            schedules = schedule_manager.get_schedules_by_date(current_date)
            
            cell_widget = QWidget()
            cell_layout = QVBoxLayout()
            cell_layout.setContentsMargins(2, 2, 2, 2)
            cell_layout.setSpacing(1)
            
            date_label = QLabel(current_date.strftime("%m-%d"))
            date_label.setAlignment(Qt.AlignCenter)
            if current_date == date.today():
                date_label.setStyleSheet("background-color: #FFEB3B; font-weight: bold;")
            else:
                date_label.setStyleSheet("font-weight: bold;")
            cell_layout.addWidget(date_label)
            
            for sched in schedules[:4]:
                sched_label = QLabel()
                if sched['patient_name']:
                    sched_text = f"{sched['start_time']} {sched['patient_name']}"
                else:
                    sched_text = f"{sched['start_time']} 空闲"
                sched_label.setText(sched_text)
                color = status_colors.get(sched['status'], QColor(255, 255, 255))
                sched_label.setStyleSheet(f"background-color: {color.name()}; padding: 2px;")
                cell_layout.addWidget(sched_label)
            
            if len(schedules) > 4:
                more_label = QLabel(f"... 还有 {len(schedules) - 4} 个")
                more_label.setAlignment(Qt.AlignCenter)
                more_label.setStyleSheet("color: #666; font-size: 10px;")
                cell_layout.addWidget(more_label)
            
            cell_layout.addStretch()
            cell_widget.setLayout(cell_layout)
            
            self.calendar_view.setCellWidget(0, col, cell_widget)
    
    def prev_week(self):
        self.current_week_start -= timedelta(days=7)
        self.load_calendar()
    
    def next_week(self):
        self.current_week_start += timedelta(days=7)
        self.load_calendar()
    
    def go_today(self):
        self.current_week_start = date.today() - timedelta(days=date.today().weekday())
        self.load_calendar()
    
    def generate_from_rule(self):
        current_item = self.rule_list.currentItem()
        rule = None
        if current_item:
            rule_id = current_item.data(Qt.UserRole)
            rule = cycle_rule_manager.get_rule(rule_id)
        
        dialog = CycleGenerateDialog(self, rule)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['rule_id']:
                QMessageBox.warning(self, "提示", "请选择周期规则")
                return
            
            if data['end_date'] < data['start_date']:
                QMessageBox.warning(self, "提示", "结束日期不能早于开始日期")
                return
            
            progress = QProgressDialog("正在生成排期...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(0)
            progress.show()
            
            try:
                added_count, total_count = schedule_manager.generate_cycle_schedules(
                    data['rule_id'], data['start_date'], data['end_date'],
                    data['patient_id']
                )
                
                progress.setValue(50)
                
                if data['generate_reminder'] and data['patient_id']:
                    from database import reminder_manager
                    reminder_manager.generate_batch_reminders(
                        (data['end_date'] - data['start_date']).days
                    )
                
                progress.setValue(100)
                
                self.load_calendar()
                self.load_schedule_list()
                
                skip_count = total_count - added_count
                msg_lines = [
                    "排期生成完成！",
                    "",
                    f"本次操作时段总数: {total_count} 个",
                    f"实际新增到排期表: {added_count} 个",
                    f"已存在（自动跳过，未重复插入）: {skip_count} 个",
                ]
                if data['patient_id']:
                    msg_lines.append("")
                    msg_lines.append("注意：每位患者每天只占用一个时段")
                QMessageBox.information(self, "完成", "\n".join(msg_lines))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"生成排期失败: {str(e)}")
            finally:
                progress.close()
    
    def batch_generate(self):
        dialog = BatchGenerateDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['chair_id']:
                QMessageBox.warning(self, "提示", "请选择诊疗椅")
                return
            
            if data['end_date'] < data['start_date']:
                QMessageBox.warning(self, "提示", "结束日期不能早于开始日期")
                return
            
            progress = QProgressDialog("正在生成空时段...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(0)
            progress.show()
            
            try:
                added_count, total_count = schedule_manager.generate_batch_schedules(
                    data['chair_id'], data['start_date'], data['end_date'],
                    data['day_of_week'], data['start_time'], data['end_time'],
                    data['interval_minutes']
                )
                
                progress.setValue(100)
                
                self.load_batch_results()
                self.load_calendar()
                
                skip_count = total_count - added_count
                msg_lines = [
                    "空时段生成完成！",
                    "",
                    f"本次操作时段总数: {total_count} 个",
                    f"实际新增到排期表: {added_count} 个",
                    f"已存在（自动跳过，未重复插入）: {skip_count} 个",
                ]
                QMessageBox.information(self, "完成", "\n".join(msg_lines))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"生成失败: {str(e)}")
            finally:
                progress.close()
    
    def load_batch_results(self):
        today = date.today()
        end_date = today + timedelta(days=30)
        
        schedules = []
        current = today
        while current <= end_date:
            day_schedules = schedule_manager.get_schedules_by_date(current)
            schedules.extend(day_schedules)
            current += timedelta(days=1)
        
        schedules = sorted(schedules, key=lambda x: (x['schedule_date'], x['start_time']))
        
        self.batch_result_table.setRowCount(len(schedules))
        
        status_names = {
            'available': '可用',
            'booked': '已预约',
            'completed': '已完成',
            'cancelled': '已取消',
        }
        
        for row, sched in enumerate(schedules):
            self.batch_result_table.setItem(row, 0, QTableWidgetItem(str(sched['id'])))
            self.batch_result_table.setItem(row, 1, QTableWidgetItem(sched['chair_name'] or ""))
            self.batch_result_table.setItem(row, 2, QTableWidgetItem(sched['schedule_date']))
            time_range = f"{sched['start_time']} - {sched['end_time']}"
            self.batch_result_table.setItem(row, 3, QTableWidgetItem(time_range))
            self.batch_result_table.setItem(row, 4, QTableWidgetItem(status_names.get(sched['status'], sched['status'])))
            self.batch_result_table.setItem(row, 5, QTableWidgetItem(sched['patient_name'] or ""))
    
    def patient_cycle_schedule(self):
        dialog = PatientBatchAssignDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['patient_id'] or not data['rule_id']:
                QMessageBox.warning(self, "提示", "请选择患者和周期规则")
                return
            
            if data['end_date'] < data['start_date']:
                QMessageBox.warning(self, "提示", "结束日期不能早于开始日期")
                return
            
            rule = cycle_rule_manager.get_rule(data['rule_id'])
            if not rule:
                QMessageBox.warning(self, "提示", "无效的周期规则")
                return
            
            patient = patient_manager.get_patient(data['patient_id'])
            if not patient:
                QMessageBox.warning(self, "提示", "无效的患者")
                return
            
            progress = QProgressDialog("正在为患者生成周期排期...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(0)
            progress.show()
            
            try:
                cycle_days = data['cycle_weeks'] * 7
                
                # 找到第一个匹配规则星期的日期
                current_date = data['start_date']
                days_diff = (rule['day_of_week'] - current_date.weekday() + 7) % 7
                current_date += timedelta(days=days_diff)
                
                count = 0
                skip_count = 0
                full_dates = []
                
                while current_date <= data['end_date']:
                    result = self._generate_patient_schedule(
                        rule, current_date, data['patient_id'], patient['patient_type']
                    )
                    if result == 'booked':
                        count += 1
                    elif result == 'full':
                        skip_count += 1
                        full_dates.append(current_date.strftime("%Y-%m-%d"))
                    current_date += timedelta(days=cycle_days)
                
                chair_manager.db.commit()
                
                progress.setValue(80)
                
                if data['generate_reminder']:
                    from database import reminder_manager
                    upcoming = schedule_manager.get_upcoming_schedules(
                        (data['end_date'] - date.today()).days
                    )
                    for sched in upcoming:
                        if sched['patient_id'] == data['patient_id']:
                            reminder_manager.generate_reminders_for_schedule(sched['id'])
                
                progress.setValue(100)
                
                msg = f"患者周期排期完成！\n\n成功排期: {count} 次"
                if skip_count > 0:
                    msg += f"\n时段已满跳过: {skip_count} 次"
                    if len(full_dates) <= 5:
                        msg += f"\n跳过日期: {', '.join(full_dates)}"
                    else:
                        msg += f"\n跳过日期: {', '.join(full_dates[:5])} 等"
                QMessageBox.information(self, "完成", msg)
                self.load_patient_schedules()
                self.load_calendar()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"生成失败: {str(e)}")
            finally:
                progress.close()
    
    def _generate_patient_schedule(self, rule, schedule_date, patient_id, patient_type) -> str:
        """为患者在指定日期分配一个可用时段（每周期只占一个）
        返回: 'booked'=成功占用, 'full'=目标时段已满, 'exists'=已占用
        """
        start = datetime.strptime(rule['start_time'], '%H:%M')
        end = datetime.strptime(rule['end_time'], '%H:%M')
        interval = timedelta(minutes=rule['interval_minutes'])
        
        priority = schedule_manager._get_priority(patient_type)
        current = start
        
        # 先检查该患者当天是否已安排
        existing_patient = chair_manager.db.execute('''
            SELECT id FROM schedules 
            WHERE chair_id=? AND schedule_date=? AND patient_id=? AND status='booked'
        ''', (rule['chair_id'], schedule_date.isoformat(), patient_id)).fetchone()
        if existing_patient:
            return 'exists'
        
        # 遍历所有时段，只占用第一个可用的时段
        booked_any = False
        while current < end:
            slot_end = current + interval
            start_str = current.strftime('%H:%M')
            end_str = slot_end.strftime('%H:%M')
            
            cursor = chair_manager.db.execute('''
                SELECT id, status, patient_id FROM schedules 
                WHERE chair_id=? AND schedule_date=? AND start_time=?
            ''', (rule['chair_id'], schedule_date.isoformat(), start_str))
            
            existing = cursor.fetchone()
            
            if existing:
                if existing['status'] == 'available' and not booked_any:
                    chair_manager.db.execute('''
                        UPDATE schedules 
                        SET patient_id=?, status='booked', patient_type=?, priority=?
                        WHERE id=?
                    ''', (patient_id, patient_type, priority, existing['id']))
                    booked_any = True
                    break
            else:
                if not booked_any:
                    chair_manager.db.execute('''
                        INSERT INTO schedules 
                        (chair_id, patient_id, schedule_date, start_time, end_time, 
                         status, patient_type, priority, cycle_rule_id)
                        VALUES (?, ?, ?, ?, ?, 'booked', ?, ?, ?)
                    ''', (
                        rule['chair_id'], patient_id, schedule_date.isoformat(),
                        start_str, end_str,
                        patient_type, priority, rule['id']
                    ))
                    booked_any = True
                    break
            
            current = slot_end
        
        if booked_any:
            return 'booked'
        else:
            return 'full'
    
    def load_patients_to_combo(self):
        current_data = self.patient_filter_combo.currentData()
        self.patient_filter_combo.blockSignals(True)
        self.patient_filter_combo.clear()
        self.patient_filter_combo.addItem("全部", None)
        patients = patient_manager.get_all_patients()
        for patient in patients:
            display = f"{patient['name']} ({patient['phone'] or '无电话'})"
            self.patient_filter_combo.addItem(display, patient['id'])
        
        if current_data:
            idx = self.patient_filter_combo.findData(current_data)
            if idx >= 0:
                self.patient_filter_combo.setCurrentIndex(idx)
        self.patient_filter_combo.blockSignals(False)
    
    def load_patient_schedules(self):
        patient_id = self.patient_filter_combo.currentData()
        qstart = self.patient_start_date.date()
        qend = self.patient_end_date.date()
        
        start_date = date(qstart.year(), qstart.month(), qstart.day())
        end_date = date(qend.year(), qend.month(), qend.day())
        
        schedules = []
        current = start_date
        while current <= end_date:
            day_schedules = schedule_manager.get_schedules_by_date(current)
            if patient_id:
                day_schedules = [s for s in day_schedules if s['patient_id'] == patient_id]
            else:
                day_schedules = [s for s in day_schedules if s['patient_id'] is not None]
            schedules.extend(day_schedules)
            current += timedelta(days=1)
        
        schedules = sorted(schedules, key=lambda x: (x['schedule_date'], x['start_time']))
        
        self.patient_schedule_table.setRowCount(len(schedules))
        
        status_names = {
            'available': '可用',
            'booked': '已预约',
            'completed': '已完成',
            'cancelled': '已取消',
        }
        
        for row, sched in enumerate(schedules):
            self.patient_schedule_table.setItem(row, 0, QTableWidgetItem(str(sched['id'])))
            self.patient_schedule_table.setItem(row, 1, QTableWidgetItem(sched['patient_name'] or ""))
            self.patient_schedule_table.setItem(row, 2, QTableWidgetItem(sched['chair_name'] or ""))
            self.patient_schedule_table.setItem(row, 3, QTableWidgetItem(sched['schedule_date']))
            time_range = f"{sched['start_time']} - {sched['end_time']}"
            self.patient_schedule_table.setItem(row, 4, QTableWidgetItem(time_range))
            type_name = self._get_type_name(sched['patient_type'])
            self.patient_schedule_table.setItem(row, 5, QTableWidgetItem(type_name))
            self.patient_schedule_table.setItem(row, 6, QTableWidgetItem(status_names.get(sched['status'], sched['status'])))
            
            action_widget = QWidget()
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("调整")
            edit_btn.setFixedWidth(50)
            edit_btn.clicked.connect(lambda _, sid=sched['id']: self.adjust_schedule(sid))
            action_layout.addWidget(edit_btn)
            
            cancel_btn = QPushButton("取消")
            cancel_btn.setFixedWidth(50)
            cancel_btn.clicked.connect(lambda _, sid=sched['id']: self.cancel_single_schedule(sid))
            action_layout.addWidget(cancel_btn)
            
            action_layout.addStretch()
            action_widget.setLayout(action_layout)
            self.patient_schedule_table.setCellWidget(row, 7, action_widget)
    
    def adjust_schedule(self, schedule_id):
        from schedule_module import ScheduleDialog
        schedule = schedule_manager.get_schedule(schedule_id)
        if not schedule:
            return
        
        dialog = ScheduleDialog(self, schedule)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            schedule_manager.update_schedule(schedule_id, **data)
            QMessageBox.information(self, "成功", "排期已调整")
            self.load_patient_schedules()
            self.load_calendar()
    
    def cancel_single_schedule(self, schedule_id):
        reply = QMessageBox.question(self, "确认", "确定要取消该排期吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            schedule_manager.cancel_schedule(schedule_id)
            self.load_patient_schedules()
            self.load_calendar()
    
    def load_schedules(self):
        self.load_calendar()
    
    def load_schedule_list(self):
        qdate = self.list_date.date()
        schedule_date = date(qdate.year(), qdate.month(), qdate.day())
        chair_id = self.list_chair.currentData()
        status = self.list_status.currentData()
        
        schedules = schedule_manager.get_schedules_by_date(schedule_date, chair_id)
        
        if status:
            schedules = [s for s in schedules if s['status'] == status]
        
        self.schedule_list_table.setRowCount(len(schedules))
        
        status_colors = {
            'available': QColor(255, 255, 255),
            'booked': QColor(173, 216, 230),
            'completed': QColor(144, 238, 144),
            'cancelled': QColor(255, 182, 193),
        }
        
        status_names = {
            'available': '可用',
            'booked': '已预约',
            'completed': '已完成',
            'cancelled': '已取消',
        }
        
        for row, sched in enumerate(schedules):
            self.schedule_list_table.setItem(row, 0, QTableWidgetItem(str(sched['id'])))
            self.schedule_list_table.setItem(row, 1, QTableWidgetItem(sched['chair_name'] or ""))
            self.schedule_list_table.setItem(row, 2, QTableWidgetItem(sched['schedule_date']))
            time_range = f"{sched['start_time']} - {sched['end_time']}"
            self.schedule_list_table.setItem(row, 3, QTableWidgetItem(time_range))
            self.schedule_list_table.setItem(row, 4, QTableWidgetItem(sched['patient_name'] or ""))
            type_name = self._get_type_name(sched['patient_type'])
            self.schedule_list_table.setItem(row, 5, QTableWidgetItem(type_name))
            
            status_item = QTableWidgetItem(status_names.get(sched['status'], sched['status']))
            color = status_colors.get(sched['status'], QColor(255, 255, 255))
            for col in range(8):
                item = self.schedule_list_table.item(row, col)
                if item:
                    item.setBackground(QBrush(color))
            
            self.schedule_list_table.setItem(row, 6, status_item)
            self.schedule_list_table.setItem(row, 7, QTableWidgetItem(sched['notes'] or ""))
    
    def edit_schedule_from_list(self):
        current_row = self.schedule_list_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要编辑的排期")
            return
        
        schedule_id = int(self.schedule_list_table.item(current_row, 0).text())
        self.adjust_schedule(schedule_id)
    
    def delete_schedule_from_list(self):
        current_row = self.schedule_list_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要删除的排期")
            return
        
        schedule_id = int(self.schedule_list_table.item(current_row, 0).text())
        reply = QMessageBox.question(self, "确认", "确定要删除该排期吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            schedule_manager.delete_schedule(schedule_id)
            self.load_schedule_list()
            self.load_calendar()
