from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
import socket
import json
import threading
import hashlib
import string
import shutil
import random
import imaplib
import email
import urllib.request 
from datetime import datetime
import landing_page
import sqlite3

# --- ENCRYPTION IMPORTS ---
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Error: 'cryptography' library missing. Run 'pip install cryptography' in terminal.")
class BadgeButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.counter = 0

    def setCounter(self, count):
        self.counter = count
        self.update() # Button ko refresh karega badge dikhane ke liye

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.counter > 0:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            # Badge ka rang aur size
            rect = self.rect()
            badge_size = 18
            badge_rect = QtCore.QRect(rect.right() - badge_size, rect.top(), badge_size, badge_size)
            
            painter.setBrush(QtGui.QColor("#ef4444")) # Red color
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(badge_rect)
            
            # Badge ke andar ka text (number)
            painter.setPen(QtGui.QColor("white"))
            font = painter.font()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(badge_rect, QtCore.Qt.AlignCenter, str(self.counter))
class ReceiverDashboard(QtWidgets.QMainWindow):
    def __init__(self, name="Jaweria Maryam Tariq"):
        super().__init__()
        self.user_name = name
        
        # Paths & Storage
        self.HISTORY_STORAGE = "receive_history_record.json"
        self.LOGS_STORAGE = "forensic_logs.json"  # Yeh line add karein
        self.RECEIVED_DIR = "Received_Forensic_Packages"
        self.existing_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        # --- Hardware Monitoring Setup ---
        self.monitor_timer = QtCore.QTimer()
        self.monitor_timer.timeout.connect(self.detect_new_hardware)
        self.monitor_timer.start(2000) # Har 2 second baad check karega
        
        if not os.path.exists(self.RECEIVED_DIR):
            os.makedirs(self.RECEIVED_DIR)
        
        self.setWindowTitle("Secure Forensic Data Sharing Framework - Receiver")
        self.showMaximized()
        self.setStyleSheet("font-family: 'Segoe UI', sans-serif; background-color: #f1f5f9;")
        
        mainWidget = QtWidgets.QWidget()
        self.setCentralWidget(mainWidget)
        mainLayout = QtWidgets.QVBoxLayout(mainWidget)
        mainLayout.setContentsMargins(0,0,0,0)
        mainLayout.setSpacing(0)
        # ================= TOP RIBBON =================
        ribbon = QtWidgets.QFrame()
        ribbon.setFixedHeight(70)
        ribbon.setStyleSheet("background-color:#0284c7; color:white; border-bottom: 3px solid #0369a1;")
        ribbonLayout = QtWidgets.QHBoxLayout(ribbon)
        
        title = QtWidgets.QLabel("SECURE FORENSIC DATA SHARING (RECEIVER PANEL)")
        title.setStyleSheet("font-size:22px; font-weight:bold; padding-left:20px;")
        ribbonLayout.addWidget(title)
        ribbonLayout.addStretch()
        # --- NOTIFICATION BELL ---
        self.notif_btn = BadgeButton("🔔")
        self.notif_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        self.notif_btn.setFixedSize(40, 40)
        self.notif_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.notif_btn.setStyleSheet("""
            QPushButton { background: #075985; border-radius: 20px; border: 1px solid white; }
            QPushButton::menu-indicator { image: none; } 
        """)
        # Notification Menu setup
        self.notif_menu = QtWidgets.QMenu(self)
        self.notif_menu.setStyleSheet("""
            QMenu { background: white; color: black; width: 300px; font-size: 13px; border: 1px solid #ccc; }
            QMenu::item { padding: 10px; border-bottom: 1px solid #eee; }
            QMenu::item:selected { background: #f0f9ff; color: #0284c7; }
        """)
        self.notif_count = 0
        self.notif_btn.setMenu(self.notif_menu)
        ribbonLayout.addWidget(self.notif_btn)
        
        ribbonLayout.addSpacing(10)
        
        self.user_info = QtWidgets.QLabel(f"👤 Logged in as: {self.user_name}  ")
        self.user_info.setStyleSheet("font-size:14px; font-weight:bold; background:#075985; padding:8px; border-radius:8px;")
        ribbonLayout.addWidget(self.user_info)
        mainLayout.addWidget(ribbon)
        # Paths for notifications
        self.NOTIF_STORAGE = "notifications_record.json"
        self.load_notifications_to_menu() # Load existing ones on startup

        # ================= BODY =================
        bodyLayout = QtWidgets.QHBoxLayout()
        bodyLayout.setContentsMargins(0,0,0,0)
        bodyLayout.setSpacing(0)
        mainLayout.addLayout(bodyLayout, 1)

        # ================= SIDEBAR =================
        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color:#0284c7;")
        sideLayout = QtWidgets.QVBoxLayout(sidebar)
        sideLayout.setContentsMargins(15,20,15,20)
        sideLayout.setSpacing(10)

        def sideButton(text, icon):
            btn = QtWidgets.QPushButton(f"  {text}")
            btn.setIcon(self.style().standardIcon(icon))
            btn.setFixedHeight(45)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton{
                    background:white; border-radius:8px;
                    font-size:14px; font-weight:bold; text-align:left; padding-left:10px;
                }
                QPushButton:hover{ background:#f0f9ff; border: 2px solid #075985; }
            """)
            return btn

        self.btn_home = sideButton("Dashboard Overview", QtWidgets.QStyle.SP_ComputerIcon)
        self.btn_methods = sideButton("Receive Data", QtWidgets.QStyle.SP_DriveNetIcon)
        self.btn_vault = sideButton("Received Vault", QtWidgets.QStyle.SP_DirIcon)
        self.btn_decrypt = sideButton("Decryption Module", QtWidgets.QStyle.SP_BrowserReload)
        self.btn_integrity = sideButton("Integrity Check", QtWidgets.QStyle.SP_DialogApplyButton)
        self.btn_history = sideButton("Receive History Record", QtWidgets.QStyle.SP_FileDialogDetailedView)
        
        for b in [self.btn_home, self.btn_methods, self.btn_vault, self.btn_decrypt, self.btn_integrity, self.btn_history]:
            sideLayout.addWidget(b)

        sideLayout.addStretch()
        
        self.logoutBtn = QtWidgets.QPushButton("Logout")
        self.logoutBtn.setFixedHeight(45)
        self.logoutBtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.logoutBtn.setStyleSheet("background:#ef4444; color:white; border-radius:8px; font-weight:bold; font-size:16px;")
        
        # ... (aapka pehle se majood style yahan rehne den) ...
        self.logoutBtn.clicked.connect(self.do_logout) # YEH LINE ADD KAREIN
        sideLayout.addWidget(self.logoutBtn)

        bodyLayout.addWidget(sidebar)
        self.stack = QtWidgets.QStackedWidget()
        bodyLayout.addWidget(self.stack)


        # ================= MAIN STACK =================
        self.stack = QtWidgets.QStackedWidget()
        bodyLayout.addWidget(self.stack, 1)
        self.setup_ui_pages()

        # Connections
        self.btn_home.clicked.connect(lambda: (self.stack.setCurrentIndex(0), self.update_dashboard_stats()))
        self.btn_methods.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_vault.clicked.connect(lambda: (self.stack.setCurrentIndex(2), self.refresh_vault_table()))
        self.btn_decrypt.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.btn_integrity.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.btn_history.clicked.connect(lambda: (self.stack.setCurrentIndex(5), self.load_history_data()))
        # In __init__ method, add this line:
        self.NOTIF_STORAGE = "notifications_record.json"
        self.load_notifications_to_menu()
        self.waiting_for_hdd = False
    def setup_ui_pages(self):
        group_box_style = "QGroupBox { background: white; border-radius: 15px; border: 1px solid #e2e8f0; font-size: 18px; font-weight: bold; margin-top: 20px; padding: 25px; } QGroupBox::title { subcontrol-origin: margin; left: 20px; padding: 0 5px; color: #0284c7; }"
        input_style = "padding: 12px; font-size: 15px; border: 1px solid #cbd5e1; border-radius: 8px; background: #f8fafc;"

        # --- 0. HOME ---
        pg0 = QtWidgets.QWidget(); l0 = QtWidgets.QVBoxLayout(pg0)
        l0.setContentsMargins(40,30,40,30); l0.setSpacing(25)
        l0.addWidget(QtWidgets.QLabel("<h1 style='color:#0f172a;'>Receiver Analytics</h1>"))
        
        h_layout = QtWidgets.QHBoxLayout(); h_layout.setSpacing(25)
        def create_card(title, color):
            f = QtWidgets.QFrame(); f.setStyleSheet(f"background:white; border-radius:15px; border: 1px solid #e2e8f0; padding:20px;")
            v = QtWidgets.QVBoxLayout(f)
            v.addWidget(QtWidgets.QLabel(f"<b style='color:{color}; font-size:15px;'>{title}</b>"))
            val = QtWidgets.QLabel("0"); val.setStyleSheet("font-size:32px; font-weight:bold;")
            v.addWidget(val); return f, val
        
        c1, self.lbl_stat_rcvd = create_card("Files Received", "#0284c7")
        c2, self.lbl_stat_ports = create_card("Active Ports", "#16a34a")
        c3, self.lbl_stat_int = create_card("Integrity Passed", "#8b5cf6")
        h_layout.addWidget(c1); h_layout.addWidget(c2); h_layout.addWidget(c3)
        l0.addLayout(h_layout)

        # Live aquisition activity (Ab ye auto-stretch hoga)
        activity_panel = QtWidgets.QFrame()
        activity_panel.setStyleSheet("background: rgba(255, 255, 255, 0.9); border-radius: 15px; border: 1px solid #e2e8f0;")
        apl = QtWidgets.QVBoxLayout(activity_panel)
        apl.setContentsMargins(20, 15, 20, 15)
        
        lbl_act = QtWidgets.QLabel("📋 Live Aquisition Activity")
        lbl_act.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        apl.addWidget(lbl_act)
        
        self.activity_list = QtWidgets.QListWidget()
        self.activity_list.setStyleSheet("font-size: 13px; border: none; background: transparent; color: #334155;")
        apl.addWidget(self.activity_list)
        
        l0.addWidget(activity_panel, 1) # '1' ka matlab hai ye bachi hui jagah khud lega
        self.stack.addWidget(pg0)
        
        # --- 1. RECEIVE METHODS ---
        pg1 = QtWidgets.QWidget(); l1 = QtWidgets.QVBoxLayout(pg1); l1.setContentsMargins(40,40,40,40)
        l1.addWidget(QtWidgets.QLabel("<h2>Data Acquisition Protocols</h2>"))
        grid = QtWidgets.QGridLayout(); grid.setSpacing(20)
        m_list = ["USB Import", "HDD Scan", "LAN Listener", "Email Fetch", "Google Drive"]
        for i, m in enumerate(m_list):
            btn = QtWidgets.QPushButton(m)
            btn.setFixedSize(220, 110);
            btn.setStyleSheet("""
                QPushButton { 
                    background: white; 
                    border: 2px solid #059669; 
                    border-radius: 12px; 
                    font-size: 14px; 
                    font-weight: bold; 
                    color: #065f46; 
                }
                QPushButton:hover { 
                    background: #0284c7;    /* Hover karne pe background green ho jayega */
                    color: white;           /* Text white ho jayega */
                    font-size: 16px;        /* Zoom effect/Bold feel */
                }
                QPushButton:pressed {
                    background: #064e3b;
                }
            """)
            btn.clicked.connect(lambda checked, name=m: self.handle_method(name))
            grid.addWidget(btn, i//3, i%3)
        l1.addLayout(grid); l1.addStretch(); self.stack.addWidget(pg1)
        self.lbl_t = QtWidgets.QLabel("Status: Idle"); self.lbl_t.setStyleSheet("font-size:14px; color:#0369a1; font-weight:bold;")
        self.p_bar = QtWidgets.QProgressBar(); self.p_bar.setFixedHeight(25); self.p_bar.setStyleSheet("font-size:12px; font-weight:bold;")
        l1.addWidget(self.lbl_t); l1.addWidget(self.p_bar)
        l1.addStretch(); self.stack.addWidget(pg1)
        # --- 2. VAULT ---
        pg2 = QtWidgets.QWidget(); l2 = QtWidgets.QVBoxLayout(pg2); l2.setContentsMargins(40,30,40,30)
        l2.addWidget(QtWidgets.QLabel("<h2>📂 Received Evidence Vault</h2>"))
        self.tab_vault = QtWidgets.QTableWidget(0, 4)
        self.tab_vault.setHorizontalHeaderLabels(["File Name", "Size (KB)", "Status", "Action"])
        self.tab_vault.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        l2.addWidget(self.tab_vault); self.stack.addWidget(pg2)

        # --- 3. DECRYPT ---
        pg3 = QtWidgets.QWidget(); l3 = QtWidgets.QVBoxLayout(pg3); l3.setContentsMargins(50, 40, 50, 40)
        dec_container = QtWidgets.QGroupBox("Data Decryption Engine"); dec_container.setStyleSheet(group_box_style)
        dl = QtWidgets.QVBoxLayout(dec_container); dl.setSpacing(20); dl.setContentsMargins(30, 40, 30, 40)
        
        # Section 1: File Source
        dl.addWidget(QtWidgets.QLabel("<span style='font-size:16px; font-weight:bold;'>1. Forensic Data Source:</span>"))
        h_file = QtWidgets.QHBoxLayout(); h_file.setSpacing(15)
        self.dec_path = QtWidgets.QLineEdit(); self.dec_path.setStyleSheet(input_style); self.dec_path.setFixedHeight(50)
        self.dec_path.setPlaceholderText("📁 Select encrypted forensic file to decrypt...") 
        btn_br_dec = QtWidgets.QPushButton("📂 Browse File"); btn_br_dec.setFixedSize(160, 50)
        btn_br_dec.setStyleSheet("background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; font-weight:bold; color:#0284c7;")
        btn_br_dec.clicked.connect(self.select_file_for_dec)
        h_file.addWidget(self.dec_path); h_file.addWidget(btn_br_dec); dl.addLayout(h_file)
        
        dl.addSpacing(10)

        # Section 2: Security Token
        dl.addWidget(QtWidgets.QLabel("<span style='font-size:16px; font-weight:bold;'>2. Security Token / Key:</span>"))
        h_key = QtWidgets.QHBoxLayout(); h_key.setSpacing(15)
        self.dec_key = QtWidgets.QLineEdit(); self.dec_key.setStyleSheet(input_style); self.dec_key.setFixedHeight(50)
        self.dec_key.setPlaceholderText("🔑 Enter 32-character AES Key...")
        # Placeholder for symmetry with screenshot
        btn_dummy = QtWidgets.QPushButton("🔐 Verify Key"); btn_dummy.setFixedSize(160, 50)
        btn_dummy.setStyleSheet("background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; font-weight:bold; color:#0284c7;")
        h_key.addWidget(self.dec_key); h_key.addWidget(btn_dummy); dl.addLayout(h_key)
        
        dl.addSpacing(20)

        # Main Button
        btn_run_dec = QtWidgets.QPushButton("🔓 START SECURE DECRYPTION")
        btn_run_dec.setFixedHeight(65); btn_run_dec.setCursor(QtCore.Qt.PointingHandCursor)
        btn_run_dec.setStyleSheet("background:#0284c7; color:white; font-size:18px; font-weight:bold; border-radius:12px;")
        btn_run_dec.clicked.connect(self.run_decryption)
        dl.addWidget(btn_run_dec)
        
        l3.addWidget(dec_container); l3.addStretch(); self.stack.addWidget(pg3)
        # --- 4. INTEGRITY CHECK ---
        pg4 = QtWidgets.QWidget(); l4 = QtWidgets.QVBoxLayout(pg4); l4.setContentsMargins(120, 40, 120, 40)
        int_container = QtWidgets.QGroupBox("🛡️ SHA-256 Integrity Verification"); int_container.setStyleSheet(group_box_style)
        il = QtWidgets.QVBoxLayout(int_container); il.setSpacing(15)
        self.hash_input = QtWidgets.QLineEdit(); self.hash_input.setPlaceholderText("Select file to verify..."); self.hash_input.setStyleSheet(input_style)
        btn_browse_hash = QtWidgets.QPushButton("🔍 Browse Evidence File"); btn_browse_hash.clicked.connect(self.select_file_for_hash)
        btn_browse_hash.setFixedHeight(55) # Size barhaya
        btn_browse_hash.setStyleSheet("""
            QPushButton {
                background: white; 
                color: #0284c7; 
                border: 2px solid #0284c7; 
                border-radius: 10px; 
                font-weight: bold; 
                font-size: 16px; 
            }
            QPushButton:hover { background: #f0f9ff; }
        """)
        btn_browse_hash.clicked.connect(self.select_file_for_hash)
        self.expected_hash = QtWidgets.QLineEdit(); self.expected_hash.setPlaceholderText("Paste Sender's Hash Here..."); self.expected_hash.setStyleSheet(input_style)
        self.hash_display = QtWidgets.QLabel("Status: Awaiting verification..."); self.hash_display.setStyleSheet("background:#1e293b; color:#38bdf8; padding:15px; border-radius:12px;")
        btn_calc = QtWidgets.QPushButton("🚀 VERIFY INTEGRITY"); btn_calc.setFixedHeight(55); btn_calc.setStyleSheet("background:#16a34a; color:white; font-weight:bold; border-radius:10px;")
        btn_calc.setFixedHeight(65) # Size barhaya
        btn_calc.setStyleSheet("""
            QPushButton {
                background: #0284c7; 
                color: white; 
                border: none; 
                font-weight: bold; 
                font-size: 18px; 
                border-radius: 10px;
            }
            QPushButton:hover { background: #0369a1; }
        """)
        btn_calc.clicked.connect(self.run_integrity_check)
        il.addWidget(self.hash_input); il.addWidget(btn_browse_hash); il.addWidget(self.expected_hash); il.addWidget(self.hash_display); il.addWidget(btn_calc)
        l4.addWidget(int_container); l4.addStretch(); self.stack.addWidget(pg4)

        # --- 5. RECEIVE HISTORY RECORD ---
        pg5 = QtWidgets.QWidget(); l5 = QtWidgets.QVBoxLayout(pg5); l5.setContentsMargins(30,30,30,30)
        l5.addWidget(QtWidgets.QLabel("<h2>📜 Receive History Record</h2>"))
        self.tab_hist = QtWidgets.QTableWidget(0, 4)
        self.tab_hist.setHorizontalHeaderLabels(["Timestamp", "Received File", "Method", "Status"])
        self.tab_hist.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        l5.addWidget(self.tab_hist); self.stack.addWidget(pg5)
        self.load_history_data()
        self.update_dashboard_stats()
        self.load_activity_logs() # Yeh line add karein taake login pe purana record show ho

    # ================= LOGIC =================

    def add_to_receive_history(self, file, protocol, status="Success"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # --- actual logic to detect suspicious or failed ---
        final_status = status
        
        # 1. Agar file ka naam khali hai ya processing mein error hai to Failed
        if not file or file == "N/A" or "Error" in file:
            final_status = "Failed"
        
        # 2. Suspicious Logic: Agar file name mein suspicious keywords hon
        suspicious_keywords = ["virus", "malware", "hack", "exploit", "shell", "attack"]
        if any(key in file.lower() for key in suspicious_keywords):
            final_status = "Suspicious"
        
        history_item = {"time": ts, "file": file, "protocol": protocol, "status": final_status}
        
        data = []
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f: 
                    data = json.load(f)
            except: 
                data = []
        
        data.append(history_item)
        with open(self.HISTORY_STORAGE, 'w') as f: 
           json.dump(data, f, indent=4)
           # Add this at the end of add_to_receive_history
        msg = f"File {file} {final_status}"
        self.add_notification(msg, final_status)
    def load_receive_history(self):
        if os.path.exists(self.HISTORY_STORAGE):
            with open(self.HISTORY_STORAGE, "r") as f:
                try:
                    data = json.load(f)
                    # Sabse pehle table ko empty karein taake duplicates nazar na ayein
                    self.tab_hist.setRowCount(0) 
                    
                    for item in data:
                        row = self.tab_hist.rowCount()
                        self.tab_hist.insertRow(row)
                        self.tab_hist.setItem(row,0,QtWidgets.QTableWidgetItem(item["time"]))
                        self.tab_hist.setItem(row,1,QtWidgets.QTableWidgetItem(item["file"]))
                        self.tab_hist.setItem(row,2,QtWidgets.QTableWidgetItem(item["protocol"]))
                        self.tab_hist.setItem(row,3,QtWidgets.QTableWidgetItem(item["status"]))
                except:
                    pass
    def copy_with_progress(self, src, dst):
        """File ko chunks mein copy karke progress dikhayega aur status fix karega"""
        try:
            import time
            total_size = os.path.getsize(src)
            bytes_copied = 0
            buffer_size = 1024 * 64  # 64KB Chunks
            
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                while True:
                    chunk = fsrc.read(buffer_size)
                    if not chunk: 
                        break
                    fdst.write(chunk)
                    bytes_copied += len(chunk)
                    
                    # Progress Update
                    percent = int((bytes_copied / total_size) * 100)
                    
                    # UI Thread-safe updates
                    QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, percent))
                    QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Status: Receiving from HDD... {percent}%"))
                    
                    # Force UI Refresh taake chunks move hote dikhen
                    QtWidgets.QApplication.processEvents()
                    
                    # Choti files ke liye thoda delay taake progress bar jump na kare
                    if total_size < 1024 * 1024 * 10: # 10MB se choti file
                        time.sleep(0.02)

            # --- SUCCESS FINALIZATION ---
            filename = os.path.basename(dst)
            
            # Yahan hum flag reset kar rahe hain taake monitor thread isay "Failed" na kare
            self.waiting_for_hdd = False 
            
            # Status Set karein aur isay lock kar dein
            QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: HDD File Received Successfully ✅"))
            QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 100))
            
            # History aur Dashboard update
            self.add_to_receive_history(filename, "HDD Scan", "Success")
            QtCore.QMetaObject.invokeMethod(self, "refresh_vault_table", QtCore.Qt.QueuedConnection)
            QtCore.QMetaObject.invokeMethod(self, "update_dashboard_stats", QtCore.Qt.QueuedConnection)

        except Exception as e:
            print(f"HDD Copy Error: {e}")
            QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: HDD Transfer Failed ❌"))
    def detect_new_hardware(self):
        """Nayi HDD detect hone par transfer shuru karega"""
        current_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        new_drives = [d for d in current_drives if d not in self.existing_drives]

        # Agar hum wait kar rahe hain aur nayi drive mili hai
        if self.waiting_for_hdd and new_drives:
            target_drive = new_drives[0]
            transfer_folder = os.path.join(target_drive, "Forensic_Transfers")

            if os.path.exists(transfer_folder):
                files = [os.path.join(transfer_folder, f) for f in os.listdir(transfer_folder) if f.endswith(".aes")]
                if files:
                    # Transfer shuru hone se pehle hi flag false kar dein taake loop repeat na ho
                    self.waiting_for_hdd = False 
                    latest_file_path = max(files, key=os.path.getmtime)
                    dst = os.path.join(self.RECEIVED_DIR, os.path.basename(latest_file_path))

                    threading.Thread(target=self.copy_with_progress, args=(latest_file_path, dst), daemon=True).start()
                    self.activity_list.addItem(f"● [HDD] Fetching: {os.path.basename(latest_file_path)}")
                else:
                    self.lbl_t.setText("Status: No .aes files found on drive.")
            else:
                self.lbl_t.setText("Status: 'Forensic_Transfers' folder missing.")
        
        # Drives list ko hamesha update rakhen
        self.existing_drives = current_drives
    def handle_method(self, name):
        try:
            # --- 1. USB aur HDD ka Logic ---
            if name == "USB Import" or name == "HDD Scan":
                # Flag set karein taake monitor function ko pata chale ke ab scan karna hai
                self.waiting_for_hdd = True
                # Purani drives ki list update kar len taake jo pehle se lagi hain wo ignore hon
                self.existing_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
                QtWidgets.QMessageBox.information(self, name, f"Monitoring Active!\n\nPlease plug in your {name}.\nSystem will fetch only the LATEST forensic package.")
                self.lbl_t.setText(f"Status: Waiting for {name} to be plugged...")
                self.p_bar.setValue(0)
                # Check if drive is already plugged in
                current = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
                if any(d not in self.existing_drives for d in current):
                    # Agar drive pehle se detector mein nahi ayi, toh detect_new_hardware handle kar lega
                    pass
                else:
                    self.lbl_t.setText(f"Status: Waiting for {name} to be plugged...")
                new_drives = [d for d in current if d not in self.existing_drives]

                if new_drives:
                    target_drive = new_drives[0]
                    usb_path = os.path.join(target_drive, "Forensic_Transfers")
                    if os.path.exists(usb_path):
                        files_to_copy = [f for f in os.listdir(usb_path) if f.endswith(".aes")]
                        if files_to_copy:
                            for filename in files_to_copy:
                                src_f = os.path.join(usb_path, filename)
                                dest_f = os.path.join(self.RECEIVED_DIR, filename)
                                self.copy_with_progress(src_f, dest_f)
                                self.add_to_receive_history(filename, name, "Success")
                                self.activity_list.addItem(f"● [{name}] Auto-Fetched: {filename}")
                            
                            self.lbl_t.setText(f"Status: {name} Completed Successfully")
                            self.refresh_vault_table()
                            self.update_dashboard_stats()
                            QtWidgets.QMessageBox.information(self, "Success", f"Successfully imported {len(files_to_copy)} files!")
                        else:
                            QtWidgets.QMessageBox.warning(self, "Empty", "No .aes files found in folder.")
                    else:
                        QtWidgets.QMessageBox.warning(self, "Missing", f"Folder 'Forensic_Transfers' not found on {target_drive}")
                else:
                    self.lbl_t.setText(f"Status: Waiting for {name} plug-in...")

            # --- 2. LAN Listener (Ab ye USB ke sath nahi chalega) ---
            elif name == "LAN Listener":
                self.activity_list.addItem(f"● LAN: Starting Listener on Port 5000...")
                self.lbl_stat_ports.setText("1")
                threading.Thread(target=self.start_lan_server, daemon=True).start()
                QtWidgets.QMessageBox.information(self, "LAN Mode", "Listening for incoming files from Sender...")

            # --- handle_method ke andar Google Drive wala block replace karein ---
            elif name == "Google Drive":
                url, ok = QtWidgets.QInputDialog.getText(self, "Google Drive Pull", "Enter Google Drive Share Link:")
                if ok and url:
                    self.lbl_t.setText("Status: Connecting to Google Drive...")
                    self.p_bar.setValue(10)
            # Threading taake UI hang na ho
                    threading.Thread(target=self.download_from_gdrive, args=(url,), daemon=True).start()
            # --- handle_method ke andar Email Fetch wala block ---
            elif name == "Email Fetch":
                # YAHAN APNA ASLI GMAIL AUR APP PASSWORD LIKHEIN
                RECEIVER_EMAIL = "salihakiran2004@gmail.com" 
                RECEIVER_APP_PASS = "qydq jlty imow sfzj" # Gmail se generate kiya hua 16-digit code
    
                self.activity_list.addItem("● Email: Connecting to secure mail server...")
                self.lbl_t.setText("Status: Authenticating...")
                self.p_bar.setValue(5)

                threading.Thread(target=self.fetch_email_attachements, args=(RECEIVER_EMAIL, RECEIVER_APP_PASS), daemon=True).start()
        
        
        except Exception as e:
            self.add_to_receive_history("Error Occurred", name, "Failed")
            self.update_dashboard_stats()
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to execute {name}: {str(e)}")

    def download_web_file(self, url):
        """Modified for Web Pull Progress Bar"""
        filename = url.split('/')[-1]
        save_path = os.path.join(self.RECEIVED_DIR, filename)
        try:
            self.activity_list.addItem(f"● Web: Downloading from {url}...")
            
            def report_hook(block_num, block_size, total_size):
                current = block_num * block_size
                self.update_progress(current, total_size)

            # urllib retrieve supports progress callback via reporthook
            urllib.request.urlretrieve(url, save_path, reporthook=report_hook)
            
            self.p_bar.setValue(100)
            self.lbl_t.setText("Status: Web Download Success!")
            self.add_to_receive_history(filename, "Web Pull", "Success")
            self.update_dashboard_stats()
            QtCore.QMetaObject.invokeMethod(self, "refresh_vault_table", QtCore.Qt.QueuedConnection)
        except Exception as e:
            self.lbl_t.setText("Status: Download Failed")
            self.activity_list.addItem(f"● Web Error: {str(e)}")
    def update_progress(self, current, total):
        """Helper function to update UI progress bar safely"""
        if total > 0:
            percentage = int((current / total) * 100)
            self.p_bar.setValue(percentage)
            self.lbl_t.setText(f"Status: Receiving... {percentage}%")
            # Force UI to update
            QtWidgets.QApplication.processEvents()
    def start_lan_server(self):
        """Final Thread-Safe LAN Logic to prevent crashing"""
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', 5000)) 
            server_socket.listen(1)
            
            # UI updates using Thread-safe method
            QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 0))
            QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: Waiting for Sender..."))

            conn, addr = server_socket.accept()
            conn.settimeout(30.0) # Connection timeout increase kiya

            # --- STEP 1: Handshake ---
            total_size = 0
            try:
                # Sirf size receive karein
                size_data = conn.recv(1024).decode('utf-8').strip()
                if size_data.isdigit():
                    total_size = int(size_data)
                    conn.send(b"ACK_SIZE") # Confirmation signal
            except:
                total_size = 0

            # --- STEP 2: Smooth Binary Transfer ---
            received_name = f"LAN_RECV_{datetime.now().strftime('%H%M%S')}.aes"
            save_path = os.path.join(self.RECEIVED_DIR, received_name)
            
            bytes_received = 0
            with open(save_path, "wb") as f:
                while True:
                    # Buffer size 16KB for stability
                    chunk = conn.recv(16384)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
                    
                    # Update Progress without freezing UI
                    if total_size > 0:
                        percentage = int((bytes_received / total_size) * 100)
                        QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, min(percentage, 99)))
                        QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Status: Receiving... {percentage}%"))

            conn.close()

            # --- STEP 3: Finalization ---
            conn.close()

            if bytes_received > 0 and (total_size == 0 or bytes_received >= total_size):
                QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 100))
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: Transfer Successfully ✅"))

                self.add_to_receive_history(received_name, "LAN", "Success")

            else:
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: Transfer Failed ❌"))
        except Exception as e:
            print(f"LAN Error: {e}")
        finally:
            if server_socket:
                server_socket.close()
    def fetch_email_attachements(self, email_user, email_pass):
        """Fetches email and shows progress in bits/chunks"""
        IMAP_SERVER = "imap.gmail.com"
        try:
            # 1. Login with App Password
            mail = imaplib.IMAP4_SSL(IMAP_SERVER)
            mail.login(email_user, email_pass)
            mail.select("inbox")            
            
            # 2. Latest Email Search
            status, messages = mail.search(None, 'ALL')
            if status != "OK" or not messages[0]:
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: No Mail Found"))
                return

            latest_id = messages[0].split()[-1] 
            res, msg_data = mail.fetch(latest_id, "(RFC822)")
            
            found_file = False
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart': continue
                        if part.get('Content-Disposition') is None: continue

                        filename = part.get_filename()
                        if filename and filename.endswith(".aes"):
                            # Payload decode
                            payload = part.get_payload(decode=True)
                            total_bits = len(payload)
                            
                            chunk_size = max(1, total_bits // 10)
                            filepath = os.path.join(self.RECEIVED_DIR, filename)
                            
                            with open(filepath, "wb") as f:
                                for i in range(0, total_bits, chunk_size):
                                    chunk = payload[i:i + chunk_size]
                                    f.write(chunk)
                                    
                                    progress = int(((i + len(chunk)) / total_bits) * 100)
                                    if progress > 100: progress = 100
                                    
                                    # Progress Update
                                    QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, progress))
                                    QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Status: Receiving Bits... {progress}%"))
                                    
                                    import time
                                    time.sleep(0.1)

                            self.add_to_receive_history(filename, "Email Fetch", "Success")
                            found_file = True

            mail.close()
            mail.logout()

            # --- YAHAN FIX HAI ---
            if found_file:
                # Agar file mil gayi toh Success message
                QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 100))
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: Data Successfully Received ✅"))
                QtCore.QMetaObject.invokeMethod(self, "refresh_vault_table", QtCore.Qt.QueuedConnection)
                QtCore.QMetaObject.invokeMethod(self, "update_dashboard_stats", QtCore.Qt.QueuedConnection)
            else:
                # Agar login ho gaya par file nahi mili
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: No Forensic Package Found"))

        except Exception as e:
            print(f"Error: {e}")

    # ✅ CHECK: agar file already receive ho chuki hai toh error show na karo
            if 'found_file' in locals() and found_file:
                QtCore.QMetaObject.invokeMethod(
                    self.lbl_t,
                    "setText",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, "Status: Data Successfully Received ✅")
                )
                QtCore.QMetaObject.invokeMethod(
                    self.p_bar,
                    "setValue",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(int, 100)
                )
            else:
                QtCore.QMetaObject.invokeMethod(
                    self.lbl_t,
                    "setText",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, "Status: Error Occurred ❌")
           )
    def select_file_for_dec(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select AES File", self.RECEIVED_DIR)
        if f: self.dec_path.setText(f) 
    def select_file_for_hash(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File", self.RECEIVED_DIR)
        if f: self.hash_input.setText(f)
    def run_decryption(self):
        path = self.dec_path.text().strip()
        key = self.dec_key.text().strip()
        
        # --- POPUP VALIDATION LOGIC ---
        if not path and not key:
            QtWidgets.QMessageBox.warning(self, "Attention", "⚠️ Please select a file and enter the key first!")
            return
        elif not path:
            QtWidgets.QMessageBox.warning(self, "File Missing", "⚠️ Please browse and select a file to decrypt.")
            return
        elif not key:
            QtWidgets.QMessageBox.warning(self, "Key Missing", "⚠️ Please provide the decryption key.")
            return
        elif len(key) != 32:
            QtWidgets.QMessageBox.warning(self, "Invalid Key", f"⚠️ AES Key must be 32 characters.\n(Current length: {len(key)})")
            return
        
        # --- ACTUAL DECRYPTION PROCESS ---
        try:
                with open(path, 'rb') as f: data = f.read()
                iv, encrypted = data[:16], data[16:]
                cipher = Cipher(algorithms.AES(key.encode()), modes.CBC(iv), backend=default_backend())
                decryptor = cipher.decryptor()
                padded = decryptor.update(encrypted) + decryptor.finalize()
                unpadder = padding.PKCS7(128).unpadder()
                original = unpadder.update(padded) + unpadder.finalize()
            
                out = os.path.join(self.RECEIVED_DIR, "DECRYPTED_" + os.path.basename(path).replace(".aes",""))
                with open(out, 'wb') as f: f.write(original)
            
                self.refresh_vault_table()
                QtWidgets.QMessageBox.information(self, "Success", "✅ Decryption successful! File saved in vault")
                self.add_notification(f"Decryption Success: {os.path.basename(path)}", "Success")
        except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Decryption failed: {str(e)}")
                self.add_notification(f"Decryption Failed!", "Failed")
    
    def run_integrity_check(self):
        path = self.hash_input.text().strip()
        expected = self.expected_hash.text().strip().lower()

        # Check if hash is entered
        if not expected:
            self.hash_display.setText("⚠️ Please enter sender's hash first!")
            self.hash_display.setStyleSheet("background:#78350f; color:#fbbf24; padding:15px; border-radius:12px; font-weight:bold;")
            return

        if os.path.exists(path):
            try:
                sha = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""): 
                        sha.update(chunk)
                current = sha.hexdigest().lower()
                
                # Matched Case
                if current == expected:
                    self.hash_display.setText("✅ INTEGRITY MATCHED!")
                    self.hash_display.setStyleSheet("background:#14532d; color:#4ade80; padding:15px; border-radius:12px; font-weight:bold;")
                    self.log_activity(f"Integrity PASSED: {os.path.basename(path)}")
                # Mismatch Case
                else:
                    self.hash_display.setText("❌ MISMATCH!")
                    self.hash_display.setStyleSheet("background:#7f1d1d; color:#f87171; padding:15px; border-radius:12px; font-weight:bold;")
                    self.log_activity(f"Integrity FAILED: {os.path.basename(path)}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Could not calculate hash: {str(e)}")
        else:
            self.hash_display.setText("⚠️ Please select a valid file first.")
            self.hash_display.setStyleSheet("background:#1e293b; color:#fbbf24; padding:15px; border-radius:12px;")
    def load_history_data(self):
        if os.path.exists(self.HISTORY_STORAGE):
            # Table ko sabse pehle khali karein taake duplicates na banen
            self.tab_hist.setRowCount(0)
            
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        row = self.tab_hist.rowCount()
                        self.tab_hist.insertRow(row)
                        
                        self.tab_hist.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('time', 'N/A')))
                        self.tab_hist.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('file', 'N/A')))
                        self.tab_hist.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('protocol', 'N/A')))
                
                        # Status Color Logic
                        status_text = item.get('status', 'Success')
                        status_item = QtWidgets.QTableWidgetItem(status_text)
                        
                        if status_text == "Success":
                            status_item.setForeground(QtGui.QColor("#16a34a"))
                        elif status_text == "Suspicious":
                            status_item.setForeground(QtGui.QColor("#7f1d1d"))
                            status_item.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))
                        elif status_text == "Failed":
                            status_item.setForeground(QtGui.QColor("#ef4444"))
                        
                        self.tab_hist.setItem(row, 3, status_item)
            except Exception as e:
                print(f"History Load Error: {e}")


    def download_file(self, filename):
        src_path = os.path.join(self.RECEIVED_DIR, filename)
        
        if filename.endswith(".aes"):
            QtWidgets.QMessageBox.warning(self, "Forensic Alert", "⚠️ Please decrypt the file first!")
            return

        # History se asli method dhoondna
        method_used = "Direct"
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    data = json.load(f)
                    for item in data:
                        h_file = item.get('file', '')
                        if h_file == filename or h_file == filename + ".aes" or filename in h_file:
                            method_used = item.get('protocol', 'Manual')
                            break
            except: pass

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Download Forensic Evidence", filename)
        
        if save_path:
            try:
                import shutil
                shutil.copy2(src_path, save_path)
                
                lower_path = save_path.lower()
                is_authorized = True
                
                # --- Forensic Check Logic ---
                if "email" in method_used.lower():
                    if "emaildata" not in lower_path:
                        is_authorized = False
                elif "lan" in method_used.lower():
                    if "shareddata" not in lower_path:
                        is_authorized = False
                # USB/HDD/HDD Monitor ke liye is_authorized humesha True rahega

                if is_authorized:
                    title = "Download Successful"
                    msg = f"<span style='color: #0284c7; font-weight: bold;'>File downloaded through {method_used}</span>"
                    status_log = f"Download ({method_used})"
                else:
                    title = "Security Warning"
                    msg = f"<span style='color: #ef4444; font-weight: bold;'>UNAUTHORIZED LOCATION: File from {method_used} saved outside secure folder!</span>"
                    status_log = f"Suspicious Download ({method_used})"

                # Popup Notification
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setWindowTitle(title)
                msg_box.setText(msg)
                msg_box.setInformativeText(f"Target: {save_path}")
                msg_box.exec_()

                # History update (Taake button green ho jaye)
                self.add_to_receive_history(filename, status_log, "Success" if is_authorized else "Warning")
                self.refresh_vault_table()

            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Download failed: {str(e)}")
    def refresh_vault_table(self):
        self.tab_vault.setColumnCount(5)
        self.tab_vault.setHorizontalHeaderLabels(["File Name", "Size (KB)", "Status", "Received Via", "Action"])
        self.tab_vault.setRowCount(0)
        
        method_map = {}
        downloaded_list = []
        
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    hist = json.load(f)
                    for item in hist:
                        fname = item.get('file', '')
                        proto = item.get('protocol', 'Internal')
                        
                        # Cleaning method name
                        if "Download" in proto:
                            if "(" in proto: proto = proto.split("(")[1].replace(")", "")
                            downloaded_list.append(fname)
                            downloaded_list.append(fname.replace("DECRYPTED_", ""))
                        
                        method_map[fname] = proto
                        method_map[fname.replace(".aes", "")] = proto
            except: pass

        if os.path.exists(self.RECEIVED_DIR):
            for filename in os.listdir(self.RECEIVED_DIR):
                row = self.tab_vault.rowCount(); self.tab_vault.insertRow(row)
                size = os.path.getsize(os.path.join(self.RECEIVED_DIR, filename)) // 1024
                
                self.tab_vault.setItem(row, 0, QtWidgets.QTableWidgetItem(filename))
                self.tab_vault.setItem(row, 1, QtWidgets.QTableWidgetItem(str(size)))
                self.tab_vault.setItem(row, 2, QtWidgets.QTableWidgetItem("Encrypted" if filename.endswith(".aes") else "Original"))
                
                # Column 3: Received Via
                m_name = method_map.get(filename, "Direct")
                self.tab_vault.setItem(row, 3, QtWidgets.QTableWidgetItem(m_name))

                # Column 4: Download Button
                is_done = filename in downloaded_list
                btn_text = "Downloaded ✅" if is_done else "Download"
                btn = QtWidgets.QPushButton(btn_text)
                
                # FIX: PyQt5 Cursor Error
                btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
                
                if is_done:
                    btn.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; border-radius: 5px; padding: 5px;")
                else:
                    btn.setStyleSheet("""
                        QPushButton { background-color: #f1f5f9; color: black; border: 1px solid #cbd5e1; font-weight: bold; border-radius: 5px; padding: 5px; }
                        QPushButton:hover { background-color: #0284c7; color: white; }
                    """)
                    btn.clicked.connect(lambda ch, f=filename: self.download_file(f))
                
                self.tab_vault.setCellWidget(row, 4, btn)
    def update_dashboard_stats(self):
        files_received = 0
        integrity_passed = 0

        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, "r") as f:
                    data = json.load(f)
                    files_received = len(data)
                    # Sirf wo count karein jo 'Success' hain
                    integrity_passed = sum(1 for item in data if item.get("status") == "Success")
            except Exception as e:
                print(f"Error loading stats: {e}")

        # UI Labels ko update karna (Ye lines loop/try se bahar honi chahiye)
        self.lbl_stat_rcvd.setText(str(files_received))
        self.lbl_stat_int.setText(str(integrity_passed))
        # Active ports logic (optional: agar koi server chal raha ho)
        # self.lbl_stat_ports.setText("0")
    # ================== LOGOUT FUNCTIONALITY ==================
    def do_logout(self):
        """Dashboard band karega aur landing page (app.py) khol dega"""
        self.close() # Dashboard window band
        try:
            # Landing page ko import karke show karna
            from app import MainAppWindow 
            self.landing = MainAppWindow()
            self.landing.showMaximized()
        except Exception as e:
            print(f"Landing page load karne mein masla aya: {e}")
    def log_activity(self, message):
        """Activity list aur JSON history mein record save karne ka sahi tariqa"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"● [{timestamp}] {message}"

        # UI Update (Thread-safe tariqa)
        self.activity_list.addItem(log_entry)
        self.activity_list.scrollToBottom()

        # JSON mein record save karna
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file": message,
            "protocol": "Integrity Check",
            "status": "Info"
        }

        data = []
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, "r") as f:
                    data = json.load(f)
            except:
                data = []

        data.append(record)
        with open(self.HISTORY_STORAGE, "w") as f:
            json.dump(data, f, indent=4)

    # 2. Transfer History Load karna (Destination column ke saath)
        if os.path.exists(self.HISTORY_STORAGE):
            with open(self.HISTORY_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        row = self.tab_hist.rowCount()
                        self.tab_hist.insertRow(row)
                        self.tab_hist.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('time', '')))
                        self.tab_hist.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('file', '')))
                        self.tab_hist.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('protocol', '')))
                        # Column 3 mein Destination load ho rahi hai
                        self.tab_hist.setItem(row, 3, QtWidgets.QTableWidgetItem(item.get('destination', 'N/A')))
                        # Column 4 mein Status load ho raha hai
                        self.tab_hist.setItem(row, 4, QtWidgets.QTableWidgetItem(item.get('status', '')))
                except Exception as e:
                    print(f"Error loading history: {e}")
    # 3. Forensic Logs Load karna
        if os.path.exists(self.LOGS_STORAGE):
            with open(self.LOGS_STORAGE, 'r') as f:
                try:
                    data = json.load(f)
                    for item in data:
                        row = self.log_table.rowCount()
                        self.log_table.insertRow(row)
                        self.log_table.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('event_id', '')))
                        self.log_table.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('activity', '')))
                        self.log_table.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('level', '')))
                        
                        # Home ki activity list mein add karein
                        self.activity_list.addItem(f"● {item.get('activity', 'Activity Recorded')}")
                except Exception as e:
                    print(f"Error loading logs: {e}")
                    self.update_dashboard_stats()
    def load_activity_logs(self):
        """History storage se purana record utha kar Live Activity list mein load karna"""
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    data = json.load(f)
                    self.activity_list.clear() # Pehle se majood list saaf karein
                    # Sirf aakhri 20-30 records dikhane ke liye (optional) ya saare
                    for item in data:
                        time = item.get('time', '00:00:00')
                        msg = item.get('file', '') # log_activity mein hum 'file' key mein message save kar rahe hain
                        self.activity_list.addItem(f"● [{time}] {msg}")
                    self.activity_list.scrollToBottom()
            except Exception as e:
                print(f"Activity load karne mein error: {e}")
    def add_notification(self, message, status="Success"):
        """Naya notification add aur save karne ke liye"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        icon = "✅" if status == "Success" else "❌"
        notif_entry = {"time": timestamp, "msg": f"{icon} {message}", "status": status}

        # 1. Load existing
        notifs = []
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f: notifs = json.load(f)
            except: notifs = []

        # 2. Add new to start of list (Top pe dikhane ke liye)
        notifs.insert(0, notif_entry)
        
        # 3. Save back
        with open(self.NOTIF_STORAGE, 'w') as f:
            json.dump(notifs[:20], f, indent=4) # Sirf top 20 rakhen taake heavy na ho
        # Nayi Logic: Counter barhaein
        self.notif_count += 1
        self.notif_btn.setCounter(self.notif_count) 
        
        # 4. Refresh UI Menu
        self.load_notifications_to_menu()
        
        # 5. Optional: Show a quick popup message (Toast)
        # QtCore.Qt.Point ki jagah QtCore.QPoint istemal karein
        QtWidgets.QToolTip.showText(self.notif_btn.mapToGlobal(QtCore.QPoint(0,0)), f"New Notification: {message}")
    def load_notifications_to_menu(self):
        """Saved notifications ko Bell icon ke menu mein load karna"""
        self.notif_menu.clear()
        # Jab user bell icon par click karega
        self.notif_count = 0 
        self.notif_btn.setCounter(0)
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f:
                    data = json.load(f)
                    if not data:
                        self.notif_menu.addAction("No new notifications")
                    for item in data:
                        action = self.notif_menu.addAction(f"[{item['time'][-8:]}] {item['msg']}")
                        if item['status'] == "Failed":
                            action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxCritical))
            except:
                self.notif_menu.addAction("Error loading notifications")
        else:
            self.notif_menu.addAction("No notifications yet")
    # --- Yeh Naya Function apne code mein add karein ---
    def download_from_gdrive(self, url):
        try:
            import gdown
            import re
            import time  # Time import karein delay ke liye

            # 1. Google Drive ID nikalne ka logic
            file_id = ""
            if 'id=' in url:
                file_id = url.split('id=')[-1]
            elif '/d/' in url:
                file_id = url.split('/d/')[1].split('/')[0]
            
            if not file_id:
                raise Exception("Invalid Google Drive Link")

            # UI Initial Update
            QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: Connecting to G-Drive..."))
            QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 20))

            # 2. Destination path
            dest_name = f"GDrive_{random.randint(1000,9999)}.aes"
            dest_path = os.path.join(self.RECEIVED_DIR, dest_name)

            # 3. Download Process
            # 'fuzzy=True' helps with various link formats
            output = gdown.download(id=file_id, output=dest_path, quiet=False, fuzzy=True)

            if output and os.path.exists(output):
                actual_filename = os.path.basename(output)
                
                # --- SUCCESS LOCK LOGIC ---
                # Hum value set karne ke baad thoda rukenge taake user dekh sake
                QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 100))
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: G-Drive Download Success ✅"))
                
                # Records update
                self.add_to_receive_history(actual_filename, "Google Drive", "Success")
                
                # UI Refresh
                QtCore.QMetaObject.invokeMethod(self, "refresh_vault_table", QtCore.Qt.QueuedConnection)
                QtCore.QMetaObject.invokeMethod(self, "update_dashboard_stats", QtCore.Qt.QueuedConnection)
                
                # Optional: Ek alert box dikha dein taake process wahin ruk jaye
                # self.show_notif("G-Drive File Received!", "Success")

            else:
                # Agar output hi nahi aya
                raise Exception("Empty Output")

        except Exception as e:
            # Sirf tabhi fail dikhaye agar sach mein error ho
            error_msg = str(e)
            print(f"G-Drive Error: {error_msg}")
            
            # Agar file exist karti hai to matlab download ho chuki hai, gdown ne shayad error return kiya ho be-wajah
            if 'dest_path' in locals() and os.path.exists(dest_path):
                QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 100))
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, "Status: G-Drive Download Success ✅"))
            else:
                QtCore.QMetaObject.invokeMethod(self.lbl_t, "setText", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Status: G-Drive Failed ❌"))
                QtCore.QMetaObject.invokeMethod(self.p_bar, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 0))
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ReceiverDashboard()
    window.show()
    sys.exit(app.exec_())