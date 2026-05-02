from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
import sqlite3
import numpy as np  
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from secureforensic_fyp import fetch_pending_users

class AdminDashboard(QtWidgets.QMainWindow):
    def __init__(self, name="Master Admin"):
        super().__init__()
        self.user_name = name
        self.setWindowTitle("Secure Forensic - Executive Admin Panel")
        self.showMaximized()
        
        # Database Path
        self.DB_PATH = r"C:\ProgramData\SecureForensic\forensic.db"
        
        # UI Styling (Blue Theme)
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QFrame#Sidebar { background-color: #0078d7; min-width: 280px; max-width: 280px; }
            QLabel#LogoText { color: white; font-size: 20px; font-weight: bold; padding: 20px; border-bottom: 1px solid #005a9e; }
            
            QPushButton#NavBtn { 
                text-align: left; padding-left: 15px; border: none; 
                border-radius: 5px; font-size: 13px; color: #ffffff; 
                background-color: transparent; margin: 2px 10px; height: 42px;
            }
            QPushButton#NavBtn:hover { background-color: #005a9e; color: white; }
            
            QTableWidget { background-color: white; border: 1px solid #dee2e6; border-radius: 8px; }
            QHeaderView::section { background-color: #0078d7; color: white; padding: 10px; font-weight: bold; font-size: 12px; }
            
            QFrame#ChartCard { background-color: white; border-radius: 12px; border: 1px solid #dcdde1; padding: 10px; }
        """)

        self.initUI()
        self.show_dashboard_overview()

    def fetch_logs(self, condition="1=1"):
        if not os.path.exists(self.DB_PATH): return []
        try:
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            query = f"SELECT username, role, action, method, file_name, file_path, time FROM logs WHERE {condition} ORDER BY id DESC"
            cursor.execute(query)
            data = cursor.fetchall()
            conn.close()
            return data
        except Exception as e:
            print(f"DB Error: {e}")
            return []

    def initUI(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
    
        # --- SIDEBAR ---
        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("Sidebar")
        side_layout = QtWidgets.QVBoxLayout(sidebar)
        
        logo = QtWidgets.QLabel("SECURE FORENSIC")
        logo.setObjectName("LogoText")
        side_layout.addWidget(logo, alignment=QtCore.Qt.AlignCenter)

        # Navigation Buttons
        btns = [
            ("📊 Dashboard Overview", self.show_dashboard_overview),
            ("📂 File Activity (C:)", self.show_file_activity),
            ("🌐 Network / LAN Logs", self.show_network_logs),
            ("📧 Email & Cloud", self.show_web_logs),
            ("🔌 USB & Storage", self.show_storage_logs),
            ("⚠️ System Alerts", self.show_alerts),
            ("🔍 Hash Integrity Check", self.show_integrity_check),
            ("👤 User Approvals", self.show_user_approvals_panel),
            ("🖥️ System Monitoring", self.show_system_monitoring)
        ]

        for text, func in btns:
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.clicked.connect(func)
            side_layout.addWidget(btn)
        
        side_layout.addStretch()

        logout_btn = QtWidgets.QPushButton("🚪 Logout")
        logout_btn.setObjectName("NavBtn")
        logout_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; margin-bottom: 20px;")
        logout_btn.clicked.connect(self.close)
        side_layout.addWidget(logout_btn)
        
        main_layout.addWidget(sidebar)

        # --- MAIN CONTENT ---
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        main_content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(main_content)
        self.content_layout.setContentsMargins(25, 25, 25, 25)
        
        self.title_label = QtWidgets.QLabel("Executive Dashboard Overview")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px; color: #2c3e50;")
        self.content_layout.addWidget(self.title_label)

        self.chart_container = QtWidgets.QFrame()
        self.chart_container.setObjectName("ChartCard")
        self.chart_container.setMinimumHeight(450) 
        self.chart_layout = QtWidgets.QHBoxLayout(self.chart_container)
        self.content_layout.addWidget(self.chart_container)

        self.table = QtWidgets.QTableWidget()
        self.table.setMinimumHeight(400)
        self.content_layout.addWidget(self.table, 1)

        scroll_area.setWidget(main_content)
        main_layout.addWidget(scroll_area)

    def draw_charts(self, logs):
        while self.chart_layout.count():
            item = self.chart_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if self.title_label.text() in ["User Registration Approvals", "System Health Monitoring"] or not logs:
            self.chart_container.hide()
            return
        
        self.chart_container.show()
        fig = plt.figure(figsize=(12, 7))
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        summary_data = []
        for d in logs:
            combined_text = (str(d[2]) + " " + str(d[3])).upper()
            neg_keys = ["FAIL", "MISMATCH", "UNAUTHORIZED", "BLOCKED", "ERROR", "DENIED"]

            if any(x in combined_text for x in neg_keys):
                summary_data.append("Failure/Alert ⚠️")
            else:
                summary_data.append("Success ✅")

        if summary_data:
            labels = list(set(summary_data))
            sizes = [summary_data.count(l) for l in labels]
            color_map = {"Success ✅": "#2ecc71", "Failure/Alert ⚠️": "#e74c3c"}
            colors = [color_map.get(l, "#3498db") for l in labels]
            
            wedges, _ = ax1.pie(sizes, startangle=140, colors=colors, wedgeprops=dict(width=0.5, edgecolor='w'))
            for i, p in enumerate(wedges):
                ang = (p.theta2 - p.theta1)/2. + p.theta1
                y, x = np.sin(np.deg2rad(ang)), np.cos(np.deg2rad(ang))
                percentage = (sizes[i]/sum(sizes))*100
                ax1.annotate(f'{percentage:.1f}%', xy=(x*0.75, y*0.75), ha='center', va='center', fontsize=10, fontweight='bold')

            ax1.legend(wedges, labels, loc="upper center", bbox_to_anchor=(0.5, -0.05), ncol=2, fontsize=9, frameon=False)
            ax1.set_title("Overall Efficiency Rate", fontsize=11, fontweight='bold')

        methods = [str(d[3]).upper() for d in logs if d[3]]
        if methods:
            m_labels = list(set(methods))
            m_counts = [methods.count(m) for m in m_labels]
            ax2.bar(m_labels, m_counts, color='#0078d7')
            plt.setp(ax2.get_xticklabels(), rotation=30, ha='right', fontsize=8)
            ax2.set_title("Activity by Method", fontsize=11, fontweight='bold')

        fig.tight_layout(pad=5.0)
        canvas = FigureCanvas(fig)
        self.chart_layout.addWidget(canvas)

    def update_table(self, headers, data):
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        for row_idx, row_data in enumerate(data):
            self.table.insertRow(row_idx)
            is_danger = False
            for col_idx, value in enumerate(row_data):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                val_upper = str(value).upper()
                if any(x in val_upper for x in ["MISMATCH", "UNAUTHORIZED", "FAILED", "ERROR"]):
                    is_danger = True
                self.table.setItem(row_idx, col_idx, item)
            
            if is_danger:
                for c in range(self.table.columnCount()):
                    if self.table.item(row_idx, c):
                        self.table.item(row_idx, c).setForeground(QtGui.QColor("red"))

    def show_dashboard_overview(self):
        self.title_label.setText("Executive Dashboard Overview")
        logs = self.fetch_logs()
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], logs)
        self.draw_charts(logs)

    def show_file_activity(self):
        self.title_label.setText("File Activity")
        logs = self.fetch_logs("action LIKE '%DOWNLOAD%' OR action LIKE '%COPIED%'")
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], logs)
        self.draw_charts(logs)

    def show_network_logs(self):
        self.title_label.setText("Network Logs")
        # --- YE HAI FIX ---
        # Humne keywords barha diye hain: SOCKET, IP, PORT, TCP aur LAN
        # Aur sakhti se SMTP (Email) aur DRIVE ko nikaal diya hai
        condition = """
            (method LIKE '%LAN%' OR 
             method LIKE '%SOCKET%' OR 
             method LIKE '%TCP%' OR 
             method LIKE '%IP%' OR 
             action LIKE '%TRANSFER%' OR 
             action LIKE '%SENT%') 
            AND method NOT LIKE '%SMTP%' 
            AND method NOT LIKE '%DRIVE%'
            AND method NOT LIKE '%WEB%'
        """
        logs = self.fetch_logs(condition)
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], logs)
        self.draw_charts(logs)

    def show_web_logs(self):
        self.title_label.setText("Web & Cloud Logs")
        # FIXED: Specific keywords for Web, Email and G-Drive
        logs = self.fetch_logs("method LIKE '%WEB%' OR method LIKE '%DRIVE%' OR method LIKE '%SMTP%'")
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], logs)
        self.draw_charts(logs)

    def show_storage_logs(self):
        self.title_label.setText("Storage Logs")
        logs = self.fetch_logs("method LIKE '%STORAGE%' OR method LIKE '%USB%'")
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], logs)
        self.draw_charts(logs)

    def show_alerts(self):
        self.title_label.setText("Security Alerts")
        logs = self.fetch_logs("action LIKE '%UNAUTHORIZED%' OR action LIKE '%FAIL%' OR action LIKE '%MISMATCH%'")
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], logs)
        self.draw_charts(logs)

    def show_integrity_check(self):
        self.title_label.setText("Hash Integrity Verification")
        logs = self.fetch_logs("action LIKE '%HASH%' OR action LIKE '%INTEGRITY%'")
        hash_data = []
        for r in logs:
            act = str(r[2]).upper()
            is_fail = any(x in act for x in ["FAIL", "MISMATCH", "ERROR", "INVALID"])
            status = "MISMATCH ❌" if is_fail else "MATCH ✅"
            hash_data.append([r[4], "SHA-256", "Source Verified", "Dest Verified", status, r[6]])
        
        self.update_table(["File Name", "Algorithm", "Sender Hash", "Receiver Hash", "Integrity Status", "Timestamp"], hash_data)
        self.draw_charts(logs)

    def show_user_approvals_panel(self):
        self.title_label.setText("User Registration Approvals")
        users = fetch_pending_users()
        self.update_table(["User", "Email", "Role", "Status", "Date"], users)
        self.chart_container.hide()

    def show_system_monitoring(self):
        self.title_label.setText("System Health Monitoring")
        self.update_table(["User", "Role", "Action", "Method", "File Name", "Path", "Time"], self.fetch_logs())
        self.chart_container.hide()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = AdminDashboard()
    win.show()
    sys.exit(app.exec_())
