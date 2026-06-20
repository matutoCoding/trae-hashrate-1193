from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDateEdit, QTimeEdit, QMessageBox, QLabel, QHeaderView,
    QTabWidget, QGroupBox, QTextEdit, QCheckBox, QListWidget, QListWidgetItem,
    QSplitter, QFrame, QProgressDialog
)
from PySide6.QtCore import Qt, QDate, QTime, QTimer
from PySide6.QtGui import QColor, QBrush, QFont
from datetime import date, datetime, timedelta
from database import (
    reminder_manager, schedule_manager, patient_manager,
    chair_manager, priority_rule_manager
)


class ReminderModule(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_data()
        
        self.reminder_timer = QTimer()
        self.reminder_timer.timeout.connect(self.check_pending_reminders)
        self.reminder_timer.start(60000)
        
        QTimer.singleShot(1000, self.check_pending_reminders)
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_pending_tab(), "待发送提醒")
        self.tabs.addTab(self.create_history_tab(), "提醒记录")
        self.tabs.addTab(self.create_settings_tab(), "提醒设置")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
    
    def create_pending_tab(self):
        widget = QWidget()
        main_layout = QHBoxLayout()
        
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        
        self.generate_reminder_btn = QPushButton("批量生成提醒")
        self.generate_reminder_btn.setMinimumHeight(40)
        action_layout.addWidget(self.generate_reminder_btn)
        
        self.send_selected_btn = QPushButton("发送选中")
        self.send_selected_btn.setMinimumHeight(40)
        self.send_selected_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        action_layout.addWidget(self.send_selected_btn)
        
        self.send_all_btn = QPushButton("发送全部")
        self.send_all_btn.setMinimumHeight(40)
        self.send_all_btn.setStyleSheet("background-color: #2196F3; color: white;")
        action_layout.addWidget(self.send_all_btn)
        
        self.refresh_pending_btn = QPushButton("刷新")
        self.refresh_pending_btn.setMinimumHeight(40)
        action_layout.addWidget(self.refresh_pending_btn)
        
        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)
        
        stats_group = QGroupBox("统计信息")
        stats_layout = QFormLayout()
        
        self.pending_count_label = QLabel("0")
        self.pending_count_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #f44336;")
        stats_layout.addRow("待发送:", self.pending_count_label)
        
        self.sent_today_label = QLabel("0")
        self.sent_today_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
        stats_layout.addRow("今日已发:", self.sent_today_label)
        
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)
        
        info_group = QGroupBox("说明")
        info_layout = QVBoxLayout()
        info_label = QLabel("""
        <p style="color: #666;">
        系统会自动检查即将到来的复诊预约，<br>
        并在预约时间前发送提醒。<br><br>
        提醒提前时间可在"提醒设置"中配置。
        </p>
        """)
        info_label.setTextFormat(Qt.RichText)
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        left_panel.setFixedWidth(250)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        self.pending_table = QTableWidget()
        self.pending_table.setColumnCount(7)
        self.pending_table.setHorizontalHeaderLabels([
            "选择", "ID", "患者", "电话", "复诊时间", "诊疗椅", "提醒时间"
        ])
        self.pending_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pending_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pending_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pending_table.setEditTriggers(QTableWidget.NoEditTriggers)
        right_layout.addWidget(self.pending_table)
        
        right_panel.setLayout(right_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 900])
        
        main_layout.addWidget(splitter)
        widget.setLayout(main_layout)
        
        self.generate_reminder_btn.clicked.connect(self.generate_batch_reminders)
        self.send_selected_btn.clicked.connect(self.send_selected_reminders)
        self.send_all_btn.clicked.connect(self.send_all_reminders)
        self.refresh_pending_btn.clicked.connect(self.load_pending_reminders)
        
        return widget
    
    def create_history_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("状态:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部", None)
        self.status_filter.addItem("待发送", "pending")
        self.status_filter.addItem("已发送", "sent")
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addWidget(QLabel("日期范围:"))
        self.history_start_date = QDateEdit()
        self.history_start_date.setCalendarPopup(True)
        default_start = date.today() - timedelta(days=7)
        self.history_start_date.setDate(QDate(default_start.year, default_start.month, default_start.day))
        filter_layout.addWidget(self.history_start_date)
        filter_layout.addWidget(QLabel("至"))
        self.history_end_date = QDateEdit()
        self.history_end_date.setCalendarPopup(True)
        self.history_end_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.history_end_date)
        
        self.apply_filter_btn = QPushButton("查询")
        filter_layout.addWidget(self.apply_filter_btn)
        filter_layout.addStretch()
        
        self.refresh_history_btn = QPushButton("刷新")
        filter_layout.addWidget(self.refresh_history_btn)
        
        layout.addLayout(filter_layout)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "ID", "患者", "电话", "复诊时间", "诊疗椅", "提醒时间", "发送时间", "状态"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.history_table)
        
        widget.setLayout(layout)
        
        self.apply_filter_btn.clicked.connect(self.load_reminder_history)
        self.refresh_history_btn.clicked.connect(self.load_reminder_history)
        self.status_filter.currentIndexChanged.connect(self.load_reminder_history)
        
        return widget
    
    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        settings_group = QGroupBox("提醒设置")
        settings_layout = QFormLayout()
        
        self.reminder_minutes_spin = QSpinBox()
        self.reminder_minutes_spin.setRange(5, 1440)
        self.reminder_minutes_spin.setSuffix(" 分钟")
        self.reminder_minutes_spin.setValue(30)
        self.reminder_minutes_spin.setToolTip("复诊前多少分钟发送提醒")
        settings_layout.addRow("提前提醒时间:", self.reminder_minutes_spin)
        
        self.auto_send_check = QCheckBox("自动发送提醒")
        self.auto_send_check.setChecked(True)
        settings_layout.addRow("", self.auto_send_check)
        
        self.reminder_template_edit = QTextEdit()
        self.reminder_template_edit.setPlaceholderText("提醒消息模板，可用变量：{患者姓名}、{复诊时间}、{诊疗椅}")
        default_template = "您好，{患者姓名}！您的复诊时间是 {复诊时间}，请准时到 {诊疗椅} 就诊。"
        self.reminder_template_edit.setPlainText(default_template)
        self.reminder_template_edit.setMaximumHeight(100)
        settings_layout.addRow("提醒模板:", self.reminder_template_edit)
        
        save_btn = QPushButton("保存设置")
        save_btn.setMinimumHeight(40)
        save_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.save_settings)
        settings_layout.addRow("", save_btn)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        test_group = QGroupBox("测试提醒")
        test_layout = QFormLayout()
        
        self.test_patient_combo = QComboBox()
        self.load_test_patients()
        test_layout.addRow("测试患者:", self.test_patient_combo)
        
        self.test_message_edit = QLineEdit()
        self.test_message_edit.setPlaceholderText("测试消息内容")
        test_layout.addRow("测试消息:", self.test_message_edit)
        
        test_send_btn = QPushButton("发送测试提醒")
        test_send_btn.setMinimumHeight(40)
        test_send_btn.clicked.connect(self.send_test_reminder)
        test_layout.addRow("", test_send_btn)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        preview_group = QGroupBox("即将到来的复诊")
        preview_layout = QVBoxLayout()
        
        self.upcoming_table = QTableWidget()
        self.upcoming_table.setColumnCount(5)
        self.upcoming_table.setHorizontalHeaderLabels([
            "患者", "电话", "复诊时间", "诊疗椅", "状态"
        ])
        self.upcoming_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.upcoming_table.setEditTriggers(QTableWidget.NoEditTriggers)
        preview_layout.addWidget(self.upcoming_table)
        
        refresh_upcoming_btn = QPushButton("刷新")
        refresh_upcoming_btn.clicked.connect(self.load_upcoming_schedules)
        preview_layout.addWidget(refresh_upcoming_btn)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        
        self.load_settings()
        self.load_upcoming_schedules()
        
        return widget
    
    def load_data(self):
        self.load_pending_reminders()
        self.load_reminder_history()
        self.load_stats()
    
    def load_settings(self):
        cursor = chair_manager.db.execute(
            "SELECT value FROM settings WHERE key='reminder_minutes_before'"
        )
        row = cursor.fetchone()
        if row:
            self.reminder_minutes_spin.setValue(int(row['value']))
    
    def save_settings(self):
        minutes = self.reminder_minutes_spin.value()
        template = self.reminder_template_edit.toPlainText().strip()
        
        chair_manager.db.execute('''
            INSERT OR REPLACE INTO settings (key, value, description)
            VALUES ('reminder_minutes_before', ?, '复诊提醒提前分钟数')
        ''', (str(minutes),))
        chair_manager.db.commit()
        
        chair_manager.db.execute('''
            INSERT OR REPLACE INTO settings (key, value, description)
            VALUES ('reminder_template', ?, '提醒消息模板')
        ''', (template,))
        chair_manager.db.commit()
        
        QMessageBox.information(self, "成功", "设置已保存")
        self.load_settings()
    
    def load_test_patients(self):
        self.test_patient_combo.clear()
        patients = patient_manager.get_all_patients()
        for patient in patients:
            display = f"{patient['name']} ({patient['phone'] or '无电话'})"
            self.test_patient_combo.addItem(display, patient['id'])
    
    def load_pending_reminders(self):
        reminders = reminder_manager.get_pending_reminders()
        self.pending_table.setRowCount(len(reminders))
        
        for row, reminder in enumerate(reminders):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox.setCheckState(Qt.Unchecked)
            self.pending_table.setItem(row, 0, checkbox)
            
            self.pending_table.setItem(row, 1, QTableWidgetItem(str(reminder['id'])))
            self.pending_table.setItem(row, 2, QTableWidgetItem(reminder['patient_name'] or ""))
            self.pending_table.setItem(row, 3, QTableWidgetItem(reminder['patient_phone'] or ""))
            
            schedule_time = f"{reminder['schedule_date']} {reminder['start_time']}"
            self.pending_table.setItem(row, 4, QTableWidgetItem(schedule_time))
            
            self.pending_table.setItem(row, 5, QTableWidgetItem(reminder['chair_name'] or ""))
            
            try:
                rt = datetime.fromisoformat(reminder['reminder_time'].replace('Z', '+00:00'))
                self.pending_table.setItem(row, 6, QTableWidgetItem(rt.strftime("%Y-%m-%d %H:%M")))
            except:
                self.pending_table.setItem(row, 6, QTableWidgetItem(reminder['reminder_time']))
        
        self.load_stats()
    
    def load_reminder_history(self):
        status = self.status_filter.currentData()
        
        qstart = self.history_start_date.date()
        qend = self.history_end_date.date()
        start_date = date(qstart.year(), qstart.month(), qstart.day())
        end_date = date(qend.year(), qend.month(), qend.day())
        
        all_reminders = reminder_manager.get_all_reminders(limit=500)
        
        filtered = []
        for r in all_reminders:
            try:
                rt = datetime.fromisoformat(r['reminder_time'].replace('Z', '+00:00')).date()
                if start_date <= rt <= end_date:
                    if not status or r['status'] == status:
                        filtered.append(r)
            except:
                continue
        
        self.history_table.setRowCount(len(filtered))
        
        status_names = {
            'pending': '待发送',
            'sent': '已发送',
        }
        
        status_colors = {
            'pending': QColor(255, 193, 7),
            'sent': QColor(76, 175, 80),
        }
        
        for row, reminder in enumerate(filtered):
            self.history_table.setItem(row, 0, QTableWidgetItem(str(reminder['id'])))
            self.history_table.setItem(row, 1, QTableWidgetItem(reminder['patient_name'] or ""))
            self.history_table.setItem(row, 2, QTableWidgetItem(reminder['patient_phone'] or ""))
            
            schedule_time = f"{reminder['schedule_date']} {reminder['start_time']}"
            self.history_table.setItem(row, 3, QTableWidgetItem(schedule_time))
            
            self.history_table.setItem(row, 4, QTableWidgetItem(reminder['chair_name'] or ""))
            
            try:
                rt = datetime.fromisoformat(reminder['reminder_time'].replace('Z', '+00:00'))
                self.history_table.setItem(row, 5, QTableWidgetItem(rt.strftime("%Y-%m-%d %H:%M")))
            except:
                self.history_table.setItem(row, 5, QTableWidgetItem(reminder['reminder_time']))
            
            sent_time = ""
            if reminder['sent_time']:
                try:
                    st = datetime.fromisoformat(reminder['sent_time'].replace('Z', '+00:00'))
                    sent_time = st.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    sent_time = reminder['sent_time']
            self.history_table.setItem(row, 6, QTableWidgetItem(sent_time))
            
            status_name = status_names.get(reminder['status'], reminder['status'])
            status_item = QTableWidgetItem(status_name)
            color = status_colors.get(reminder['status'], QColor(0, 0, 0))
            status_item.setForeground(QBrush(color))
            self.history_table.setItem(row, 7, status_item)
    
    def load_upcoming_schedules(self):
        schedules = schedule_manager.get_upcoming_schedules(days=7)
        self.upcoming_table.setRowCount(len(schedules))
        
        status_names = {
            'available': '可用',
            'booked': '已预约',
            'completed': '已完成',
            'cancelled': '已取消',
        }
        
        for row, sched in enumerate(schedules):
            self.upcoming_table.setItem(row, 0, QTableWidgetItem(sched['patient_name'] or ""))
            self.upcoming_table.setItem(row, 1, QTableWidgetItem(sched['patient_phone'] or ""))
            
            schedule_time = f"{sched['schedule_date']} {sched['start_time']}"
            self.upcoming_table.setItem(row, 2, QTableWidgetItem(schedule_time))
            
            self.upcoming_table.setItem(row, 3, QTableWidgetItem(sched['chair_name'] or ""))
            
            status_item = QTableWidgetItem(status_names.get(sched['status'], sched['status']))
            if sched['status'] == 'booked':
                status_item.setForeground(QBrush(QColor(33, 150, 243)))
            self.upcoming_table.setItem(row, 4, status_item)
    
    def load_stats(self):
        pending = reminder_manager.get_pending_reminders()
        self.pending_count_label.setText(str(len(pending)))
        
        today = date.today().isoformat()
        cursor = chair_manager.db.execute('''
            SELECT COUNT(*) as count FROM reminders 
            WHERE DATE(sent_time) = ? AND status = 'sent'
        ''', (today,))
        row = cursor.fetchone()
        self.sent_today_label.setText(str(row['count'] if row else 0))
    
    def check_pending_reminders(self):
        if not self.auto_send_check.isChecked():
            return
        
        reminders = reminder_manager.get_pending_reminders()
        
        for reminder in reminders:
            try:
                reminder_time = datetime.fromisoformat(reminder['reminder_time'].replace('Z', '+00:00'))
                now = datetime.now()
                
                if reminder_time <= now:
                    self._send_reminder(reminder)
            except:
                continue
    
    def _send_reminder(self, reminder):
        patient_name = reminder['patient_name'] or "患者"
        schedule_time = f"{reminder['schedule_date']} {reminder['start_time']}"
        chair_name = reminder['chair_name'] or "诊疗椅"
        
        message = self.reminder_template_edit.toPlainText().strip()
        if not message:
            message = f"复诊提醒：{patient_name}，您的复诊时间是 {schedule_time}，请准时到 {chair_name} 就诊。"
        else:
            message = message.replace("{患者姓名}", patient_name)
            message = message.replace("{复诊时间}", schedule_time)
            message = message.replace("{诊疗椅}", chair_name)
        
        print(f"[提醒系统] 发送提醒给 {patient_name}: {message}")
        
        reminder_manager.mark_reminder_sent(reminder['id'])
        
        return True
    
    def generate_batch_reminders(self):
        progress = QProgressDialog("正在生成提醒...", "取消", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        progress.show()
        
        try:
            count = reminder_manager.generate_batch_reminders(days=7)
            progress.setValue(100)
            
            QMessageBox.information(self, "成功", f"成功生成 {count} 条提醒")
            self.load_pending_reminders()
            self.load_reminder_history()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成提醒失败: {str(e)}")
        finally:
            progress.close()
    
    def send_selected_reminders(self):
        selected_ids = []
        for row in range(self.pending_table.rowCount()):
            item = self.pending_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                reminder_id = int(self.pending_table.item(row, 1).text())
                selected_ids.append(reminder_id)
        
        if not selected_ids:
            QMessageBox.warning(self, "提示", "请选择要发送的提醒")
            return
        
        reply = QMessageBox.question(self, "确认", 
            f"确定发送选中的 {len(selected_ids)} 条提醒吗？",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        progress = QProgressDialog("正在发送提醒...", "取消", 0, len(selected_ids), self)
        progress.setWindowModality(Qt.WindowModal)
        
        sent_count = 0
        for i, reminder_id in enumerate(selected_ids):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            
            cursor = chair_manager.db.execute('''
                SELECT r.*, p.name as patient_name, p.phone as patient_phone,
                       s.schedule_date, s.start_time, c.name as chair_name
                FROM reminders r
                LEFT JOIN patients p ON r.patient_id = p.id
                LEFT JOIN schedules s ON r.schedule_id = s.id
                LEFT JOIN chairs c ON s.chair_id = c.id
                WHERE r.id = ?
            ''', (reminder_id,))
            reminder = cursor.fetchone()
            
            if reminder:
                self._send_reminder(dict(reminder))
                sent_count += 1
        
        progress.setValue(len(selected_ids))
        
        QMessageBox.information(self, "完成", f"成功发送 {sent_count} 条提醒")
        self.load_pending_reminders()
        self.load_reminder_history()
        self.load_stats()
    
    def send_all_reminders(self):
        pending = reminder_manager.get_pending_reminders()
        if not pending:
            QMessageBox.information(self, "提示", "没有待发送的提醒")
            return
        
        reply = QMessageBox.question(self, "确认", 
            f"确定发送全部 {len(pending)} 条提醒吗？",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        progress = QProgressDialog("正在发送提醒...", "取消", 0, len(pending), self)
        progress.setWindowModality(Qt.WindowModal)
        
        sent_count = 0
        for i, reminder in enumerate(pending):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            self._send_reminder(reminder)
            sent_count += 1
        
        progress.setValue(len(pending))
        
        QMessageBox.information(self, "完成", f"成功发送 {sent_count} 条提醒")
        self.load_pending_reminders()
        self.load_reminder_history()
        self.load_stats()
    
    def send_test_reminder(self):
        patient_id = self.test_patient_combo.currentData()
        message = self.test_message_edit.text().strip()
        
        if not patient_id:
            QMessageBox.warning(self, "提示", "请选择测试患者")
            return
        
        if not message:
            QMessageBox.warning(self, "提示", "请输入测试消息")
            return
        
        patient = patient_manager.get_patient(patient_id)
        if not patient:
            QMessageBox.warning(self, "提示", "无效的患者")
            return
        
        print(f"[测试提醒] 发送给 {patient['name']} ({patient['phone']}): {message}")
        
        QMessageBox.information(self, "成功", 
            f"测试提醒已发送！\n\n患者: {patient['name']}\n电话: {patient['phone'] or '无'}\n消息: {message}")
