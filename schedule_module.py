from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QTimeEdit, QDateEdit, QMessageBox, QLabel, QHeaderView,
    QTabWidget, QGroupBox, QTextEdit, QCheckBox, QListWidget, QListWidgetItem,
    QSplitter, QFrame
)
from PySide6.QtCore import Qt, QDate, QTime
from PySide6.QtGui import QColor, QBrush
from datetime import date, timedelta
from database import (
    chair_manager, patient_manager, cycle_rule_manager, 
    schedule_manager, priority_rule_manager
)


class ChairDialog(QDialog):
    def __init__(self, parent=None, chair=None):
        super().__init__(parent)
        self.chair = chair
        self.setWindowTitle("诊疗椅信息")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.active_check = QCheckBox("启用")
        self.active_check.setChecked(True)
        
        layout.addRow("诊疗椅名称:", self.name_edit)
        layout.addRow("描述:", self.desc_edit)
        layout.addRow("", self.active_check)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        if chair:
            self.name_edit.setText(chair['name'])
            self.desc_edit.setText(chair['description'] or "")
            self.active_check.setChecked(chair['is_active'] == 1)
    
    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'description': self.desc_edit.toPlainText().strip(),
            'is_active': self.active_check.isChecked()
        }


class CycleRuleDialog(QDialog):
    def __init__(self, parent=None, rule=None):
        super().__init__(parent)
        self.rule = rule
        self.setWindowTitle("周期规则")
        self.setModal(True)
        self.resize(450, 400)
        
        layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        
        self.chair_combo = QComboBox()
        self.load_chairs()
        
        self.day_combo = QComboBox()
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, day in enumerate(days):
            self.day_combo.addItem(day, i)
        
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
        
        self.type_combo = QComboBox()
        self.load_patient_types()
        
        self.active_check = QCheckBox("启用")
        self.active_check.setChecked(True)
        
        layout.addRow("规则名称:", self.name_edit)
        layout.addRow("诊疗椅:", self.chair_combo)
        layout.addRow("每周:", self.day_combo)
        layout.addRow("开始时间:", self.start_time)
        layout.addRow("结束时间:", self.end_time)
        layout.addRow("间隔:", self.interval_spin)
        layout.addRow("患者类型:", self.type_combo)
        layout.addRow("", self.active_check)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        if rule:
            self.name_edit.setText(rule['name'])
            self.day_combo.setCurrentIndex(rule['day_of_week'])
            self.start_time.setTime(QTime.fromString(rule['start_time'], "HH:mm"))
            self.end_time.setTime(QTime.fromString(rule['end_time'], "HH:mm"))
            self.interval_spin.setValue(rule['interval_minutes'])
            self.type_combo.setCurrentText(self._get_type_name(rule['patient_type']))
            self.active_check.setChecked(rule['is_active'] == 1)
            
            if rule['chair_id']:
                idx = self.chair_combo.findData(rule['chair_id'])
                if idx >= 0:
                    self.chair_combo.setCurrentIndex(idx)
    
    def _get_type_name(self, type_key):
        rules = priority_rule_manager.get_all_rules()
        for r in rules:
            if r['patient_type'] == type_key:
                return r['name']
        return "普通患者"
    
    def load_chairs(self):
        self.chair_combo.clear()
        self.chair_combo.addItem("不限", None)
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.chair_combo.addItem(chair['name'], chair['id'])
    
    def load_patient_types(self):
        self.type_combo.clear()
        rules = priority_rule_manager.get_all_rules()
        for rule in rules:
            self.type_combo.addItem(rule['name'], rule['patient_type'])
    
    def get_data(self):
        return {
            'name': self.name_edit.text().strip(),
            'chair_id': self.chair_combo.currentData(),
            'day_of_week': self.day_combo.currentData(),
            'start_time': self.start_time.time().toString("HH:mm"),
            'end_time': self.end_time.time().toString("HH:mm"),
            'interval_minutes': self.interval_spin.value(),
            'patient_type': self.type_combo.currentData(),
            'is_active': self.active_check.isChecked()
        }


class ScheduleDialog(QDialog):
    def __init__(self, parent=None, schedule=None):
        super().__init__(parent)
        self.schedule = schedule
        self.setWindowTitle("排期详情")
        self.setModal(True)
        self.resize(450, 400)
        
        layout = QFormLayout()
        
        self.chair_combo = QComboBox()
        self.load_chairs()
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        
        self.patient_combo = QComboBox()
        self.patient_combo.setEditable(True)
        self.load_patients()
        
        self.type_combo = QComboBox()
        self.load_patient_types()
        
        self.status_combo = QComboBox()
        self.status_combo.addItem("可用", "available")
        self.status_combo.addItem("已预约", "booked")
        self.status_combo.addItem("已完成", "completed")
        self.status_combo.addItem("已取消", "cancelled")
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        
        layout.addRow("诊疗椅:", self.chair_combo)
        layout.addRow("日期:", self.date_edit)
        layout.addRow("开始时间:", self.start_time)
        layout.addRow("结束时间:", self.end_time)
        layout.addRow("患者:", self.patient_combo)
        layout.addRow("患者类型:", self.type_combo)
        layout.addRow("状态:", self.status_combo)
        layout.addRow("备注:", self.notes_edit)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        if schedule:
            idx = self.chair_combo.findData(schedule['chair_id'])
            if idx >= 0:
                self.chair_combo.setCurrentIndex(idx)
            
            self.date_edit.setDate(QDate.fromString(schedule['schedule_date'], "yyyy-MM-dd"))
            self.start_time.setTime(QTime.fromString(schedule['start_time'], "HH:mm"))
            self.end_time.setTime(QTime.fromString(schedule['end_time'], "HH:mm"))
            
            if schedule['patient_id']:
                idx = self.patient_combo.findData(schedule['patient_id'])
                if idx >= 0:
                    self.patient_combo.setCurrentIndex(idx)
            
            idx = self.type_combo.findData(schedule['patient_type'])
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            
            idx = self.status_combo.findData(schedule['status'])
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
            
            self.notes_edit.setText(schedule['notes'] or "")
    
    def load_chairs(self):
        self.chair_combo.clear()
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.chair_combo.addItem(chair['name'], chair['id'])
    
    def load_patients(self):
        self.patient_combo.clear()
        self.patient_combo.addItem("", None)
        patients = patient_manager.get_all_patients()
        for patient in patients:
            display = f"{patient['name']} ({patient['phone'] or '无电话'})"
            self.patient_combo.addItem(display, patient['id'])
    
    def load_patient_types(self):
        self.type_combo.clear()
        rules = priority_rule_manager.get_all_rules()
        for rule in rules:
            self.type_combo.addItem(rule['name'], rule['patient_type'])
    
    def get_data(self):
        return {
            'chair_id': self.chair_combo.currentData(),
            'schedule_date': self.date_edit.date().toString("yyyy-MM-dd"),
            'start_time': self.start_time.time().toString("HH:mm"),
            'end_time': self.end_time.time().toString("HH:mm"),
            'patient_id': self.patient_combo.currentData(),
            'patient_type': self.type_combo.currentData(),
            'status': self.status_combo.currentData(),
            'notes': self.notes_edit.toPlainText().strip()
        }


class ScheduleModule(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_chair_tab(), "诊疗椅管理")
        self.tabs.addTab(self.create_cycle_tab(), "周期规则")
        self.tabs.addTab(self.create_schedule_tab(), "排期管理")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def create_chair_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.add_chair_btn = QPushButton("新增诊疗椅")
        self.edit_chair_btn = QPushButton("编辑")
        self.delete_chair_btn = QPushButton("删除")
        self.refresh_chair_btn = QPushButton("刷新")
        
        btn_layout.addWidget(self.add_chair_btn)
        btn_layout.addWidget(self.edit_chair_btn)
        btn_layout.addWidget(self.delete_chair_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_chair_btn)
        
        self.chair_table = QTableWidget()
        self.chair_table.setColumnCount(4)
        self.chair_table.setHorizontalHeaderLabels(["ID", "名称", "描述", "状态"])
        self.chair_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.chair_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.chair_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.chair_table)
        widget.setLayout(layout)
        
        self.add_chair_btn.clicked.connect(self.add_chair)
        self.edit_chair_btn.clicked.connect(self.edit_chair)
        self.delete_chair_btn.clicked.connect(self.delete_chair)
        self.refresh_chair_btn.clicked.connect(self.load_chairs)
        
        return widget
    
    def create_cycle_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.add_rule_btn = QPushButton("新增规则")
        self.edit_rule_btn = QPushButton("编辑")
        self.delete_rule_btn = QPushButton("删除")
        self.refresh_rule_btn = QPushButton("刷新")
        
        btn_layout.addWidget(self.add_rule_btn)
        btn_layout.addWidget(self.edit_rule_btn)
        btn_layout.addWidget(self.delete_rule_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_rule_btn)
        
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(8)
        self.rule_table.setHorizontalHeaderLabels([
            "ID", "规则名称", "诊疗椅", "每周", "时段", "间隔", "患者类型", "状态"
        ])
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rule_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.rule_table)
        widget.setLayout(layout)
        
        self.add_rule_btn.clicked.connect(self.add_rule)
        self.edit_rule_btn.clicked.connect(self.edit_rule)
        self.delete_rule_btn.clicked.connect(self.delete_rule)
        self.refresh_rule_btn.clicked.connect(self.load_rules)
        
        return widget
    
    def create_schedule_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        filter_group = QGroupBox("筛选")
        filter_layout = QVBoxLayout()
        
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("日期:"))
        self.schedule_date = QDateEdit()
        self.schedule_date.setCalendarPopup(True)
        self.schedule_date.setDate(QDate.currentDate())
        self.schedule_date.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.schedule_date)
        filter_layout.addLayout(date_layout)
        
        chair_layout = QHBoxLayout()
        chair_layout.addWidget(QLabel("诊疗椅:"))
        self.schedule_chair = QComboBox()
        self.schedule_chair.addItem("全部", None)
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.schedule_chair.addItem(chair['name'], chair['id'])
        chair_layout.addWidget(self.schedule_chair)
        filter_layout.addLayout(chair_layout)
        
        self.apply_filter_btn = QPushButton("查询")
        filter_layout.addWidget(self.apply_filter_btn)
        
        status_group = QGroupBox("状态说明")
        status_layout = QVBoxLayout()
        
        status_info = [
            ("可用", QColor(255, 255, 255)),
            ("已预约", QColor(173, 216, 230)),
            ("已完成", QColor(144, 238, 144)),
            ("已取消", QColor(255, 182, 193)),
        ]
        
        for name, color in status_info:
            item_layout = QHBoxLayout()
            color_label = QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #999;")
            item_layout.addWidget(color_label)
            item_layout.addWidget(QLabel(name))
            item_layout.addStretch()
            status_layout.addLayout(item_layout)
        
        status_group.setLayout(status_layout)
        filter_layout.addWidget(status_group)
        filter_layout.addStretch()
        
        filter_group.setLayout(filter_layout)
        filter_group.setFixedWidth(220)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.add_schedule_btn = QPushButton("新增排期")
        self.edit_schedule_btn = QPushButton("编辑")
        self.delete_schedule_btn = QPushButton("删除")
        self.booking_btn = QPushButton("预约")
        self.cancel_booking_btn = QPushButton("取消预约")
        self.refresh_schedule_btn = QPushButton("刷新")
        
        btn_layout.addWidget(self.add_schedule_btn)
        btn_layout.addWidget(self.edit_schedule_btn)
        btn_layout.addWidget(self.delete_schedule_btn)
        btn_layout.addWidget(self.booking_btn)
        btn_layout.addWidget(self.cancel_booking_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.refresh_schedule_btn)
        
        self.schedule_table = QTableWidget()
        self.schedule_table.setColumnCount(7)
        self.schedule_table.setHorizontalHeaderLabels([
            "ID", "诊疗椅", "时段", "患者", "患者类型", "状态", "备注"
        ])
        self.schedule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.schedule_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.schedule_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        right_layout.addLayout(btn_layout)
        right_layout.addWidget(self.schedule_table)
        right_panel.setLayout(right_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(filter_group)
        splitter.addWidget(right_panel)
        splitter.setSizes([220, 800])
        
        main_layout.addWidget(splitter)
        widget.setLayout(main_layout)
        
        self.apply_filter_btn.clicked.connect(self.load_schedules)
        self.schedule_date.dateChanged.connect(self.load_schedules)
        self.schedule_chair.currentIndexChanged.connect(self.load_schedules)
        self.add_schedule_btn.clicked.connect(self.add_schedule)
        self.edit_schedule_btn.clicked.connect(self.edit_schedule)
        self.delete_schedule_btn.clicked.connect(self.delete_schedule)
        self.booking_btn.clicked.connect(self.booking_schedule)
        self.cancel_booking_btn.clicked.connect(self.cancel_booking)
        self.refresh_schedule_btn.clicked.connect(self.load_schedules)
        
        return widget
    
    def load_data(self):
        self.load_chairs()
        self.load_rules()
        self.load_schedules()
    
    def load_chairs(self):
        chairs = chair_manager.get_all_chairs(active_only=False)
        self.chair_table.setRowCount(len(chairs))
        
        for row, chair in enumerate(chairs):
            self.chair_table.setItem(row, 0, QTableWidgetItem(str(chair['id'])))
            self.chair_table.setItem(row, 1, QTableWidgetItem(chair['name']))
            self.chair_table.setItem(row, 2, QTableWidgetItem(chair['description'] or ""))
            
            status = "启用" if chair['is_active'] == 1 else "停用"
            status_item = QTableWidgetItem(status)
            if chair['is_active'] == 1:
                status_item.setForeground(QBrush(QColor(0, 128, 0)))
            else:
                status_item.setForeground(QBrush(QColor(255, 0, 0)))
            self.chair_table.setItem(row, 3, status_item)
    
    def load_rules(self):
        rules = cycle_rule_manager.get_all_rules(active_only=False)
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        
        self.rule_table.setRowCount(len(rules))
        
        for row, rule in enumerate(rules):
            self.rule_table.setItem(row, 0, QTableWidgetItem(str(rule['id'])))
            self.rule_table.setItem(row, 1, QTableWidgetItem(rule['name']))
            self.rule_table.setItem(row, 2, QTableWidgetItem(rule['chair_name'] or "不限"))
            self.rule_table.setItem(row, 3, QTableWidgetItem(days[rule['day_of_week']]))
            time_range = f"{rule['start_time']} - {rule['end_time']}"
            self.rule_table.setItem(row, 4, QTableWidgetItem(time_range))
            self.rule_table.setItem(row, 5, QTableWidgetItem(f"{rule['interval_minutes']}分钟"))
            
            type_name = self._get_type_name(rule['patient_type'])
            self.rule_table.setItem(row, 6, QTableWidgetItem(type_name))
            
            status = "启用" if rule['is_active'] == 1 else "停用"
            status_item = QTableWidgetItem(status)
            if rule['is_active'] == 1:
                status_item.setForeground(QBrush(QColor(0, 128, 0)))
            else:
                status_item.setForeground(QBrush(QColor(255, 0, 0)))
            self.rule_table.setItem(row, 7, status_item)
    
    def _get_type_name(self, type_key):
        rules = priority_rule_manager.get_all_rules()
        for r in rules:
            if r['patient_type'] == type_key:
                return r['name']
        return "普通患者"
    
    def load_schedules(self):
        qdate = self.schedule_date.date()
        schedule_date = date(qdate.year(), qdate.month(), qdate.day())
        chair_id = self.schedule_chair.currentData()
        
        schedules = schedule_manager.get_schedules_by_date(schedule_date, chair_id)
        self.schedule_table.setRowCount(len(schedules))
        
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
            self.schedule_table.setItem(row, 0, QTableWidgetItem(str(sched['id'])))
            self.schedule_table.setItem(row, 1, QTableWidgetItem(sched['chair_name'] or ""))
            
            time_range = f"{sched['start_time']} - {sched['end_time']}"
            self.schedule_table.setItem(row, 2, QTableWidgetItem(time_range))
            self.schedule_table.setItem(row, 3, QTableWidgetItem(sched['patient_name'] or ""))
            
            type_name = self._get_type_name(sched['patient_type'])
            self.schedule_table.setItem(row, 4, QTableWidgetItem(type_name))
            
            status_item = QTableWidgetItem(status_names.get(sched['status'], sched['status']))
            color = status_colors.get(sched['status'], QColor(255, 255, 255))
            for col in range(7):
                item = self.schedule_table.item(row, col)
                if item:
                    item.setBackground(QBrush(color))
            
            self.schedule_table.setItem(row, 5, status_item)
            self.schedule_table.setItem(row, 6, QTableWidgetItem(sched['notes'] or ""))
    
    def add_chair(self):
        dialog = ChairDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "提示", "请输入诊疗椅名称")
                return
            chair_manager.add_chair(data['name'], data['description'])
            self.load_chairs()
            self.refresh_schedule_chair_combo()
    
    def edit_chair(self):
        current_row = self.chair_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要编辑的诊疗椅")
            return
        
        chair_id = int(self.chair_table.item(current_row, 0).text())
        chair = chair_manager.get_chair(chair_id)
        
        dialog = ChairDialog(self, chair)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "提示", "请输入诊疗椅名称")
                return
            chair_manager.update_chair(chair_id, data['name'], data['description'], data['is_active'])
            self.load_chairs()
            self.refresh_schedule_chair_combo()
    
    def delete_chair(self):
        current_row = self.chair_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要删除的诊疗椅")
            return
        
        chair_id = int(self.chair_table.item(current_row, 0).text())
        reply = QMessageBox.question(self, "确认", "确定要删除该诊疗椅吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            chair_manager.delete_chair(chair_id)
            self.load_chairs()
            self.refresh_schedule_chair_combo()
    
    def refresh_schedule_chair_combo(self):
        current_data = self.schedule_chair.currentData()
        self.schedule_chair.blockSignals(True)
        self.schedule_chair.clear()
        self.schedule_chair.addItem("全部", None)
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.schedule_chair.addItem(chair['name'], chair['id'])
        
        if current_data:
            idx = self.schedule_chair.findData(current_data)
            if idx >= 0:
                self.schedule_chair.setCurrentIndex(idx)
        self.schedule_chair.blockSignals(False)
    
    def add_rule(self):
        dialog = CycleRuleDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "提示", "请输入规则名称")
                return
            cycle_rule_manager.add_rule(
                data['name'], data['chair_id'], data['day_of_week'],
                data['start_time'], data['end_time'], data['interval_minutes'],
                data['patient_type']
            )
            self.load_rules()
    
    def edit_rule(self):
        current_row = self.rule_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要编辑的规则")
            return
        
        rule_id = int(self.rule_table.item(current_row, 0).text())
        rule = cycle_rule_manager.get_rule(rule_id)
        
        dialog = CycleRuleDialog(self, rule)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "提示", "请输入规则名称")
                return
            cycle_rule_manager.update_rule(rule_id, **data)
            self.load_rules()
    
    def delete_rule(self):
        current_row = self.rule_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要删除的规则")
            return
        
        rule_id = int(self.rule_table.item(current_row, 0).text())
        reply = QMessageBox.question(self, "确认", "确定要删除该规则吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            cycle_rule_manager.delete_rule(rule_id)
            self.load_rules()
    
    def add_schedule(self):
        dialog = ScheduleDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            data['status'] = 'available'
            data['priority'] = 0
            
            cursor = chair_manager.db.execute('''
                INSERT INTO schedules 
                (chair_id, schedule_date, start_time, end_time, status, 
                 patient_id, patient_type, priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['chair_id'], data['schedule_date'],
                data['start_time'], data['end_time'], data['status'],
                data['patient_id'], data['patient_type'],
                self._get_priority(data['patient_type']), data['notes']
            ))
            chair_manager.db.commit()
            self.load_schedules()
    
    def _get_priority(self, patient_type):
        return schedule_manager._get_priority(patient_type)
    
    def edit_schedule(self):
        current_row = self.schedule_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要编辑的排期")
            return
        
        schedule_id = int(self.schedule_table.item(current_row, 0).text())
        schedule = schedule_manager.get_schedule(schedule_id)
        
        dialog = ScheduleDialog(self, schedule)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            schedule_manager.update_schedule(schedule_id, **data)
            self.load_schedules()
    
    def delete_schedule(self):
        current_row = self.schedule_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要删除的排期")
            return
        
        schedule_id = int(self.schedule_table.item(current_row, 0).text())
        reply = QMessageBox.question(self, "确认", "确定要删除该排期吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            schedule_manager.delete_schedule(schedule_id)
            self.load_schedules()
    
    def booking_schedule(self):
        current_row = self.schedule_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要预约的排期")
            return
        
        schedule_id = int(self.schedule_table.item(current_row, 0).text())
        schedule = schedule_manager.get_schedule(schedule_id)
        
        if schedule['status'] != 'available':
            QMessageBox.warning(self, "提示", "该排期已被预约")
            return
        
        dialog = PatientSelectDialog(self)
        if dialog.exec() == QDialog.Accepted:
            patient_id, patient_type = dialog.get_selected()
            if schedule_manager.book_schedule(schedule_id, patient_id, patient_type):
                QMessageBox.information(self, "成功", "预约成功")
                self.load_schedules()
            else:
                QMessageBox.warning(self, "失败", "预约失败，请重试")
    
    def cancel_booking(self):
        current_row = self.schedule_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要取消预约的排期")
            return
        
        schedule_id = int(self.schedule_table.item(current_row, 0).text())
        schedule = schedule_manager.get_schedule(schedule_id)
        
        if schedule['status'] != 'booked':
            QMessageBox.warning(self, "提示", "该排期未被预约")
            return
        
        reply = QMessageBox.question(self, "确认", "确定要取消该预约吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            schedule_manager.cancel_schedule(schedule_id)
            self.load_schedules()


class PatientSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择患者")
        self.setModal(True)
        self.resize(500, 450)
        
        layout = QVBoxLayout()
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入患者姓名或电话")
        search_layout.addWidget(self.search_edit)
        self.search_btn = QPushButton("搜索")
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)
        
        self.patient_list = QListWidget()
        self.patient_list.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.patient_list)
        
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("患者类型:"))
        self.type_combo = QComboBox()
        rules = priority_rule_manager.get_all_rules()
        for rule in rules:
            self.type_combo.addItem(rule['name'], rule['patient_type'])
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确定")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.search_btn.clicked.connect(self.load_patients)
        self.search_edit.returnPressed.connect(self.load_patients)
        
        self.load_patients()
    
    def load_patients(self):
        keyword = self.search_edit.text().strip()
        if keyword:
            patients = patient_manager.search_patients(keyword)
        else:
            patients = patient_manager.get_all_patients()
        
        self.patient_list.clear()
        type_names = {r['patient_type']: r['name'] for r in priority_rule_manager.get_all_rules()}
        
        for patient in patients:
            type_name = type_names.get(patient['patient_type'], '普通患者')
            display = f"{patient['name']} - {patient['phone'] or '无电话'} - {type_name}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, patient['id'])
            item.setData(Qt.UserRole + 1, patient['patient_type'])
            self.patient_list.addItem(item)
    
    def get_selected(self):
        current_item = self.patient_list.currentItem()
        if current_item:
            patient_id = current_item.data(Qt.UserRole)
            patient_type = self.type_combo.currentData()
            return patient_id, patient_type
        return None, None
    
    def accept(self):
        if not self.patient_list.currentItem():
            QMessageBox.warning(self, "提示", "请选择患者")
            return
        super().accept()
