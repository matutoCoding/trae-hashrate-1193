from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QMessageBox, QLabel, QHeaderView, QCheckBox,
    QTabWidget, QGroupBox, QListWidget, QListWidgetItem,
    QSplitter, QFrame, QGridLayout, QLCDNumber, QProgressBar
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QBrush, QFont, QPalette
from datetime import date, datetime, timedelta
from database import (
    chair_manager, patient_manager, queue_manager, 
    schedule_manager, priority_rule_manager
)


class CheckinDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("患者取号")
        self.setModal(True)
        self.resize(450, 450)
        
        layout = QFormLayout()
        
        self.patient_combo = QComboBox()
        self.patient_combo.setEditable(True)
        self.load_patients()
        
        self.type_combo = QComboBox()
        self.load_patient_types()
        
        self.chair_combo = QComboBox()
        self.chair_combo.addItem("不限", None)
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.chair_combo.addItem(chair['name'], chair['id'])
        
        self.schedule_combo = QComboBox()
        self.schedule_combo.addItem("无预约", None)
        
        self.is_jump_check = QCheckBox("优先插队（急诊/VIP）")
        self.is_jump_check.setChecked(False)
        
        layout.addRow("患者:", self.patient_combo)
        layout.addRow("患者类型:", self.type_combo)
        layout.addRow("指定诊疗椅:", self.chair_combo)
        layout.addRow("关联预约:", self.schedule_combo)
        layout.addRow("", self.is_jump_check)
        
        self.priority_info = QLabel()
        self.priority_info.setWordWrap(True)
        self.priority_info.setStyleSheet("color: #666; padding: 8px; background-color: #f5f5f5; border-radius: 4px;")
        layout.addRow("", self.priority_info)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("取号")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.type_combo.currentIndexChanged.connect(self.update_priority_info)
        self.patient_combo.currentIndexChanged.connect(self.on_patient_changed)
        
        self.update_priority_info()
    
    def load_patients(self):
        self.patient_combo.clear()
        patients = patient_manager.get_all_patients()
        for patient in patients:
            display = f"{patient['name']} ({patient['phone'] or '无电话'})"
            self.patient_combo.addItem(display, patient['id'])
    
    def load_patient_types(self):
        self.type_combo.clear()
        rules = priority_rule_manager.get_all_rules()
        for rule in rules:
            display = f"{rule['name']} (优先级: {rule['priority_level']})"
            self.type_combo.addItem(display, rule['patient_type'])
    
    def on_patient_changed(self):
        patient_id = self.patient_combo.currentData()
        if patient_id:
            patient = patient_manager.get_patient(patient_id)
            if patient:
                idx = self.type_combo.findData(patient['patient_type'])
                if idx >= 0:
                    self.type_combo.setCurrentIndex(idx)
            self.load_patient_schedules(patient_id)
    
    def load_patient_schedules(self, patient_id):
        self.schedule_combo.clear()
        self.schedule_combo.addItem("无预约", None)
        
        today = date.today()
        schedules = schedule_manager.get_schedules_by_date(today)
        patient_schedules = [s for s in schedules if s['patient_id'] == patient_id and s['status'] == 'booked']
        
        for sched in patient_schedules:
            display = f"{sched['start_time']} - {sched['chair_name']}"
            self.schedule_combo.addItem(display, sched['id'])
    
    def update_priority_info(self):
        patient_type = self.type_combo.currentData()
        rule = priority_rule_manager.get_rule_by_type(patient_type)
        if rule:
            jump_text = "允许插队" if rule['can_jump'] else "不允许插队"
            info = f"<b>{rule['name']}</b><br>优先级: {rule['priority_level']}<br>{jump_text}<br><i>{rule['description']}</i>"
            self.priority_info.setText(info)
            
            if rule['can_jump']:
                self.is_jump_check.setEnabled(True)
            else:
                self.is_jump_check.setChecked(False)
                self.is_jump_check.setEnabled(False)
    
    def get_data(self):
        return {
            'patient_id': self.patient_combo.currentData(),
            'patient_type': self.type_combo.currentData(),
            'chair_id': self.chair_combo.currentData(),
            'schedule_id': self.schedule_combo.currentData(),
            'is_jump': self.is_jump_check.isChecked()
        }
    
    def accept(self):
        data = self.get_data()
        if not data['patient_id']:
            QMessageBox.warning(self, "提示", "请选择患者")
            return
        
        if data['is_jump']:
            rule = priority_rule_manager.get_rule_by_type(data['patient_type'])
            if not rule or not rule['can_jump']:
                QMessageBox.warning(self, "提示", "该患者类型不允许插队")
                return
        
        super().accept()


class JumpQueueDialog(QDialog):
    def __init__(self, parent=None, queue_item=None):
        super().__init__(parent)
        self.queue_item = queue_item
        self.setWindowTitle("优先插队")
        self.setModal(True)
        self.resize(400, 350)
        
        layout = QFormLayout()
        
        self.patient_label = QLabel()
        layout.addRow("当前患者:", self.patient_label)
        
        self.current_position_label = QLabel()
        layout.addRow("当前位置:", self.current_position_label)
        
        self.target_position_spin = QSpinBox()
        self.target_position_spin.setRange(1, 999)
        layout.addRow("插队到位置:", self.target_position_spin)
        
        self.jump_reason_edit = QLineEdit()
        self.jump_reason_edit.setPlaceholderText("请输入插队原因（如：急诊、VIP等）")
        layout.addRow("插队原因:", self.jump_reason_edit)
        
        self.priority_info = QLabel()
        self.priority_info.setWordWrap(True)
        self.priority_info.setStyleSheet("color: #666; padding: 8px; background-color: #f5f5f5; border-radius: 4px;")
        layout.addRow("", self.priority_info)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("确认插队")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        if queue_item:
            self.patient_label.setText(queue_item.get('patient_name', ''))
            self.current_position_label.setText(str(queue_item.get('queue_number', 0)))
            self.target_position_spin.setValue(max(1, queue_item.get('queue_number', 1) - 1))
            
            rule = priority_rule_manager.get_rule_by_type(queue_item.get('patient_type', 'normal'))
            if rule:
                jump_text = "允许插队" if rule['can_jump'] else "不允许插队"
                info = f"<b>{rule['name']}</b><br>优先级: {rule['priority_level']}<br>{jump_text}<br><i>{rule['description']}</i>"
                self.priority_info.setText(info)
    
    def get_data(self):
        return {
            'target_position': self.target_position_spin.value(),
            'reason': self.jump_reason_edit.text().strip()
        }


class CallingDisplayDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("叫号显示屏")
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout()
        
        title_label = QLabel("口腔正畸科 - 叫号系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1976D2; padding: 10px;")
        layout.addWidget(title_label)
        
        time_label = QLabel()
        time_label.setAlignment(Qt.AlignCenter)
        time_font = QFont()
        time_font.setPointSize(14)
        time_label.setFont(time_font)
        time_label.setStyleSheet("color: #666;")
        layout.addWidget(time_label)
        self.time_label = time_label
        
        current_group = QGroupBox("当前叫号")
        current_layout = QVBoxLayout()
        
        self.current_number = QLCDNumber()
        self.current_number.setDigitCount(4)
        self.current_number.setMinimumHeight(120)
        self.current_number.setStyleSheet("background-color: #1976D2; color: white;")
        current_layout.addWidget(self.current_number)
        
        self.current_patient_label = QLabel()
        self.current_patient_label.setAlignment(Qt.AlignCenter)
        patient_font = QFont()
        patient_font.setPointSize(20)
        patient_font.setBold(True)
        self.current_patient_label.setFont(patient_font)
        self.current_patient_label.setStyleSheet("color: #1976D2; padding: 10px;")
        current_layout.addWidget(self.current_patient_label)
        
        self.current_chair_label = QLabel()
        self.current_chair_label.setAlignment(Qt.AlignCenter)
        self.current_chair_label.setStyleSheet("color: #666; font-size: 14px;")
        current_layout.addWidget(self.current_chair_label)
        
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)
        
        waiting_group = QGroupBox("等待队列")
        waiting_layout = QVBoxLayout()
        
        self.waiting_table = QTableWidget()
        self.waiting_table.setColumnCount(3)
        self.waiting_table.setHorizontalHeaderLabels(["序号", "患者", "类型"])
        self.waiting_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.waiting_table.verticalHeader().setVisible(False)
        self.waiting_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.waiting_table.setSelectionMode(QTableWidget.NoSelection)
        waiting_layout.addWidget(self.waiting_table)
        
        waiting_group.setLayout(waiting_layout)
        layout.addWidget(waiting_group)
        
        stats_layout = QHBoxLayout()
        self.waiting_count_label = QLabel()
        self.waiting_count_label.setStyleSheet("font-size: 14px; color: #f44336; font-weight: bold;")
        stats_layout.addWidget(self.waiting_count_label)
        
        self.completed_count_label = QLabel()
        self.completed_count_label.setStyleSheet("font-size: 14px; color: #4CAF50; font-weight: bold;")
        stats_layout.addStretch()
        stats_layout.addWidget(self.completed_count_label)
        
        layout.addLayout(stats_layout)
        
        btn_layout = QHBoxLayout()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_display)
        self.refresh_timer.start(1000)
        
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        
        self.refresh_display()
        self.update_time()
    
    def update_time(self):
        self.time_label.setText(datetime.now().strftime("%Y年%m月%d日 %H:%M:%S"))
    
    def refresh_display(self):
        waiting_queue = queue_manager.get_waiting_queue()
        today_queue = queue_manager.get_today_queue()
        
        if waiting_queue:
            first = waiting_queue[0]
            self.current_number.display(first['queue_number'])
            self.current_patient_label.setText(first['patient_name'] or "")
            chair_text = f"请前往 {first['chair_name']}" if first['chair_name'] else "请稍候"
            self.current_chair_label.setText(chair_text)
        else:
            self.current_number.display(0)
            self.current_patient_label.setText("暂无等待患者")
            self.current_chair_label.setText("")
        
        display_queue = waiting_queue[1:6]
        self.waiting_table.setRowCount(len(display_queue))
        
        type_colors = {
            'emergency': QColor(244, 67, 54),
            'vip': QColor(255, 152, 0),
            'priority': QColor(33, 150, 243),
            'normal': QColor(0, 0, 0),
        }
        
        for row, item in enumerate(display_queue):
            num_item = QTableWidgetItem(str(item['queue_number']))
            num_item.setTextAlignment(Qt.AlignCenter)
            self.waiting_table.setItem(row, 0, num_item)
            
            patient_item = QTableWidgetItem(item['patient_name'] or "")
            patient_item.setTextAlignment(Qt.AlignCenter)
            self.waiting_table.setItem(row, 1, patient_item)
            
            rule = priority_rule_manager.get_rule_by_type(item['patient_type'])
            type_name = rule['name'] if rule else "普通患者"
            type_item = QTableWidgetItem(type_name)
            type_item.setTextAlignment(Qt.AlignCenter)
            color = type_colors.get(item['patient_type'], QColor(0, 0, 0))
            type_item.setForeground(QBrush(color))
            self.waiting_table.setItem(row, 2, type_item)
        
        waiting_count = len(waiting_queue)
        completed_count = len([q for q in today_queue if q['status'] == 'completed'])
        
        self.waiting_count_label.setText(f"等待中: {waiting_count} 人")
        self.completed_count_label.setText(f"已完成: {completed_count} 人")


class QueueModule(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_queue)
        self.refresh_timer.start(5000)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_queue_tab(), "排队叫号")
        self.tabs.addTab(self.create_jump_tab(), "优先插队")
        self.tabs.addTab(self.create_history_tab(), "今日记录")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def create_queue_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        
        self.checkin_btn = QPushButton("患者取号")
        self.checkin_btn.setMinimumHeight(40)
        self.checkin_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        action_layout.addWidget(self.checkin_btn)
        
        self.call_next_btn = QPushButton("叫下一位")
        self.call_next_btn.setMinimumHeight(40)
        self.call_next_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #4CAF50; color: white;")
        action_layout.addWidget(self.call_next_btn)
        
        self.complete_btn = QPushButton("完成当前")
        self.complete_btn.setMinimumHeight(40)
        self.complete_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        action_layout.addWidget(self.complete_btn)
        
        self.cancel_btn = QPushButton("取消取号")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #f44336; color: white;")
        action_layout.addWidget(self.cancel_btn)
        
        self.show_display_btn = QPushButton("显示叫号屏")
        self.show_display_btn.setMinimumHeight(40)
        self.show_display_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2196F3; color: white;")
        action_layout.addWidget(self.show_display_btn)
        
        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)
        
        filter_group = QGroupBox("筛选")
        filter_layout = QFormLayout()
        
        self.chair_filter = QComboBox()
        self.chair_filter.addItem("全部", None)
        chairs = chair_manager.get_all_chairs()
        for chair in chairs:
            self.chair_filter.addItem(chair['name'], chair['id'])
        filter_layout.addRow("诊疗椅:", self.chair_filter)
        
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部", None)
        rules = priority_rule_manager.get_all_rules()
        for rule in rules:
            self.type_filter.addItem(rule['name'], rule['patient_type'])
        filter_layout.addRow("患者类型:", self.type_filter)
        
        self.apply_filter_btn = QPushButton("应用筛选")
        filter_layout.addRow("", self.apply_filter_btn)
        
        filter_group.setLayout(filter_layout)
        left_layout.addWidget(filter_group)
        
        stats_group = QGroupBox("统计信息")
        stats_layout = QFormLayout()
        
        self.total_waiting_label = QLabel("0")
        self.total_waiting_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f44336;")
        stats_layout.addRow("等待中:", self.total_waiting_label)
        
        self.today_called_label = QLabel("0")
        self.today_called_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3;")
        stats_layout.addRow("已叫号:", self.today_called_label)
        
        self.today_completed_label = QLabel("0")
        self.today_completed_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4CAF50;")
        stats_layout.addRow("已完成:", self.today_completed_label)
        
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        left_panel.setFixedWidth(280)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        current_group = QGroupBox("当前叫号")
        current_layout = QGridLayout()
        
        current_layout.addWidget(QLabel("号码:"), 0, 0)
        self.current_number_label = QLabel()
        self.current_number_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #1976D2;")
        current_layout.addWidget(self.current_number_label, 0, 1)
        
        current_layout.addWidget(QLabel("患者:"), 1, 0)
        self.current_patient_label = QLabel()
        self.current_patient_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        current_layout.addWidget(self.current_patient_label, 1, 1)
        
        current_layout.addWidget(QLabel("类型:"), 2, 0)
        self.current_type_label = QLabel()
        current_layout.addWidget(self.current_type_label, 2, 1)
        
        current_layout.addWidget(QLabel("诊疗椅:"), 3, 0)
        self.current_chair_label = QLabel()
        current_layout.addWidget(self.current_chair_label, 3, 1)
        
        current_layout.addWidget(QLabel("叫号时间:"), 4, 0)
        self.current_called_time_label = QLabel()
        current_layout.addWidget(self.current_called_time_label, 4, 1)
        
        current_group.setLayout(current_layout)
        right_layout.addWidget(current_group)
        
        queue_group = QGroupBox("等待队列")
        queue_layout = QVBoxLayout()
        
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(7)
        self.queue_table.setHorizontalHeaderLabels([
            "ID", "号码", "患者", "类型", "优先级", "诊疗椅", "等待时间"
        ])
        self.queue_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        queue_layout.addWidget(self.queue_table)
        
        queue_group.setLayout(queue_layout)
        right_layout.addWidget(queue_group)
        
        right_panel.setLayout(right_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([280, 900])
        
        main_layout.addWidget(splitter)
        widget.setLayout(main_layout)
        
        self.checkin_btn.clicked.connect(self.patient_checkin)
        self.call_next_btn.clicked.connect(self.call_next)
        self.complete_btn.clicked.connect(self.complete_current)
        self.cancel_btn.clicked.connect(self.cancel_queue)
        self.show_display_btn.clicked.connect(self.show_display)
        self.apply_filter_btn.clicked.connect(self.load_queue)
        self.chair_filter.currentIndexChanged.connect(self.load_queue)
        self.type_filter.currentIndexChanged.connect(self.load_queue)
        
        self.current_queue_item = None
        self.display_dialog = None
        
        return widget
    
    def create_jump_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        left_panel = QGroupBox("等待队列")
        left_layout = QVBoxLayout()
        
        self.jump_queue_list = QListWidget()
        self.jump_queue_list.itemDoubleClicked.connect(self.jump_selected)
        left_layout.addWidget(self.jump_queue_list)
        
        btn_layout = QHBoxLayout()
        self.jump_btn = QPushButton("优先插队")
        self.jump_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self.refresh_jump_btn = QPushButton("刷新")
        btn_layout.addWidget(self.jump_btn)
        btn_layout.addWidget(self.refresh_jump_btn)
        left_layout.addLayout(btn_layout)
        
        left_panel.setLayout(left_layout)
        left_panel.setFixedWidth(350)
        
        right_panel = QGroupBox("优先级规则")
        right_layout = QVBoxLayout()
        
        self.priority_table = QTableWidget()
        self.priority_table.setColumnCount(5)
        self.priority_table.setHorizontalHeaderLabels([
            "ID", "名称", "患者类型", "优先级", "可插队"
        ])
        self.priority_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.priority_table.setEditTriggers(QTableWidget.NoEditTriggers)
        right_layout.addWidget(self.priority_table)
        
        info_label = QLabel("""
        <h3>插队规则说明</h3>
        <ul>
        <li><b style="color: #f44336;">急诊</b> - 最高优先级，可直接插队到最前面</li>
        <li><b style="color: #FF9800;">VIP贵宾</b> - 高优先级，可插队到普通患者前面</li>
        <li><b style="color: #2196F3;">复诊优先</b> - 中等优先级，正常排队但优先于普通患者</li>
        <li><b>普通患者</b> - 正常优先级，按取号顺序排队</li>
        </ul>
        <p style="color: #666;">注意：只有设置为"可插队"的患者类型才能执行插队操作</p>
        """)
        info_label.setTextFormat(Qt.RichText)
        info_label.setWordWrap(True)
        right_layout.addWidget(info_label)
        
        right_panel.setLayout(right_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 800])
        
        main_layout.addWidget(splitter)
        widget.setLayout(main_layout)
        
        self.jump_btn.clicked.connect(self.jump_selected)
        self.refresh_jump_btn.clicked.connect(self.load_jump_data)
        
        return widget
    
    def create_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("状态:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部", None)
        self.status_filter.addItem("等待中", "waiting")
        self.status_filter.addItem("已叫号", "called")
        self.status_filter.addItem("已完成", "completed")
        self.status_filter.addItem("已取消", "cancelled")
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addWidget(QLabel("患者类型:"))
        self.history_type_filter = QComboBox()
        self.history_type_filter.addItem("全部", None)
        rules = priority_rule_manager.get_all_rules()
        for rule in rules:
            self.history_type_filter.addItem(rule['name'], rule['patient_type'])
        filter_layout.addWidget(self.history_type_filter)
        
        self.apply_history_filter_btn = QPushButton("查询")
        filter_layout.addWidget(self.apply_history_filter_btn)
        filter_layout.addStretch()
        
        self.refresh_history_btn = QPushButton("刷新")
        filter_layout.addWidget(self.refresh_history_btn)
        
        layout.addLayout(filter_layout)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels([
            "ID", "号码", "患者", "类型", "优先级", "诊疗椅", "签到时间", "叫号时间", "状态"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.history_table)
        
        widget.setLayout(layout)
        
        self.apply_history_filter_btn.clicked.connect(self.load_history)
        self.refresh_history_btn.clicked.connect(self.load_history)
        self.status_filter.currentIndexChanged.connect(self.load_history)
        self.history_type_filter.currentIndexChanged.connect(self.load_history)
        
        return widget
    
    def load_data(self):
        self.load_queue()
        self.load_jump_data()
        self.load_history()
        self.load_stats()
    
    def load_queue(self):
        chair_id = self.chair_filter.currentData()
        patient_type = self.type_filter.currentData()
        
        queue = queue_manager.get_waiting_queue(chair_id)
        
        if patient_type:
            queue = [q for q in queue if q['patient_type'] == patient_type]
        
        self.queue_table.setRowCount(len(queue))
        
        type_colors = {
            'emergency': QColor(244, 67, 54),
            'vip': QColor(255, 152, 0),
            'priority': QColor(33, 150, 243),
            'normal': QColor(0, 0, 0),
        }
        
        for row, item in enumerate(queue):
            self.queue_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            
            num_item = QTableWidgetItem(str(item['queue_number']))
            num_item.setTextAlignment(Qt.AlignCenter)
            self.queue_table.setItem(row, 1, num_item)
            
            self.queue_table.setItem(row, 2, QTableWidgetItem(item['patient_name'] or ""))
            
            rule = priority_rule_manager.get_rule_by_type(item['patient_type'])
            type_name = rule['name'] if rule else "普通患者"
            type_item = QTableWidgetItem(type_name)
            color = type_colors.get(item['patient_type'], QColor(0, 0, 0))
            type_item.setForeground(QBrush(color))
            self.queue_table.setItem(row, 3, type_item)
            
            priority_item = QTableWidgetItem(str(item['priority']))
            priority_item.setTextAlignment(Qt.AlignCenter)
            self.queue_table.setItem(row, 4, priority_item)
            
            self.queue_table.setItem(row, 5, QTableWidgetItem(item['chair_name'] or "不限"))
            
            wait_time = self._calculate_wait_time(item['checkin_time'])
            wait_item = QTableWidgetItem(wait_time)
            wait_item.setTextAlignment(Qt.AlignCenter)
            self.queue_table.setItem(row, 6, wait_item)
        
        self.load_current_called()
    
    def _calculate_wait_time(self, checkin_time_str):
        try:
            checkin_time = datetime.fromisoformat(checkin_time_str.replace('Z', '+00:00'))
            wait_seconds = (datetime.now() - checkin_time).total_seconds()
            
            if wait_seconds < 60:
                return f"{int(wait_seconds)}秒"
            elif wait_seconds < 3600:
                return f"{int(wait_seconds // 60)}分钟"
            else:
                hours = int(wait_seconds // 3600)
                minutes = int((wait_seconds % 3600) // 60)
                return f"{hours}小时{minutes}分钟"
        except:
            return "未知"
    
    def load_current_called(self):
        today_queue = queue_manager.get_today_queue()
        called = [q for q in today_queue if q['status'] == 'called']
        
        if called:
            current = called[0]
            self.current_queue_item = current
            self.current_number_label.setText(str(current['queue_number']))
            self.current_patient_label.setText(current['patient_name'] or "")
            
            rule = priority_rule_manager.get_rule_by_type(current['patient_type'])
            type_name = rule['name'] if rule else "普通患者"
            self.current_type_label.setText(type_name)
            
            self.current_chair_label.setText(current['chair_name'] or "不限")
            
            if current['called_time']:
                try:
                    called_time = datetime.fromisoformat(current['called_time'].replace('Z', '+00:00'))
                    self.current_called_time_label.setText(called_time.strftime("%H:%M:%S"))
                except:
                    self.current_called_time_label.setText("")
        else:
            self.current_queue_item = None
            self.current_number_label.setText("-")
            self.current_patient_label.setText("无")
            self.current_type_label.setText("")
            self.current_chair_label.setText("")
            self.current_called_time_label.setText("")
    
    def load_stats(self):
        today_queue = queue_manager.get_today_queue()
        waiting = len([q for q in today_queue if q['status'] == 'waiting'])
        called = len([q for q in today_queue if q['status'] == 'called'])
        completed = len([q for q in today_queue if q['status'] == 'completed'])
        
        self.total_waiting_label.setText(str(waiting))
        self.today_called_label.setText(str(called + completed))
        self.today_completed_label.setText(str(completed))
    
    def load_jump_data(self):
        self.jump_queue_list.clear()
        queue = queue_manager.get_waiting_queue()
        
        type_colors = {
            'emergency': QColor(244, 67, 54),
            'vip': QColor(255, 152, 0),
            'priority': QColor(33, 150, 243),
            'normal': QColor(0, 0, 0),
        }
        
        for item in queue:
            rule = priority_rule_manager.get_rule_by_type(item['patient_type'])
            type_name = rule['name'] if rule else "普通患者"
            can_jump = rule['can_jump'] if rule else False
            
            display = f"#{item['queue_number']} {item['patient_name'] or ''}\n  {type_name} | 优先级: {item['priority']}"
            if can_jump:
                display += " | 可插队"
            
            list_item = QListWidgetItem(display)
            list_item.setData(Qt.UserRole, item['id'])
            list_item.setData(Qt.UserRole + 1, item)
            
            color = type_colors.get(item['patient_type'], QColor(0, 0, 0))
            list_item.setForeground(QBrush(color))
            
            if can_jump:
                font = list_item.font()
                font.setBold(True)
                list_item.setFont(font)
            
            self.jump_queue_list.addItem(list_item)
        
        rules = priority_rule_manager.get_all_rules()
        self.priority_table.setRowCount(len(rules))
        
        for row, rule in enumerate(rules):
            self.priority_table.setItem(row, 0, QTableWidgetItem(str(rule['id'])))
            self.priority_table.setItem(row, 1, QTableWidgetItem(rule['name']))
            self.priority_table.setItem(row, 2, QTableWidgetItem(rule['patient_type']))
            
            priority_item = QTableWidgetItem(str(rule['priority_level']))
            priority_item.setTextAlignment(Qt.AlignCenter)
            self.priority_table.setItem(row, 3, priority_item)
            
            can_jump_text = "是" if rule['can_jump'] else "否"
            can_jump_item = QTableWidgetItem(can_jump_text)
            can_jump_item.setTextAlignment(Qt.AlignCenter)
            if rule['can_jump']:
                can_jump_item.setForeground(QBrush(QColor(76, 175, 80)))
            self.priority_table.setItem(row, 4, can_jump_item)
    
    def load_history(self):
        status = self.status_filter.currentData()
        patient_type = self.history_type_filter.currentData()
        
        queue = queue_manager.get_today_queue()
        
        if status:
            queue = [q for q in queue if q['status'] == status]
        
        if patient_type:
            queue = [q for q in queue if q['patient_type'] == patient_type]
        
        self.history_table.setRowCount(len(queue))
        
        status_names = {
            'waiting': '等待中',
            'called': '已叫号',
            'completed': '已完成',
            'cancelled': '已取消',
        }
        
        status_colors = {
            'waiting': QColor(255, 193, 7),
            'called': QColor(33, 150, 243),
            'completed': QColor(76, 175, 80),
            'cancelled': QColor(244, 67, 54),
        }
        
        for row, item in enumerate(queue):
            self.history_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            
            num_item = QTableWidgetItem(str(item['queue_number']))
            num_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(row, 1, num_item)
            
            self.history_table.setItem(row, 2, QTableWidgetItem(item['patient_name'] or ""))
            
            rule = priority_rule_manager.get_rule_by_type(item['patient_type'])
            type_name = rule['name'] if rule else "普通患者"
            self.history_table.setItem(row, 3, QTableWidgetItem(type_name))
            
            priority_item = QTableWidgetItem(str(item['priority']))
            priority_item.setTextAlignment(Qt.AlignCenter)
            self.history_table.setItem(row, 4, priority_item)
            
            self.history_table.setItem(row, 5, QTableWidgetItem(item['chair_name'] or "不限"))
            
            checkin_time = ""
            if item['checkin_time']:
                try:
                    dt = datetime.fromisoformat(item['checkin_time'].replace('Z', '+00:00'))
                    checkin_time = dt.strftime("%H:%M:%S")
                except:
                    pass
            self.history_table.setItem(row, 6, QTableWidgetItem(checkin_time))
            
            called_time = ""
            if item['called_time']:
                try:
                    dt = datetime.fromisoformat(item['called_time'].replace('Z', '+00:00'))
                    called_time = dt.strftime("%H:%M:%S")
                except:
                    pass
            self.history_table.setItem(row, 7, QTableWidgetItem(called_time))
            
            status_name = status_names.get(item['status'], item['status'])
            status_item = QTableWidgetItem(status_name)
            status_item.setTextAlignment(Qt.AlignCenter)
            color = status_colors.get(item['status'], QColor(0, 0, 0))
            status_item.setForeground(QBrush(color))
            self.history_table.setItem(row, 8, status_item)
        
        self.load_stats()
    
    def patient_checkin(self):
        dialog = CheckinDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            
            try:
                queue_item = queue_manager.add_to_queue(
                    data['patient_id'], data['schedule_id'],
                    data['chair_id'], data['patient_type'],
                    data['is_jump']
                )
                
                if data['is_jump']:
                    QMessageBox.information(self, "成功", 
                        f"患者已优先插队！\n号码: {queue_item['queue_number']}\n位置: 第1位")
                else:
                    QMessageBox.information(self, "成功", 
                        f"患者取号成功！\n号码: {queue_item['queue_number']}\n前面有 {queue_item['queue_number'] - 1} 人")
                
                self.load_queue()
                self.load_jump_data()
                self.load_history()
                
            except ValueError as e:
                QMessageBox.warning(self, "错误", str(e))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"取号失败: {str(e)}")
    
    def call_next(self):
        chair_id = self.chair_filter.currentData()
        
        called = queue_manager.call_next(chair_id)
        if called:
            patient_name = called['patient_name'] or "未知患者"
            message = f"请 {patient_name} 到 {called['chair_name'] or '指定诊疗椅'} 就诊\n号码: {called['queue_number']}"
            
            QMessageBox.information(self, "叫号", message)
            self.load_queue()
            self.load_jump_data()
            self.load_history()
        else:
            QMessageBox.information(self, "提示", "没有等待的患者")
    
    def complete_current(self):
        if not self.current_queue_item:
            QMessageBox.warning(self, "提示", "没有当前叫号的患者")
            return
        
        reply = QMessageBox.question(self, "确认", 
            f"确定完成 {self.current_queue_item['patient_name']} 的就诊吗？",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            queue_manager.complete_queue(self.current_queue_item['id'])
            self.load_queue()
            self.load_jump_data()
            self.load_history()
    
    def cancel_queue(self):
        current_row = self.queue_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请选择要取消的患者")
            return
        
        queue_id = int(self.queue_table.item(current_row, 0).text())
        queue_item = queue_manager.get_queue_item(queue_id)
        
        reply = QMessageBox.question(self, "确认", 
            f"确定取消 {queue_item['patient_name']} 的取号吗？",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            queue_manager.cancel_queue(queue_id)
            self.load_queue()
            self.load_jump_data()
            self.load_history()
    
    def show_display(self):
        if not self.display_dialog:
            self.display_dialog = CallingDisplayDialog(self)
        self.display_dialog.show()
        self.display_dialog.raise_()
        self.display_dialog.activateWindow()
    
    def jump_selected(self):
        current_item = self.jump_queue_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请选择要插队的患者")
            return
        
        queue_item = current_item.data(Qt.UserRole + 1)
        if not queue_item:
            return
        
        rule = priority_rule_manager.get_rule_by_type(queue_item['patient_type'])
        if not rule or not rule['can_jump']:
            QMessageBox.warning(self, "提示", "该患者类型不允许插队")
            return
        
        dialog = JumpQueueDialog(self, queue_item)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            
            try:
                success = queue_manager.jump_queue(queue_item['id'], data['target_position'])
                if success:
                    QMessageBox.information(self, "成功", 
                        f"患者已插队到第 {data['target_position']} 位")
                    self.load_queue()
                    self.load_jump_data()
                    self.load_history()
                else:
                    QMessageBox.warning(self, "失败", "插队失败")
            except ValueError as e:
                QMessageBox.warning(self, "错误", str(e))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"插队失败: {str(e)}")
