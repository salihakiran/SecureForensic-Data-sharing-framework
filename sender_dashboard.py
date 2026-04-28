from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
import random
import string
import shutil
import socket
import urllib.request
import smtplib
import json
import threading
import http
import sqlite3
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive as PDrive

# --- UPDATED IMPORTS TO PREVENT RESOLUTION ERRORS ---
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from  cryptography.hazmat.backends import default_backend
except ImportError:
    print("Error: 'cryptography' library missing. Run 'pip install cryptography' in terminal.")

class SenderDashboard(QtWidgets.QMainWindow):
    # Signals define karein
    upload_finished = QtCore.pyqtSignal(str, str) # title, message
    update_progress = QtCore.pyqtSignal(int, str) # (value, status_text)
    show_gdrive_link = QtCore.pyqtSignal(str)
    def __init__(self, name="Jaweria Maryam Tariq"):
        super().__init__()
        self.user_name = name
        
        # Files names for storage
        self.FILES_STORAGE = "my_files.json"
        self.HISTORY_STORAGE = "transfer_history.json"
        self.LOGS_STORAGE = "forensic_logs.json"
        self.NOTIFICATIONS_STORAGE = "notifications.json"
        self.unread_count = 0

        self.ACTIVITY_FILE = "sender_activity_log.txt"
        self.load_activities()
        
        
        # --- EMAIL SETTINGS ---
        self.SENDER_EMAIL = "furqant972@gmail.com" 
        self.SENDER_PASSWORD = "ggyd lqua sohh tuxo" 
        
        self.setWindowTitle("Secure Forensic Data Sharing Framework")
        self.showMaximized()
        
        
        self.existing_drives = self.get_current_drives()
        self.selected_file_path = ""
        
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
        
        title = QtWidgets.QLabel("SECURE FORENSIC DATA SHARING(SENDER PANEL)")
        title.setStyleSheet("font-size:22px; font-weight:bold; padding-left:20px;")
        ribbonLayout.addWidget(title)
        ribbonLayout.addStretch()


        # --- IMPROVED NOTIFICATION SYSTEM ---
        self.notif_container = QtWidgets.QWidget()
        self.notif_container.setFixedSize(60, 50)
        self.notif_container.setStyleSheet("background: transparent;")
        notif_layout = QtWidgets.QVBoxLayout(self.notif_container)

        # Main Bell Button
        self.notif_btn = QtWidgets.QPushButton("🔔")
        self.notif_btn.setFixedSize(45, 45)
        self.notif_btn.setCursor(QtCore.Qt.PointingHandCursor)
        # Border aur dropdown arrow hatane ke liye 'border:none' aur 'QPushButton::menu-indicator' use kiya
        self.notif_btn.setStyleSheet("""
            QPushButton { 
                background: transparent; border: none; font-size: 28px; color: white; 
            }
            QPushButton::menu-indicator { image: none; } 
            QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 22px; }
        """)

        # Red Badge (The Number Circle)
        self.notif_badge = QtWidgets.QLabel("0", self.notif_btn)
        self.notif_badge.setFixedSize(20, 20)
        self.notif_badge.move(25, 2) # Position adjust karne ke liye
        self.notif_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.notif_badge.setStyleSheet("""
            background-color: #ef4444; color: white; border-radius: 10px; 
            font-size: 11px; font-weight: bold; border: 1px solid white;
        """)
        self.notif_badge.hide() # Shuru mein hide rahega
        self.unread_count = 0

        # Dropdown Menu Formatting
        self.notif_menu = QtWidgets.QMenu(self)
        self.notif_menu.aboutToShow.connect(self.mark_as_read) # Menu khulne pe badge hat jayega
        self.notif_menu.setStyleSheet("""
            QMenu { background: white; border: 1px solid #e2e8f0; width: 280px; border-radius: 8px; }
            QMenu::item { padding: 12px; border-bottom: 1px solid #f1f5f9; color: #333; }
            QMenu::item:selected { background: #f0f9ff; }
        """)
        self.notif_btn.setMenu(self.notif_menu)
        
        ribbonLayout.addWidget(self.notif_btn)
        

        self.user_info = QtWidgets.QLabel(f"👤 Logged in as: {self.user_name}  ")
        self.user_info.setStyleSheet("font-size:14px; font-weight:bold; background:#075985; padding:8px; border-radius:8px;")
        ribbonLayout.addWidget(self.user_info)
        
        mainLayout.addWidget(ribbon)

        
    

        # ================= BODY =================
        bodyLayout = QtWidgets.QHBoxLayout()
        bodyLayout.setContentsMargins(0,0,0,0)
        bodyLayout.setSpacing(0)
        mainLayout.addLayout(bodyLayout)

        # ================= SIDEBAR =================
        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #0284c7; /* Top bar wala Blue color */
                border: none;
            }
        """)
        sideLayout = QtWidgets.QVBoxLayout(sidebar)

        sideLayout.setContentsMargins(15, 20, 15, 20) # Top/Bottom margins manage karein
        sideLayout.setSpacing(8)

        

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

        self.btn_home = sideButton("Home", QtWidgets.QStyle.SP_ComputerIcon)
        self.btn_upload = sideButton("Upload & Encrypt", QtWidgets.QStyle.SP_ArrowUp)
        self.btn_transfer = sideButton("Transfer Data", QtWidgets.QStyle.SP_DriveNetIcon)
        self.btn_files = sideButton("My Files", QtWidgets.QStyle.SP_DirIcon)
        self.btn_history = sideButton("Transfer History", QtWidgets.QStyle.SP_FileDialogDetailedView)
        self.btn_doc = sideButton("Case Documentation", QtWidgets.QStyle.SP_FileIcon)
        self.btn_logs = sideButton("Forensic Logs", QtWidgets.QStyle.SP_MessageBoxInformation)
        self.btn_integrity = sideButton("Integrity Check", QtWidgets.QStyle.SP_DialogApplyButton)
        for b in [self.btn_home, self.btn_upload, self.btn_transfer, self.btn_files, self.btn_history, self.btn_logs, self.btn_integrity, self.btn_doc]:
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

        self.setup_ui_pages()
        self.load_stored_data()

        self.btn_home.clicked.connect(self.go_home)                          # Index 0
        self.btn_upload.clicked.connect(lambda: self.stack.setCurrentIndex(1)) # Index 1
        self.btn_transfer.clicked.connect(lambda: self.stack.setCurrentIndex(2)) # Index 2
        self.btn_files.clicked.connect(lambda: self.stack.setCurrentIndex(3))  # Index 3
        self.btn_logs.clicked.connect(lambda: self.stack.setCurrentIndex(4))    # Forensic Logs (4)
        self.btn_integrity.clicked.connect(lambda: self.stack.setCurrentIndex(5)) # Integrity Check (5)
        self.btn_history.clicked.connect(lambda: self.stack.setCurrentIndex(6)) # Transfer History (6)
        self.btn_doc.clicked.connect(self.show_case_form)
        self.upload_finished.connect(self.show_message_box)
        # __init__ ke andar ye add karein:
        self.update_progress.connect(self.handle_ui_progress)
        self.show_gdrive_link.connect(self.show_gdrive_success)
    def show_message_box(self, title, message):
        QtWidgets.QMessageBox.information(self, title, message)
    def log_to_ws_db(self, action, method, file_name, file_path):
        try:
            import sqlite3
            from datetime import datetime
            # WS wala hi database path use karein
            db_path = r"C:\ProgramData\SecureForensic\forensic.db"
            conn = sqlite3.connect(db_path, timeout=10)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO logs (username, role, action, method, file_name, file_path, time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.user_name, "User", action, method, file_name, file_path, 
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"WS Logging Error: {e}")

    def save_activity(self, text):
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{ts} - {text}"
        if hasattr(self, 'activity_list'):
            self.activity_list.addItem(entry)
        try:
            # self.ACTIVITY_FILE ko __init__ mein define lazmi karein
            with open(self.ACTIVITY_FILE, "a") as f:
                f.write(entry + "\n")
        except:
            pass
    
    
        

    def load_activities(self):
        if hasattr(self, 'ACTIVITY_FILE') and os.path.exists(self.ACTIVITY_FILE):
            try:
                with open(self.ACTIVITY_FILE, "r") as f:
                    lines = f.readlines()
                    if hasattr(self, 'activity_list'):
                        for line in lines[-20:]:
                            self.activity_list.addItem(line.strip())
            except:
                pass
        
    
    def setup_ui_pages(self):
        # --- 1. HOME (Height Adjusted for No Scroll) ---
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, "background.jpg").replace("\\", "/")

        pg1 = QtWidgets.QWidget()
        pg1.setObjectName("HomePage")
        pg1.setStyleSheet(f"#HomePage {{ border-image: url('{image_path}') 0 0 0 0 stretch stretch; }}")
        
        l1 = QtWidgets.QVBoxLayout(pg1)
        l1.setContentsMargins(30, 20, 30, 20) # Margins thore kam kiye
        l1.setSpacing(15) 

        header = QtWidgets.QLabel("Forensic Dashboard Overview")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #0284c7; background: transparent;")
        l1.addWidget(header)

        # Cards Layout
        h_layout = QtWidgets.QHBoxLayout()
        h_layout.setSpacing(12)

        # --- Custom Card Function (Square Box Style like Pic 2) ---
        # --- Home Card Function (No-Shaking Zoom) ---
        def home_card(title, title_color="#0284c7"):
            class HoverFrame(QtWidgets.QFrame):
                def enterEvent(self, event):
                    # Layout ko hilaaye baghair highlight karne ka tareeka:
                    # Hum size change nahi karenge, sirf border aur shadow se "Bara" dikhayenge
                    
                    # Shadow ko mazeed gehra (dark) kar dein taake lage card upar uth gaya hai
                    sh = QtWidgets.QGraphicsDropShadowEffect()
                    sh.setBlurRadius(30)
                    sh.setOffset(0, 8)
                    sh.setColor(QtGui.QColor(0, 0, 0, 60))
                    self.setGraphicsEffect(sh)
                    super().enterEvent(event)

                def leaveEvent(self, event):
                    # Wapis normal state
                    self.setStyleSheet(f"""
                        background-color: rgba(255, 255, 255, 0.95); 
                        border-radius: 12px; 
                        border: 2px solid #0284c7;
                    """)
                    sh = QtWidgets.QGraphicsDropShadowEffect()
                    sh.setBlurRadius(15); sh.setOffset(0, 4); sh.setColor(QtGui.QColor(0,0,0,35))
                    self.setGraphicsEffect(sh)
                    super().leaveEvent(event)

            f = HoverFrame()
            f.setFixedSize(165, 145) # Size ko "static" (pakka) kar diya taake screen na hile
            f.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(255, 255, 255, 0.95); 
                    border-radius: 12px; 
                    border: 2px solid #0284c7;
                }}
            """)
            
            # Default Shadow
            shadow = QtWidgets.QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15); shadow.setOffset(0, 4); shadow.setColor(QtGui.QColor(0,0,0,35))
            f.setGraphicsEffect(shadow)
            
            v = QtWidgets.QVBoxLayout(f)
            v.setContentsMargins(10, 15, 10, 15)
            
            lbl_title = QtWidgets.QLabel(title.upper())
            lbl_title.setAlignment(QtCore.Qt.AlignCenter)
            lbl_title.setWordWrap(True)
            lbl_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {title_color}; border: none; background: transparent;")
            
            lbl_value = QtWidgets.QLabel("0")
            lbl_value.setAlignment(QtCore.Qt.AlignCenter)
            lbl_value.setStyleSheet("font-size: 36px; font-weight: bold; color: #000000; border: none; background: transparent;")
            
            v.addWidget(lbl_title)
            v.addWidget(lbl_value)
            return f, lbl_value
        
        card_files, self.lbl_stat_files = home_card("Files Prepared", "#0284c7")
        card_trans, self.lbl_stat_transfers = home_card("Total Transfers", "#475569")
        card_success, self.lbl_stat_success = home_card("Success Rate", "#8b5cf6")
        card_susp, self.lbl_stat_suspicious = home_card("Suspicious", "#dc2626")
        card_fail, self.lbl_stat_failed = home_card("Failed", "#f97316")
        
        for c in [card_files, card_trans, card_success, card_susp, card_fail]:
            h_layout.addWidget(c)

            # Cards ko Layout mein add karein aur CENTER align karein
        h_layout = QtWidgets.QHBoxLayout()
        h_layout.setSpacing(20)
        h_layout.setAlignment(QtCore.Qt.AlignCenter) # Saare cards screen ke beech mein rahenge

        h_layout.addWidget(card_files)
        h_layout.addWidget(card_trans)
        h_layout.addWidget(card_success)
        h_layout.addWidget(card_susp)
        h_layout.addWidget(card_fail)
        
        l1.addLayout(h_layout)
        
    

        # Recent Activity Panel (Ab ye auto-stretch hoga)
        activity_panel = QtWidgets.QFrame()
        activity_panel.setStyleSheet("background: rgba(255, 255, 255, 0.9); border-radius: 15px; border: 1px solid #e2e8f0;")
        apl = QtWidgets.QVBoxLayout(activity_panel)
        apl.setContentsMargins(20, 15, 20, 15)
        
        lbl_act = QtWidgets.QLabel("📋 Recent Forensic Activity Logs")
        lbl_act.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        apl.addWidget(lbl_act)
        
        self.activity_list = QtWidgets.QListWidget()
        self.activity_list.setStyleSheet("font-size: 13px; border: none; background: transparent; color: #334155;")
        apl.addWidget(self.activity_list)
        
        l1.addWidget(activity_panel, 1) # '1' ka matlab hai ye bachi hui jagah khud lega
        self.stack.addWidget(pg1)
        # --- 2. UPLOAD & ENCRYPT ---
        # --- PAGE 2: UPLOAD & ENCRYPT ---
        pg2 = QtWidgets.QWidget(); l2 = QtWidgets.QVBoxLayout(pg2)
        l2.setContentsMargins(60, 30, 60, 30)
        
        box = QtWidgets.QGroupBox("Data Encryption Engine")
        box.setStyleSheet("font-size:18px; font-weight:bold; color:#0369a1; padding:20px; border:2px solid #e2e8f0; border-radius:12px; background:white;")
        bl = QtWidgets.QVBoxLayout(box); bl.setSpacing(15)
        
        # 1. Forensic Data Source Box
        self.in_path = QtWidgets.QLineEdit() 
        self.in_path.setFixedHeight(45)
        self.in_path.setStyleSheet("font-size:14px; padding:5px; border-radius:6px; border:1px solid #cbd5e1; background:white;")
        # Placeholder add kiya:
        self.in_path.setPlaceholderText("📁 Select forensic file to encrypt...") 
        
        btn_br = QtWidgets.QPushButton("📁 Browse File")
        btn_br.setFixedSize(180, 45)
        btn_br.setStyleSheet("font-weight:bold; font-size:13px; border-radius:6px; background:#f1f5f9; border:1px solid #cbd5e1; padding: 5px;")
        btn_br.clicked.connect(self.do_browse)
        
        # 2. Security Token / Key Box
        self.in_key = QtWidgets.QLineEdit()
        self.in_key.setFixedHeight(45)
        self.in_key.setStyleSheet("font-size:14px; padding:5px; border-radius:6px; border:1px solid #cbd5e1; background:white;")
        # Placeholder add kiya:
        self.in_key.setPlaceholderText("🔑 Enter or Generate 32-character AES Key...") 
        
        self.btn_gk = QtWidgets.QPushButton("🔑 Generate Key")

        self.btn_gk.setFixedSize(180, 45)
        self.btn_gk.setStyleSheet("font-weight:bold; font-size:13px; border-radius:6px; background:#f1f5f9; border:1px solid #cbd5e1; padding: 5px;")
        self.btn_gk.clicked.connect(self.do_key)

        # 3. Encryption Button
        btn_proc = QtWidgets.QPushButton("🛡️ START SECURE ENCRYPTION")
        btn_proc.setFixedHeight(55)
        btn_proc.setStyleSheet("background:#0284c7; color:white; font-size:16px; border-radius:8px; font-weight:bold; padding: 10px; text-align: center;")
        btn_proc.clicked.connect(self.do_encrypt_logic)
        
        # Layouts set karna
        bl.addWidget(QtWidgets.QLabel("<span style='font-size:14px; color:black;'>1. Forensic Data Source:</span>"))
        h1 = QtWidgets.QHBoxLayout()
        h1.addWidget(self.in_path)
        h1.addWidget(btn_br)
        bl.addLayout(h1)
        
        bl.addWidget(QtWidgets.QLabel("<span style='font-size:14px; color:black;'>2. Security Token / Key:</span>"))
        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(self.in_key)
        h2.addWidget(self.btn_gk)
        bl.addLayout(h2)
        
        bl.addSpacing(10)
        bl.addWidget(btn_proc)
        
        l2.addWidget(box)
        l2.addStretch()
        self.stack.addWidget(pg2)

        # --- 3. TRANSFER DATA ---
        pg3 = QtWidgets.QWidget(); l3 = QtWidgets.QVBoxLayout(pg3)
        l3.setContentsMargins(30,30,30,30); l3.setSpacing(10)
        l3.addWidget(QtWidgets.QLabel("<h1 style='color:#0369a1;'>Transfer Protocol Selection</h1>"))
        grid = QtWidgets.QGridLayout(); grid.setSpacing(15)
        methods = ["USB", "HDD", "LAN", "Email", "Google Drive"]
        for i, m in enumerate(methods):
            btn = QtWidgets.QPushButton(m)
            btn.setFixedSize(180, 80); btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { 
                    background: white; 
                    border: 2px solid #0284c7; 
                    border-radius: 15px; 
                    font-size: 16px; 
                    font-weight: bold; 
                    color: #0369a1; 
                }
                QPushButton:hover { 
                    background: #0284c7;    /* Hover karne pe background blue ho jayega */
                    color: white;           /* Text ka rang white ho jayega */
                    font-size: 18px;        /* Text thora sa bold/bara dikhega */
                    border: 2px solid #0369a1;
                }
                QPushButton:pressed {
                    background: #0369a1;
                }
            """)
            btn.clicked.connect(lambda checked, name=m: self.do_transfer_logic(name))
            grid.addWidget(btn, i//3, i%3)
        l3.addLayout(grid); l3.addSpacing(10)
        self.lbl_t = QtWidgets.QLabel("Status: Idle"); self.lbl_t.setStyleSheet("font-size:14px; color:#0369a1; font-weight:bold;")
        self.p_bar = QtWidgets.QProgressBar(); self.p_bar.setFixedHeight(25); self.p_bar.setStyleSheet("font-size:12px; font-weight:bold;")
        l3.addWidget(self.lbl_t); l3.addWidget(self.p_bar)
        l3.addStretch(); self.stack.addWidget(pg3)

        # --- 4. MY FILES ---
        # --- 4. MY FILES ---
        pg4 = QtWidgets.QWidget(); l4 = QtWidgets.QVBoxLayout(pg4)
        l4.setContentsMargins(30,30,30,30)
        l4.addWidget(QtWidgets.QLabel("<h2>My Encrypted Files</h2>"))
        
        # Fixed: Direct 4 columns initialized
        self.tab_files = QtWidgets.QTableWidget(0, 4)
        self.tab_files.setColumnCount(4)
        self.tab_files.setHorizontalHeaderLabels(["Filename", "Method", "Size", "Date"])
        self.tab_files.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        l4.addWidget(self.tab_files)
        self.stack.addWidget(pg4)

        # --- 5. FORENSIC LOGS (Audit Trail) ---
        pg_logs = QtWidgets.QWidget(); l_logs = QtWidgets.QVBoxLayout(pg_logs)
        l_logs.setContentsMargins(30,30,30,30)
        l_logs.addWidget(QtWidgets.QLabel("<h2>Detailed Forensic Audit Logs</h2>"))
        self.log_table = QtWidgets.QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["Event ID", "Activity Description", "Security Level"])
        self.log_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        l_logs.addWidget(self.log_table)
        self.stack.addWidget(pg_logs)

        # --- 6. INTEGRITY CHECK (SHA-256) ---
        # --- 6. INTEGRITY CHECK (SHA-256) ---
        pg_int = QtWidgets.QWidget()
        l_int = QtWidgets.QVBoxLayout(pg_int)
        l_int.setContentsMargins(80, 40, 80, 40) 
        
        int_box = QtWidgets.QGroupBox("Data Integrity Verification")
        int_box.setMinimumHeight(580) # Thora height barhayi taake copy button fit aaye
        int_box.setStyleSheet("""
            QGroupBox {
                font-size: 18px; font-weight: bold; color: #0369a1; 
                padding-top: 35px; border: 2px solid #e2e8f0; 
                border-radius: 15px; background: white;
            }
        """)
        
        il = QtWidgets.QVBoxLayout(int_box)
        il.setContentsMargins(40, 40, 40, 40) 
        il.setSpacing(15) 
        
        # 1. Input Field
        self.in_check_path = QtWidgets.QLineEdit()
        self.in_check_path.setPlaceholderText(" Select file to verify integrity...")
        self.in_check_path.setFixedHeight(45) 
        self.in_check_path.setStyleSheet("border-radius: 8px; border: 1px solid #cbd5e1; font-size: 14px; padding-left: 10px;")
        
        # 2. Select File Button
        btn_sel = QtWidgets.QPushButton("📁 Select File")
        btn_sel.setFixedHeight(45)
        btn_sel.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; font-weight: bold;")
        btn_sel.clicked.connect(self.select_file_for_hash)
        
        # 3. Generate Hash Button (Blue)
        btn_calc = QtWidgets.QPushButton("Generate Forensic Hash")
        btn_calc.setFixedHeight(50) 
        btn_calc.setStyleSheet("background: #0284c7; color: white; font-weight: bold; font-size: 15px; border-radius: 10px;")
        btn_calc.clicked.connect(self.calculate_hash_logic)
        
        # 4. Hash Result Label (Text Bara Kar Diya)
        self.out_hash = QtWidgets.QLabel("Status: System Ready")
        self.out_hash.setWordWrap(True)
        self.out_hash.setMinimumHeight(110) 
        self.out_hash.setAlignment(QtCore.Qt.AlignCenter)
        # Font size 16px aur Bold kiya hai taake hash wazeh nazar aaye
        self.out_hash.setStyleSheet("""
            padding: 15px; background: #f0f9ff; border-radius: 10px; 
            color: #0369a1; border: 1px dashed #0284c7; 
            font-family: 'Consolas'; font-size: 16px; font-weight: bold;
        """)

        # 5. NEW: Copy Hash Button
        btn_copy = QtWidgets.QPushButton("📋 Copy Hash to Clipboard")
        btn_copy.setFixedHeight(40)
        btn_copy.setCursor(QtCore.Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: #0284c7; color: white; font-weight: bold; 
                font-size: 13px; border-radius: 8px;
            }
            QPushButton:hover { background: #475569; }
        """)
        btn_copy.clicked.connect(self.copy_hash_to_clipboard) # Naya function link kiya

        il.addWidget(self.in_check_path)
        il.addWidget(btn_sel)
        il.addWidget(btn_calc)
        il.addWidget(self.out_hash)
        il.addWidget(btn_copy) # Layout mein add kiya
        il.addStretch() 
        
        l_int.addWidget(int_box)
        l_int.addStretch() 
        self.stack.addWidget(pg_int)
        

        # --- 7. TRANSFER HISTORY (Missing Table) ---
        # --- 7. TRANSFER HISTORY ---
        pg_hist = QtWidgets.QWidget(); l_hist = QtWidgets.QVBoxLayout(pg_hist)
        l_hist.setContentsMargins(30,30,30,30)
        l_hist.addWidget(QtWidgets.QLabel("<h2>Transfer History Logs</h2>"))
        
        # Fixed: 5 columns and 5 matching labels
        self.tab_hist = QtWidgets.QTableWidget(0, 5)
        self.tab_hist.setColumnCount(5)
        self.tab_hist.setHorizontalHeaderLabels(["Timestamp", "File", "Protocol", "Destination", "Status"])
        self.tab_hist.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        
        l_hist.addWidget(self.tab_hist)
        self.stack.addWidget(pg_hist)
    def copy_hash_to_clipboard(self):
        # Label se text nikaalna (tags remove karke)
        full_text = self.out_hash.text()
        if "SHA-256 Hash:" in full_text:
            # Sirf hash value extract karna
            hash_val = full_text.split("<br>")[-1]
            cb = QtWidgets.QApplication.clipboard()
            cb.setText(hash_val, mode=QtGui.QClipboard.Clipboard)
            QtWidgets.QMessageBox.information(self, "Copied", "Hash has been copied to clipboard!")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "No hash generated yet to copy.")

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

    # ================= REFRESH LOGIC =================
    def update_dashboard_stats(self):
        count_files = self.tab_files.rowCount()
        self.lbl_stat_files.setText(str(count_files))

        count_trans = self.tab_hist.rowCount()
        self.lbl_stat_transfers.setText(str(count_trans))

        succ, susp, fail = 0, 0, 0
        for i in range(count_trans):
            # Status column (Index 4) se text lein
            status_item = self.tab_hist.item(i, 4)
            if status_item:
                txt = status_item.text()
                if "Success" in txt: succ += 1
                elif "Suspicious" in txt: susp += 1
                elif "Failed" in txt: fail += 1
        
        self.lbl_stat_suspicious.setText(str(susp))
        self.lbl_stat_failed.setText(str(fail))
        
        if count_trans > 0:
            rate = int((succ / count_trans) * 100)
            self.lbl_stat_success.setText(f"{rate}%")
        else:
            self.lbl_stat_success.setText("0%")
    def go_home(self):
        self.update_dashboard_stats()
        self.stack.setCurrentIndex(0)

    # ================= DATA PERSISTENCE =================
    def save_data_to_file(self, filename, data):

        try:
            existing_data = []
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    existing_data = json.load(f)
            existing_data.append(data)
            with open(filename, 'w') as f:
                json.dump(existing_data, f, indent=4)
        except Exception as e:
            print(f"Error saving data: {e}")

    def load_stored_data(self):
        # 1. My Files Load karna (Pehle jaisa hi rahega)
        if os.path.exists(self.FILES_STORAGE):
            with open(self.FILES_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        row = self.tab_files.rowCount()
                        self.tab_files.insertRow(row)
                        self.tab_files.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('filename', 'Unknown')))
                        self.tab_files.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('method', 'AES-256')))
                        self.tab_files.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('size', 'N/A'))) 
                        self.tab_files.setItem(row, 3, QtWidgets.QTableWidgetItem(item.get('date', 'Unknown')))
                except Exception as e:
                    print(f"Error loading files: {e}")
        
        # 2. TRANSFER HISTORY LOAD (Yahan Colors ka Logic Update kiya hai)
        if os.path.exists(self.HISTORY_STORAGE):
            with open(self.HISTORY_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        row = self.tab_hist.rowCount()
                        self.tab_hist.insertRow(row)
                        self.tab_hist.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('time', '')))
                        self.tab_hist.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('file', '')))
                        self.tab_hist.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('protocol', '')))
                        self.tab_hist.setItem(row, 3, QtWidgets.QTableWidgetItem(item.get('destination', 'N/A')))
                        
                        # --- COLOR LOGIC FOR RELOADED DATA ---
                        status_text = item.get('status', '')
                        status_item = QtWidgets.QTableWidgetItem(status_text)
                        
                        if "Success" in status_text:
                            status_item.setForeground(QtGui.QColor("#16a34a")) # Green
                        elif "Suspicious" in status_text:
                            status_item.setForeground(QtGui.QColor("#991b1b")) # Dark Red
                            font = QtGui.QFont(); font.setBold(True)
                            status_item.setFont(font)
                        elif "Failed" in status_text:
                            status_item.setForeground(QtGui.QColor("#ef4444")) # Light Red
                            
                        self.tab_hist.setItem(row, 4, status_item)
                except Exception as e:
                    print(f"Error loading history: {e}")

        # 3. Forensic Logs Load (Pehle jaisa hi rahega)
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
                        self.activity_list.addItem(f"● {item.get('activity', 'Activity Recorded')}")
                except Exception as e:
                    print(f"Error loading logs: {e}")
        
        self.update_dashboard_stats()

    def show_case_form(self):
        if not self.selected_file_path:
            QtWidgets.QMessageBox.warning(self, "Warning", "Please encrypt a file first!")
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Forensic Chain of Custody")
        dialog.setFixedWidth(450)
        dialog.setStyleSheet("background-color: white; font-family: 'Segoe UI';")
        layout = QtWidgets.QVBoxLayout(dialog)

        # Labels & Inputs
        layout.addWidget(QtWidgets.QLabel("<b>Case Identifier (e.g. Case 001):</b>"))
        case_id_input = QtWidgets.QLineEdit()
        layout.addWidget(case_id_input)

        layout.addWidget(QtWidgets.QLabel("<b>Authorized Investigator Name:</b>"))
        investigator_input = QtWidgets.QLineEdit()
        investigator_input.setPlaceholderText("Minimum 3 characters required")
        layout.addWidget(investigator_input)
        
        layout.addWidget(QtWidgets.QLabel("<b>Evidence Classification:</b>"))
        classification = QtWidgets.QComboBox()
        classification.addItems(["-- Select Classification --", "Top Secret", "Confidential", "Internal"])
        layout.addWidget(classification)

        btn_verify = QtWidgets.QPushButton("Verify & Proceed to Transfer")
        btn_verify.setStyleSheet("background-color: #0284c7; color: white; padding: 12px; font-weight: bold; border-radius: 5px;")
        layout.addWidget(btn_verify)

        def validate_logic():
            c_id = case_id_input.text().strip()
            inv = investigator_input.text().strip()
            
            # --- STRICT VALIDATION ---
            if not c_id or not inv or classification.currentIndex() == 0:
                QtWidgets.QMessageBox.critical(dialog, "Error", "All fields are mandatory!")
            elif "case" not in c_id.lower():
                QtWidgets.QMessageBox.critical(dialog, "Error", "Case ID must contain the word 'Case'!")
            elif len(inv) < 3: # At least 3 digits/characters rule
                QtWidgets.QMessageBox.critical(dialog, "Error", "Investigator name must be at least 3 characters long!")
            else:
                self.temp_case_id = c_id
                self.temp_investigator = inv
                dialog.accept()

        btn_verify.clicked.connect(validate_logic)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Step 2: Documentation ke baad Transfer Methods page khule (Index 2)
            if hasattr(self, 'stack'):
                self.stack.setCurrentIndex(2)
                self.show_msg("Success", "Documentation saved. Now choose a Transfer Method.")

    def get_current_drives(self):
        return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

    def do_browse(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Forensic File")
        if file_path:
            self.in_path.setText(file_path)
            # --- YEH LINE ZAROORI HAI ---
            # Hum asli rasta save kar rahe hain taake encryption ke baad bhi yaad rahe
            self.original_selection_path = file_path

    def do_key(self):
        # Pehle check karein ke file select hai ya nahi
        if not self.in_path.text().strip():
            QtWidgets.QMessageBox.warning(self, "Selection Required", "⚠️ Please select a forensic file first!")
            return
        
        # Agar box mein pehle se key maujood hai (yani user dobara click kar raha hai)
        if self.in_key.text().strip():
            reply = QtWidgets.QMessageBox.question(self, 'Change Key?', 
                     "A security key is already generated. Are you sure you want to replace it with a NEW one?",
                     QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            
            if reply == QtWidgets.QMessageBox.No:
                return  # Agar user 'No' kahe toh purani key hi rehne do

        # Nayi unique AES-256 key generate karein
        key = ''.join(random.choices("0123456789abcdef", k=32))
        self.in_key.setText(key)
        
        # Log mein entry
        self.add_forensic_log(f"New AES key generated for session.", "LOW")

       

    def add_notification(self, title, message, status):
        from datetime import datetime
        time_now = datetime.now().strftime("%H:%M:%S")
        
        # Icon selection based on status
        if "Success" in status: 
            icon = "✅"
        elif "Suspicious" in status: 
            icon = "🚨"
        else: 
            icon = "❌"
        
        # Format: Single line for menu, but full details
        # Hum \n ki jagah space aur dashes use kar rahe hain taake menu mein pura show ho
        display_text = f"{icon} [{time_now}] {title}: {message}"
        
        # UI Menu Update
        action = QtWidgets.QAction(display_text, self)
        
        # Is se jab aap mouse notification pe layengi toh pura message tooltip mein dikhega
        action.setToolTip(f"Full Message: {message}")
        
        if len(self.notif_menu.actions()) == 0:
            self.notif_menu.addAction(action)
        else:
            self.notif_menu.insertAction(self.notif_menu.actions()[0], action)

        # Badge Update
        self.unread_count += 1
        self.notif_badge.setText(str(self.unread_count))
        self.notif_badge.show()

        # Save to JSON
        notif_entry = {
            "text": display_text,
            "is_read": False,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.save_data_to_file(self.NOTIFICATIONS_STORAGE, notif_entry)

    def mark_as_read(self):
        """Jab user click karke menu dekhega toh badge hat jayega aur file update hogi"""
        self.unread_count = 0
        self.notif_badge.hide()
        
        # File mein sab notifications ko 'read' mark kar dein
        if os.path.exists(self.NOTIFICATIONS_STORAGE):
            try:
                with open(self.NOTIFICATIONS_STORAGE, 'r') as f:
                    data = json.load(f)
                
                for n in data:
                    n['is_read'] = True
                
                with open(self.NOTIFICATIONS_STORAGE, 'w') as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                print(f"Error marking notifications as read: {e}")

    def do_encrypt_logic(self, filename):
        self.log_to_ws_db("APP_ENCRYPTION_START", "SENDER_APP", filename, "Internal Vault")
        input_path = self.in_path.text()
        key_text = self.in_key.text()

        if input_path and key_text:
            if len(key_text) != 32:
                QtWidgets.QMessageBox.warning(self, "Key Error", "AES-256 key must be exactly 32 characters long.")
                return

            try:
                # --- FILE SIZE CALCULATE ---
                file_size_bytes = os.path.getsize(input_path)
                if file_size_bytes < 1024 * 1024:
                    file_size_str = f"{file_size_bytes / 1024:.2f} KB"
                else:
                    file_size_str = f"{file_size_bytes / (1024 * 1024):.2f} MB"

                original_filename = os.path.basename(input_path)
                encrypted_filename = f"ENCRYPTED_{original_filename}.aes"
                save_dir = "Encrypted_Vault"
                if not os.path.exists(save_dir): os.makedirs(save_dir)
                dest_path = os.path.join(save_dir, encrypted_filename)

                # --- AES ENCRYPTION LOGIC ---
                with open(dest_path + ".key.txt", 'w') as kf:
                    kf.write(key_text)

                key = key_text.encode('utf-8')
                iv = os.urandom(16) 
                
                with open(input_path, 'rb') as f:
                    file_data = f.read()

                padder = padding.PKCS7(128).padder()
                padded_data = padder.update(file_data) + padder.finalize()

                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

                with open(dest_path, 'wb') as f:
                    f.write(iv + encrypted_data)

                # --- SUCCESS UPDATES ---
                self.selected_file_path = dest_path 
                date_str = QtCore.QDate.currentDate().toString()
                
                # Table Update
                row = self.tab_files.rowCount()
                self.tab_files.insertRow(row)
                self.tab_files.setItem(row, 0, QtWidgets.QTableWidgetItem(encrypted_filename))
                self.tab_files.setItem(row, 1, QtWidgets.QTableWidgetItem("AES-256"))
                self.tab_files.setItem(row, 2, QtWidgets.QTableWidgetItem(file_size_str))
                self.tab_files.setItem(row, 3, QtWidgets.QTableWidgetItem(date_str))
                
                # Activity & Storage
                self.save_data_to_file(self.FILES_STORAGE, {
                    "filename": encrypted_filename, 
                    "method": "AES-256", 
                    "size": file_size_str, 
                    "date": date_str
                })
                self.activity_list.addItem(f"● File Secured: {encrypted_filename} at {QtCore.QTime.currentTime().toString()}")

                # Final Success Message
                QtWidgets.QMessageBox.information(self, "Security Engine", f"Data '{original_filename}' encrypted successfully!")

                # --- AUTOMATIC FORENSIC TRIGGER ---
                # Ab encryption kamyab ho chuki hai, toh documentation form khulega
                QtCore.QTimer.singleShot(300, self.show_case_form)

            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Encryption Failed", f"An error occurred: {str(e)}")
        else:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please provide both file path and a 32-char key.")
    

    def do_transfer_logic(self, method):
        if not self.selected_file_path:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please select and encrypt a file first.")
            return

        # --- REAL FORENSIC CHECK ---
        file_name = os.path.basename(self.selected_file_path).lower()
        file_size = os.path.getsize(self.selected_file_path)
        suspicious_exts = ['.exe', '.bat', '.py', '.msi', '.sh', '.cmd', '.js']
        
        status = "Success"
        log_level = "LOW"

        if any(file_name.endswith(ext) for ext in suspicious_exts):
            status = "Suspicious (Unsafe)"
            log_level = "HIGH"
        elif file_size == 0:
            status = "Failed (Empty File)"
            log_level = "MEDIUM"

        # Alert if suspicious
        if status != "Success":
            QtWidgets.QMessageBox.critical(self, "Forensic Alert", 
                f"SECURITY WARNING: The file '{file_name}' is {status}.")
            # Yahan notification foran bhej dein kyunke transfer block ho gaya
            self.add_notification(f"{method} Transfer", f"Result: {status}", status)
            self.add_to_history(method, status)
            self.add_forensic_log(f"File Selected: {os.path.basename(file_name)}", "INFO")
            return

        self.lbl_t.setText(f"Status: Initiating {method}...")
        self.p_bar.setValue(0)

   # --- PROTOCOL EXECUTION ---
        
        if method == "Google Drive":
            if not self.selected_file_path:
                self.add_notification("Error", "Please select and encrypt a file first!", "Failed")
                return
            
            self.lbl_t.setText("Status: Authenticating Google Drive...")
            # Threading use karein taake UI hang na ho
            thread = threading.Thread(target=self.perform_gdrive_upload)
            thread.daemon = True
            thread.start()
        if method in ["USB", "HDD"]:
            self.existing_drives = self.get_current_drives()
            self.monitor_timer = QtCore.QTimer()
            # Pass method to detect_new_hardware
            self.monitor_timer.timeout.connect(lambda: self.detect_new_hardware(method))
            self.monitor_timer.start(1000)
            QtWidgets.QMessageBox.information(self, "Hardware Scan", f"Please plug in your {method} drive...")

        elif method == "LAN":
            ip, ok = QtWidgets.QInputDialog.getText(self, 'LAN Transfer', 'Enter Receiver IP:')
            if ok and ip: 
                # LAN function ab khud notification handle karega
                self.perform_lan_transfer(ip) 
            else:
                self.lbl_t.setText("Status: Cancelled")

        elif method == "Email":
            self.perform_real_email_transfer()
        
    def detect_new_hardware(self, method):
        """Monitors for USB/HDD connection and handles notifications"""
        current_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        new_drives = [d for d in current_drives if d not in self.existing_drives]

        if new_drives:
            self.monitor_timer.stop()
            target_drive = new_drives[0]
            # Nayi drive milte hi copy_file_to_drive function ko call karein
            self.copy_file_to_drive(target_drive, method)
    def copy_file_to_drive(self, drive, method):
        try:
            if not hasattr(self, 'selected_file_path') or not self.selected_file_path:
                QtWidgets.QMessageBox.warning(self, "No File", "Please select a file first!")
                return

            filename = os.path.basename(self.selected_file_path)
            # Root ke bajaye folder mein save karein taake Permission Error na aaye
            dest_folder = os.path.join(drive, "Forensic_Transfers")
            
            # Folder check aur creation
            if not os.path.exists(dest_folder):
                try:
                    os.makedirs(dest_folder)
                except Exception as e:
                    # Agar folder na ban sake (USB write protected ho)
                    raise PermissionError(f"Cannot create folder on {drive}. Drive might be write-protected.")

            target_path = os.path.join(dest_folder, filename)

            # Progress Bar & UI Updates
            for i in range(0, 101, 20):
                QtCore.QThread.msleep(50)
                self.p_bar.setValue(i)
                self.lbl_t.setText(f"Status: Copying to {method}... {i}%")
                QtWidgets.QApplication.processEvents()

            # Forensic Copy (Metadata preserve karta hai)
            import shutil
            shutil.copy2(self.selected_file_path, target_path)
            
            # Final UI Updates
            self.p_bar.setValue(100)
            self.lbl_t.setText(f"Status: {method} Success! 100%")
            
            # Logging & Notifications
            self.add_to_history(method, "Success", destination=dest_folder)
            self.add_notification(f"{method} Transfer", f"File copied to {dest_folder}", "Success")
            
            # Forensic Log Entry
            try:
                self.add_forensic_log(f"File copied to {method} drive: {drive}", "LOW")
            except: pass
            
            # Success Popup (Professional Look)
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowTitle("Transfer Complete")
            msg_box.setText(f"<span style='color: #16a34a; font-weight: bold;'>✅ Success! File transferred to {method}.</span>")
            msg_box.setInformativeText(f"Destination: {dest_folder}")
            msg_box.exec_()

           
            
        except PermissionError as pe:
            self.lbl_t.setText("Status: Permission Denied")
            QtWidgets.QMessageBox.critical(self, "Access Error", f"Permission Denied: {str(pe)}\n\nTry running app as Administrator.")
        except Exception as e:
            self.lbl_t.setText("Status: Copy Failed")
            QtWidgets.QMessageBox.critical(self, "Transfer Error", f"Failed to copy file: {str(e)}")
            self.p_bar.setValue(0)
    def perform_lan_transfer(self, ip):
        method_label = "LAN Transfer"
        try:
            if not self.selected_file_path or not os.path.exists(self.selected_file_path):
                self.add_notification(method_label, "Failed: File not found", "Failed")
                QtWidgets.QMessageBox.warning(self, "Error", "File not found!")
                return

            # Check for suspicious extensions before sending
            file_ext = os.path.splitext(self.selected_file_path)[1].lower()
            if file_ext in ['.exe', '.bat', '.py', '.msi']:
                self.add_notification(method_label, f"Suspicious file blocked: {os.path.basename(self.selected_file_path)}", "Suspicious")
                QtWidgets.QMessageBox.critical(self, "Security Alert", "Suspicious file detected!")
                return

            self.lbl_t.setText(f"Status: Connecting to {ip}...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, 5000))
            
            # File sending logic
            with open(self.selected_file_path, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    client_socket.sendall(chunk)
            
            client_socket.close()
            
            # Success Outcome
            self.p_bar.setValue(100)
            self.lbl_t.setText("Status: LAN Transfer Success!")
            self.add_notification(method_label, f"File sent to {ip} successfully", "Success")
            self.add_to_history("LAN", "Success", destination=ip)
            QtWidgets.QMessageBox.information(self, "Success", f"File sent to {ip}!")

            

        except Exception as e:
            # Fail Outcome
            self.lbl_t.setText("Status: LAN Failed")
            self.add_notification(method_label, f"Transfer failed: {str(e)}", "Failed")
            self.add_to_history("LAN", "Failed", destination=ip)
            QtWidgets.QMessageBox.critical(self, "Error", f"LAN Error: {str(e)}")
            

    def perform_real_email_transfer(self):
        import ssl
        import time
        import os
        method_label = "Email Transfer"
        
        self.SENDER_EMAIL = "furqant972@gmail.com"
        self.SENDER_PASSWORD = "ldrc xmjp ncqm qzyo" 

        receiver, ok = QtWidgets.QInputDialog.getText(self, 'Email Transfer', 'Enter Receiver Email:')
        if not ok or not receiver: return

        try:
            # 1. Internet Check
            import socket
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=3)
            except OSError:
                QtWidgets.QMessageBox.warning(self, "No Internet", "Please connect to the internet first!")
                return

            if not self.selected_file_path or not os.path.exists(self.selected_file_path):
                QtWidgets.QMessageBox.warning(self, "File Error", "Please select a file first!")
                return

            # --- 2. FOOLPROOF PATH VALIDATION ---
            # Hum check karenge ke kya ASLI file (jo shuru mein select hui thi) EmailData folder se thi?
            # Agar kisi wajah se original_selection_path nahi milta, toh current path check kar lega.
            origin_path = getattr(self, 'original_selection_path', self.selected_file_path)
            
            check_string = str(origin_path).lower()
            authorized_folder = "emaildata".lower()
            
            # Agar raste mein 'emaildata' aata hai toh Authorized hai
            is_authorized = authorized_folder in check_string
            
            real_file_name = os.path.basename(self.selected_file_path)

            # --- 3. Progress Bar & SMTP Setup ---
            for i in range(1, 41):
                self.p_bar.setValue(i); QtWidgets.QApplication.processEvents(); time.sleep(0.01)

            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context, timeout=30)
            server.login(self.SENDER_EMAIL, self.SENDER_PASSWORD)
            
            for i in range(41, 71):
                self.p_bar.setValue(i); QtWidgets.QApplication.processEvents(); time.sleep(0.01)

            # --- 4. Message Construction ---
            from email.mime.multipart import MIMEMultipart
            from email.mime.base import MIMEBase
            from email import encoders

            msg = MIMEMultipart()
            msg['From'] = self.SENDER_EMAIL
            msg['To'] = receiver
            msg['Subject'] = "Secure Forensic Package"
            
            with open(self.selected_file_path, "rb") as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{real_file_name}"')
                msg.attach(part)

            server.send_message(msg)
            server.quit()

            for i in range(71, 101):
                self.p_bar.setValue(i); QtWidgets.QApplication.processEvents(); time.sleep(0.01)

            # --- 5. FINAL LOGGING DECISION ---
            if is_authorized:
                # Agar C:\EmailData se thi toh SUCCESS
                self.add_forensic_log(f"Email Sent to {receiver}", "SUCCESS", real_file_name)
                status_txt = "Email has been sent successfully!"
            else:
                # Agar bahar se thi toh UNAUTHORIZED
                self.add_forensic_log(f"UNAUTHORIZED_LOCATION_UPLOAD: {receiver}", "WARNING", real_file_name)
                status_txt = "Security Warning: File sent from unauthorized location!"

            self.add_notification(method_label, f"Sent to {receiver}", "Success")
            self.add_to_history("Email", "Success", destination=receiver)
            QtWidgets.QMessageBox.information(self, "Success", status_txt)

            

        except Exception as e:
            self.p_bar.setValue(0)
            QtWidgets.QMessageBox.critical(self, "Error", f"Email failed: {str(e)}")
    def perform_gdrive_upload(self):
        method_label = "Google Drive"
        try:
            # --- AUTHORIZATION LOGIC ---
            origin_path = getattr(self, 'original_selection_path', self.selected_file_path)
            check_string = str(origin_path).lower()
            authorized_folder = "clouddata".lower()
            
            is_authorized = authorized_folder in check_string
            real_file_name = os.path.basename(self.selected_file_path)

            self.update_progress.emit(10, "Status: Authenticating Google Drive...")
            
            gauth = GoogleAuth()
            gauth.LocalWebserverAuth() 
            drive = PDrive(gauth)

            self.update_progress.emit(50, f"Status: Uploading {real_file_name}...")

            gfile = drive.CreateFile({'title': real_file_name})
            gfile.SetContentFile(self.selected_file_path)
            gfile.Upload()

            gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            share_link = gfile['alternateLink']
            
            # --- Forensic Hash Calculation (Naya Add Kiya) ---
            file_hash = self.generate_file_hash(self.selected_file_path)

            # --- YAHAN CHANGE HAI ---
            if is_authorized:
                status_msg = "File uploaded to Cloud successfully!"
                status_type = "Success"
                self.add_forensic_log(f"Cloud Upload Success: {real_file_name}", "SUCCESS", real_file_name)
                
                # NAYA: Case Documentation ke sath database mein record karna
                self.record_forensic_event(real_file_name, "Cloud Upload", file_hash=file_hash)
            else:
                status_msg = "Security Warning: Unauthorized Cloud Transfer Detected!"
                status_type = "Suspicious"
                self.add_forensic_log(f"UNAUTHORIZED_CLOUD_UPLOAD: {real_file_name}", "WARNING", real_file_name)
                
                # NAYA: Unauthorized upload ko bhi Case details ke sath record karna
                self.record_forensic_event(real_file_name, "UNAUTHORIZED_CLOUD_UPLOAD", file_hash=file_hash)

            # UI Update
            self.update_progress.emit(100, f"Status: {status_msg}")
            self.show_gdrive_link.emit(share_link)
            
            self.add_to_history("Google Drive", status_type, destination="Google Cloud")
            
            QtCore.QMetaObject.invokeMethod(self, "add_notification", 
                                          QtCore.Qt.QueuedConnection,
                                          QtCore.Q_ARG(str, method_label),
                                          QtCore.Q_ARG(str, status_msg),
                                          QtCore.Q_ARG(str, status_type))

           

        except Exception as e:
            self.update_progress.emit(0, f"Status: G-Drive Error - {str(e)}")
            self.add_notification(method_label, f"Upload failed: {str(e)}", "Failed")
    def show_msg(self, title, text):
        QtWidgets.QMessageBox.information(self, title, text)
    @QtCore.pyqtSlot(str)
    def show_gdrive_success(self, link):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Success")
        msg.setText(f"<b>File Uploaded to Drive!</b><br><br>Share this link with Receiver:<br><a href='{link}'>{link}</a>")
        copy_btn = msg.addButton("Copy Link", QtWidgets.QMessageBox.ActionRole)
        msg.addButton(QtWidgets.QMessageBox.Ok)
        msg.exec_()
        if msg.clickedButton() == copy_btn:
            QtWidgets.QApplication.clipboard().setText(link)
    def handle_ui_progress(self, value, text):
        self.p_bar.setValue(value)
        self.lbl_t.setText(text)
    def add_to_history(self, method, status, destination="N/A"):
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        # Check karein agar path mojood hai toh filename nikalen
        file_name = os.path.basename(self.selected_file_path) if self.selected_file_path else "Unknown"
        
        row = self.tab_hist.rowCount()
        self.tab_hist.insertRow(row)
        
        # Basic Data setup
        self.tab_hist.setItem(row, 0, QtWidgets.QTableWidgetItem(time_str))
        self.tab_hist.setItem(row, 1, QtWidgets.QTableWidgetItem(file_name))
        self.tab_hist.setItem(row, 2, QtWidgets.QTableWidgetItem(method))
        self.tab_hist.setItem(row, 3, QtWidgets.QTableWidgetItem(destination))
        
        # --- VISUAL STATUS LOGIC ---
        status_item = QtWidgets.QTableWidgetItem(status)
        
        if "Suspicious" in status:
            # Red color for suspicious files
            status_item.setForeground(QtGui.QColor("#dc2626")) 
            font = QtGui.QFont()
            font.setBold(True)
            status_item.setFont(font)
        elif "Failed" in status:
            # Orange color for failed/empty files
            status_item.setForeground(QtGui.QColor("#f97316"))
        else:
            # Green color for normal success
            status_item.setForeground(QtGui.QColor("#16a34a"))
            
        self.tab_hist.setItem(row, 4, status_item)
        
        # Database (JSON) mein save karein taake record rahe
        self.save_data_to_file(self.HISTORY_STORAGE, {
            "time": time_str, 
            "file": file_name, 
            "protocol": method, 
            "destination": destination, 
            "status": status
        })
        
        # Stats refresh karein
        self.update_dashboard_stats()

    # Forensic Hash Calculation Logic
    def select_file_for_hash(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File for Hash")
        if f: self.in_check_path.setText(f)

    def calculate_hash_logic(self):
        import hashlib
        path = self.in_check_path.text()
        if os.path.exists(path):
            sha256_hash = hashlib.sha256()
            with open(path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            v_hash = sha256_hash.hexdigest()
            self.out_hash.setText(f"<b>SHA-256 Hash:</b><br>{v_hash}")
            # Add to Forensic Logs
            self.add_forensic_log(f"Integrity Check performed on {os.path.basename(path)}", "MEDIUM")
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "File not found!")

    # Forensic Logging Logic
    def add_forensic_log(self, activity, level, file_name="N/A"):
        # --- STEP 1: UI UPDATE ---
        try:
            event_id = f"EVT-{random.randint(1000, 9999)}"
            
            # Table update
            row = self.log_table.rowCount()
            self.log_table.insertRow(row)
            self.log_table.setItem(row, 0, QtWidgets.QTableWidgetItem(event_id))
            self.log_table.setItem(row, 1, QtWidgets.QTableWidgetItem(activity))
            self.log_table.setItem(row, 2, QtWidgets.QTableWidgetItem(level))

            # Activity list
            self.activity_list.addItem(f"● {activity} ({file_name})")
            
            # JSON save
            log_data = {"event_id": event_id, "activity": activity, "level": level, "file": file_name}
            self.save_data_to_file(self.LOGS_STORAGE, log_data)
        except Exception as ui_err:
            print(f"UI Update Error: {ui_err}")

        # --- STEP 2: WS DATABASE ---
        try:
            import sqlite3
            from datetime import datetime
            import os
            
            db_path = r"C:\ProgramData\SecureForensic\forensic.db"
            if not os.path.exists(os.path.dirname(db_path)): return

            conn = sqlite3.connect(db_path, timeout=20)
            cur = conn.cursor()
            
            # YAHAN SEQUENCE SAHI KAR DI HAI:
            # logs (username, role, action, method, file_name, file_path, time)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Hum file_path ki jagah level bhej rahe hain filhal, lekin file_name ki jagah REAL name
            cur.execute("""
                INSERT INTO logs (username, role, action, method, file_name, file_path, time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.user_name, "User", activity, "APP_FORENSIC", file_name, level, current_time))
            
            conn.commit()
            conn.close()
            print(f"WS Log Saved: {file_name}")
            
        except Exception as e:
            print(f"WS Logging Skip (Reason: {e})")
    def show_msg(self, title, message):
        # Yeh function missing tha jiski wajah se crash ho raha tha
        QtWidgets.QMessageBox.information(self, title, message)
    # --- Class ke andar ye naya function add karein ---
    def upload_to_google_drive(self, file_path) :
        try:
            self.log_activity("● G-Drive: Authenticating...")
            gauth = GoogleAuth()
        
        # Ye line browser kholegi login ke liye (sirf pehli baar)
            gauth.LocalWebserverAuth() 
            drive = PDrive(gauth)

            self.log_activity(f"● G-Drive: Uploading {os.path.basename(file_path)}...")
        
            folder_id = "root" # Aap specific folder ID bhi de sakte hain
            gfile = drive.CreateFile({'title': os.path.basename(file_path)})
            gfile.SetContentFile(file_path)
            gfile.Upload()

        # Shareable link banana taake receiver ko manually diya ja sakay
            gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            share_link = gfile['alternateLink']

            self.log_activity(f"● G-Drive: Upload Success!")
        
        # Ek popup mein link dikhayein taake user receiver ko bhej sakay
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle("Upload Successful")
            msg.setText("File uploaded to Google Drive!")
            msg.setInformativeText(f"Share this link with Receiver:\n\n{share_link}")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
        
            self.add_to_history(os.path.basename(file_path), "Google Drive", "Success")

        except Exception as e:
            self.log_activity(f"● G-Drive Error: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "G-Drive Error", f"Failed to upload: {str(e)}")
    @QtCore.pyqtSlot(str, str)
   
    def record_forensic_event(self, filename, event_type, file_hash="N/A"):
        """Inserts forensic logs into the shared Admin Database."""
        try:
            # Ensure attributes exist to avoid crashes
            c_id = getattr(self, 'temp_case_id', 'N/A')
            inv = getattr(self, 'temp_investigator', 'Unknown')
            
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            
            # Formatting the description for the Admin Audit Trail
            detailed_desc = f"Case: {c_id} | Inv: {inv} | File: {filename} | Hash: {file_hash}"
            
            cursor.execute("""
                INSERT INTO audit_trail (action_type, user_id, description, timestamp) 
                VALUES (?, ?, ?, ?)
            """, (event_type, 1, detailed_desc, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Admin Log Error: {e}")

    def show_msg(self, title, message):
        """Helper function to show alerts without crashing."""
        QtWidgets.QMessageBox.information(self, title, message)

    def record_manual_transfer(self, method_name):
        """Triggered by USB/LAN/HDD buttons."""
        if not self.selected_file_path:
            self.show_msg("System Warning", "Please select and encrypt a file first!")
            return

        try:
            file_name = os.path.basename(self.selected_file_path)
            file_hash = self.generate_file_hash(self.selected_file_path)
            
            # 1. Log to Admin Database
            self.record_forensic_event(file_name, f"Transfer Method: {method_name}", file_hash)
            
            # 2. Update History & My Files Table with Colors
            self.update_tables_after_transfer(file_name, method_name, "Success")
            
            # 3. SUCCESS MESSAGE
            self.show_msg("Success", f"Evidence logged! Moving to My Files view.")

            # --- AUTOMATIC PAGE SWITCH TO MY FILES (Index 1) ---
            if hasattr(self, 'stack'):
                self.stack.setCurrentIndex(1) # My Files ka index 1 hai
            
        except Exception as e:
            self.update_tables_after_transfer(os.path.basename(self.selected_file_path), method_name, "Fail")
            self.show_msg("Error", f"Logging failed: {str(e)}")
    
    

    def load_stored_data(self):
        # 1. My Files Load karna (Size column ke saath)
        if os.path.exists(self.FILES_STORAGE):
            with open(self.FILES_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        row = self.tab_files.rowCount()
                        self.tab_files.insertRow(row)
                        self.tab_files.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('filename', 'Unknown')))
                        self.tab_files.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('method', 'AES-256')))
                        # Column 2 mein Size load ho raha hai
                        self.tab_files.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('size', 'N/A'))) 
                        # Column 3 mein Date load ho rahi hai
                        self.tab_files.setItem(row, 3, QtWidgets.QTableWidgetItem(item.get('date', 'Unknown')))
                except Exception as e:
                    print(f"Error loading files: {e}")
        
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


        # --- Notifications Load Karein ---
        if os.path.exists(self.NOTIFICATIONS_STORAGE):
            with open(self.NOTIFICATIONS_STORAGE, 'r') as f:
                try:
                    all_notifs = json.load(f)
                    self.unread_count = 0
                    # Reverse isliye taake latest upar aayein
                    for n in all_notifs:
                        action = QtWidgets.QAction(n.get('text', ''), self)
                        # Menu mein add karein
                        if len(self.notif_menu.actions()) == 0:
                            self.notif_menu.addAction(action)
                        else:
                            self.notif_menu.insertAction(self.notif_menu.actions()[0], action)
                        
                        
                        if not n.get('is_read', False):
                            self.unread_count += 1
                    
                    # Agar unread notifications hain toh badge dikhayein
                    if self.unread_count > 0:
                        self.notif_badge.setText(str(self.unread_count))
                        self.notif_badge.show()
                except Exception as e:
                    print(f"Error loading notifications: {e}")
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = SenderDashboard()
    win.show()
    sys.exit(app.exec_())