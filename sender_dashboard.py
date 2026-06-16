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
import hashlib
import http
import sqlite3
import os
import sys
from app import write_audit_log, write_anomaly_alert, write_system_log, DB_PATH
from key_exchange import encrypt_aes_key, is_valid_public_key
from db_crypto import encrypt_field, decrypt_field
# Set working directory to the folder where sender_dashboard.py is located
SENDER_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SENDER_BASE_DIR)
print(f"[SUCCESS] Sender working directory: {os.getcwd()}")
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive as PDrive

# --- ENCRYPTION IMPORTS ---
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Error: 'cryptography' library missing...")

# --- REPORTLAB (PDF) IMPORTS ---
try:
    from reportlab.lib.pagesizes import A4 as _RL_A4
    from reportlab.lib import colors as _RL_colors
    from reportlab.lib.styles import getSampleStyleSheet as _RL_styles
    from reportlab.lib.units import cm as _RL_cm
    from reportlab.platypus import (
        SimpleDocTemplate as _RL_Doc, Paragraph as _RL_Para,
        Spacer as _RL_Spacer, Table as _RL_Table,
        TableStyle as _RL_TableStyle, HRFlowable as _RL_HR
    )
    from reportlab.lib.enums import TA_CENTER as _RL_CENTER, TA_LEFT as _RL_LEFT
    from reportlab.lib.styles import ParagraphStyle as _RL_PS
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False

# ═══════════════════════════════════════════════════════════════
# NOTIFICATION BELL — clean bell button with red badge counter
# ═══════════════════════════════════════════════════════════════
class NotifBell(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.counter = 0
        self.setFixedSize(50, 50)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_Hover)

        # Bell emoji label
        self._bell = QtWidgets.QLabel("🔔", self)
        self._bell.setFixedSize(50, 50)
        self._bell.setAlignment(QtCore.Qt.AlignCenter)
        self._bell.setStyleSheet("font-size:26px; background:transparent;")

        # Red badge label (hidden by default)
        self._badge = QtWidgets.QLabel("", self)
        self._badge.setFixedSize(20, 20)
        self._badge.move(28, 2)
        self._badge.setAlignment(QtCore.Qt.AlignCenter)
        self._badge.setStyleSheet(
            "background:#ef4444; color:white; border-radius:10px; "
            "font-size:9px; font-weight:bold; border:2px solid white;"
        )
        self._badge.hide()

    def setCounter(self, n):
        self.counter = n
        if n > 0:
            self._badge.setText(str(n) if n < 100 else "99+")
            self._badge.show()
        else:
            self._badge.hide()
        self.update()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()

    def enterEvent(self, e):
        self._bell.setStyleSheet(
            "font-size:26px; background:rgba(255,255,255,0.15); "
            "border-radius:25px;"
        )

    def leaveEvent(self, e):
        self._bell.setStyleSheet("font-size:26px; background:transparent;")


# ═══════════════════════════════════════════════════════════════
# NOTIFICATION PANEL — styled dropdown panel
# ═══════════════════════════════════════════════════════════════
class NotifPanel(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setFixedWidth(380)
        self.setStyleSheet(
            "NotifPanel { background:white; border-radius:14px; "
            "border:1px solid #e2e8f0; }"
        )
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        self._all_notifs = []
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────
        hdr = QtWidgets.QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1a56db, stop:1 #1e62f0); "
            "border-top-left-radius:14px; border-top-right-radius:14px; }"
        )
        hl = QtWidgets.QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(8)

        bell_lbl = QtWidgets.QLabel("🔔")
        bell_lbl.setStyleSheet("font-size:18px; background:transparent;")
        title_lbl = QtWidgets.QLabel("Notifications")
        title_lbl.setStyleSheet(
            "color:white; font-size:14px; font-weight:bold; background:transparent;"
        )
        self.count_lbl = QtWidgets.QLabel("0")
        self.count_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.count_lbl.setFixedSize(22, 22)
        self.count_lbl.setStyleSheet(
            "background:#ef4444; color:white; font-size:10px; font-weight:bold; "
            "border-radius:11px; border:none;"
        )
        self.count_lbl.hide()

        self.clear_btn = QtWidgets.QPushButton("🗑 Clear All")
        self.clear_btn.setFixedHeight(26)
        self.clear_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet(
            "QPushButton { background:rgba(255,255,255,0.18); color:white; "
            "font-size:11px; font-weight:bold; border-radius:6px; "
            "padding:0 10px; border:1px solid rgba(255,255,255,0.30); } "
            "QPushButton:hover { background:rgba(255,255,255,0.35); }"
        )

        hl.addWidget(bell_lbl)
        hl.addWidget(title_lbl)
        hl.addWidget(self.count_lbl)
        hl.addStretch()
        hl.addWidget(self.clear_btn)
        root.addWidget(hdr)

        # ── Scroll area ──────────────────────────────────────────
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(320)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea { border:none; background:white; }
            QScrollBar:vertical {
                background:#f1f5f9; width:7px;
                border-radius:3px; margin:2px;
            }
            QScrollBar::handle:vertical {
                background:#cbd5e1; border-radius:3px; min-height:24px;
            }
            QScrollBar::handle:vertical:hover { background:#1a56db; }
        """)
        self.items_w = QtWidgets.QWidget()
        self.items_w.setStyleSheet("background:white;")
        self.items_l = QtWidgets.QVBoxLayout(self.items_w)
        self.items_l.setContentsMargins(10, 8, 10, 8)
        self.items_l.setSpacing(6)
        self.scroll.setWidget(self.items_w)
        root.addWidget(self.scroll)

        # ── Footer ───────────────────────────────────────────────
        foot = QtWidgets.QFrame()
        foot.setFixedHeight(36)
        foot.setStyleSheet(
            "QFrame { background:#f8fafc; border-top:1px solid #e2e8f0; "
            "border-bottom-left-radius:14px; border-bottom-right-radius:14px; }"
        )
        fl = QtWidgets.QHBoxLayout(foot)
        fl.setContentsMargins(14, 0, 14, 0)
        self.foot_lbl = QtWidgets.QLabel("No notifications yet")
        self.foot_lbl.setStyleSheet(
            "color:#94a3b8; font-size:11px; background:transparent;"
        )
        fl.addWidget(self.foot_lbl)
        fl.addStretch()
        root.addWidget(foot)

    def populate(self, notifs):
        self._all_notifs = notifs
        n = len(notifs)
        self.count_lbl.setText(str(n))
        self.count_lbl.setVisible(n > 0)
        self.foot_lbl.setText(
            f"{n} notification{'s' if n != 1 else ''}" if n else "No notifications yet"
        )
        self._render(notifs)

    def _render(self, notifs):
        while self.items_l.count():
            c = self.items_l.takeAt(0)
            if c.widget():
                c.widget().deleteLater()

        if not notifs:
            empty = QtWidgets.QLabel("🔕   No notifications yet")
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setStyleSheet(
                "color:#94a3b8; font-size:13px; padding:40px 20px; background:transparent;"
            )
            self.items_l.addWidget(empty)
            return

        STATUS_CFG = {
            "Success": ("#dcfce7", "#16a34a", "✅"),
            "Failed":  ("#fee2e2", "#dc2626", "❌"),
            "Warning": ("#fef9c3", "#ca8a04", "⚠️"),
            "Info":    ("#e0f2fe", "#1a56db", "ℹ️"),
        }

        for item in notifs:
            st = item.get("status", "Info")
            bg, accent, icon = STATUS_CFG.get(st, STATUS_CFG["Info"])

            row = QtWidgets.QFrame()
            row.setStyleSheet(
                f"QFrame {{ background:white; border-radius:8px; "
                f"border-left:3px solid {accent}; "
                f"border-top:1px solid #f1f5f9; "
                f"border-right:1px solid #f1f5f9; "
                f"border-bottom:1px solid #f1f5f9; }}"
                f"QFrame:hover {{ background:#f0f9ff; }}"
            )
            row.setFixedHeight(60)
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(10, 8, 10, 8)
            rl.setSpacing(10)

            ic_lbl = QtWidgets.QLabel(icon)
            ic_lbl.setFixedSize(32, 32)
            ic_lbl.setAlignment(QtCore.Qt.AlignCenter)
            ic_lbl.setStyleSheet(
                f"background:{bg}; border-radius:16px; font-size:15px; border:none;"
            )
            rl.addWidget(ic_lbl)

            tw = QtWidgets.QWidget()
            tw.setStyleSheet("background:transparent; border:none;")
            tl = QtWidgets.QVBoxLayout(tw)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)

            msg = item.get("msg", "").lstrip("✅❌⚠️ℹ️ ")
            ml = QtWidgets.QLabel(msg)
            ml.setWordWrap(True)
            ml.setStyleSheet(
                "font-size:12px; font-weight:bold; color:#1e293b; "
                "background:transparent; border:none;"
            )
            tl.addWidget(ml)

            tl2 = QtWidgets.QLabel("🕐 " + item.get("time", ""))
            tl2.setStyleSheet(
                "font-size:10px; color:#94a3b8; background:transparent; border:none;"
            )
            tl.addWidget(tl2)
            rl.addWidget(tw, 1)

            pill = QtWidgets.QLabel(st)
            pill.setFixedHeight(18)
            pill.setAlignment(QtCore.Qt.AlignCenter)
            pill.setStyleSheet(
                f"background:{bg}; color:{accent}; font-size:9px; font-weight:bold; "
                f"border-radius:9px; padding:0 7px; border:none;"
            )
            rl.addWidget(pill)
            self.items_l.addWidget(row)

        self.items_l.addStretch()

    def show_below(self, widget):
        pos = widget.mapToGlobal(QtCore.QPoint(0, widget.height() + 6))
        screen_w = QtWidgets.QApplication.desktop().screenGeometry().width()
        x = pos.x() - self.width() + widget.width()
        if x + self.width() > screen_w:
            x = screen_w - self.width() - 10
        if x < 0:
            x = 0
        self.move(x, pos.y())
        self.show()
        self.raise_()


class SenderDashboard(QtWidgets.QMainWindow):
    # Signals define karein
    upload_finished = QtCore.pyqtSignal(str, str) # title, message
    update_progress = QtCore.pyqtSignal(int, str) # (value, status_text)
    show_gdrive_link = QtCore.pyqtSignal(str)
    sig_notification = QtCore.pyqtSignal(str, str)
    def __init__(self, user_name="Saliha Kiran"):
        super().__init__()
        self.user_name = user_name
        
        # Base directory = Sender_Project folder
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        
        # Files names for storage (inside Sender_Project folder)
        self.FILES_STORAGE = os.path.join(self.BASE_DIR, "my_files.json")
        self.HISTORY_STORAGE = os.path.join(self.BASE_DIR, "transfer_history.json")
        self.LOGS_STORAGE = os.path.join(self.BASE_DIR, "forensic_logs.json")
        self.NOTIFICATIONS_STORAGE = os.path.join(self.BASE_DIR, "notifications.json")
        self.NOTIF_STORAGE = os.path.join(self.BASE_DIR, "notifications.json")
        self.unread_count = 0
        self.notif_count = 0

        self.ACTIVITY_FILE = os.path.join(self.BASE_DIR, "sender_activity_log.txt")
        
        # Folders inside Sender_Project
        self.ENCRYPTED_VAULT_DIR = os.path.join(self.BASE_DIR, "Encrypted_Vault")
        self.VAULT_DIR = self.ENCRYPTED_VAULT_DIR  # alias used in do_encrypt_logic
        self.MY_KEYS_DIR = os.path.join(self.BASE_DIR, "my_keys")
        self.RECEIVER_KEYS_DIR = os.path.join(self.BASE_DIR, "receiver_keys")
        
        # Create folders if not exist
        for folder in [self.ENCRYPTED_VAULT_DIR, self.MY_KEYS_DIR, self.RECEIVER_KEYS_DIR]:
            if not os.path.exists(folder):
                os.makedirs(folder)
                print(f"✅ Created folder: {folder}")
        
        # --- EMAIL SETTINGS ---
        self.SENDER_EMAIL    = "furqant972@gmail.com"
        self.SENDER_PASSWORD = "xjcw zcmz sxzm rpjs"
        
        self.setWindowTitle("Secure Forensic Data Sharing Framework - Sender Panel")
        self.showMaximized()
        self.setStyleSheet("QMainWindow { background: #f0f6ff; }")
        
        self.existing_drives = self.get_current_drives()
        self.selected_file_path = ""
        
        mainWidget = QtWidgets.QWidget()
        mainWidget.setStyleSheet("background: #f0f6ff;")
        self.setCentralWidget(mainWidget)
        mainLayout = QtWidgets.QVBoxLayout(mainWidget)
        mainLayout.setContentsMargins(0,0,0,0)
        mainLayout.setSpacing(0)

        # ================= TOP RIBBON (NEW DARK UI) =================
        ribbon = QtWidgets.QFrame()
        ribbon.setFixedHeight(72)
        ribbon.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a56db, stop:0.5 #1e62f0, stop:1 #1a56db);
                border-bottom: 2px solid #60a5fa;
            }
        """)
        ribbonLayout = QtWidgets.QHBoxLayout(ribbon)
        ribbonLayout.setContentsMargins(20, 0, 20, 0)

        # Shield icon + title
        shield_lbl = QtWidgets.QLabel("🛡️")
        shield_lbl.setStyleSheet("font-size:28px; background:transparent;")
        ribbonLayout.addWidget(shield_lbl)

        title_block = QtWidgets.QVBoxLayout()
        title_block.setSpacing(0)
        title = QtWidgets.QLabel("SECURE FORENSIC DATA SHARING")
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#ffffff; background:transparent; letter-spacing:2px;")
        title_block.addWidget(title)
        ribbonLayout.addLayout(title_block)
        ribbonLayout.addStretch()

        # Notification button
        self.notif_btn = NotifBell(self)
        self.notif_count = 0
        self.notif_panel = NotifPanel(self)
        self.notif_panel.clear_btn.clicked.connect(self._clear_all_notifications)
        self.notif_btn.clicked.connect(self._toggle_notif_panel)
        ribbonLayout.addWidget(self.notif_btn)

        ribbonLayout.addSpacing(12)

        # User badge
        self.user_info = QtWidgets.QLabel(f"  👤  {self.user_name}  ")
        self.user_info.setStyleSheet("""
            font-size:13px; font-weight:bold;
            background: rgba(255,255,255,0.18);
            color: #ffffff;
            padding: 8px 14px;
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.40);
        """)
        ribbonLayout.addWidget(self.user_info)

        mainLayout.addWidget(ribbon)

        # ================= BODY =================
        bodyLayout = QtWidgets.QHBoxLayout()
        bodyLayout.setContentsMargins(0, 0, 0, 0)
        bodyLayout.setSpacing(0)
        mainLayout.addLayout(bodyLayout)

        # ================= SIDEBAR (NEW DARK UI) =================
        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a56db, stop:1 #1648c0);
                border-right: 2px solid #60a5fa;
            }
        """)
        sideLayout = QtWidgets.QVBoxLayout(sidebar)
        sideLayout.setContentsMargins(14, 20, 14, 20)
        sideLayout.setSpacing(8)


        def sideButton(text, icon, emoji=""):
            btn = QtWidgets.QPushButton(f"  {emoji}  {text}")
            btn.setIcon(self.style().standardIcon(icon))
            btn.setIconSize(QtCore.QSize(0, 0))  # hide default icon, use emoji
            btn.setFixedHeight(46)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #ffffff;
                    border: none;
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: bold;
                    color: #1a1a1a;
                    text-align: left;
                    padding-left: 12px;
                }
                QPushButton:hover {
                    background: #e8f0fe;
                    color: #1a56db;
                    border: none;
                }
            """)
            return btn

        self.btn_home     = sideButton("Home",             QtWidgets.QStyle.SP_ComputerIcon,             "🏠")
        self.btn_upload   = sideButton("Upload & Encrypt", QtWidgets.QStyle.SP_ArrowUp,                  "🔒")
        self.btn_transfer = sideButton("Transfer Data",    QtWidgets.QStyle.SP_DriveNetIcon,              "📡")
        self.btn_files    = sideButton("My Files",         QtWidgets.QStyle.SP_DirIcon,                  "📁")
        self.btn_history  = sideButton("Transfer History", QtWidgets.QStyle.SP_FileDialogDetailedView,   "📊")
        self.btn_doc      = sideButton("Case Documentation", QtWidgets.QStyle.SP_FileIcon,               "📋")
        self.btn_logs     = sideButton("Forensic Logs",    QtWidgets.QStyle.SP_MessageBoxInformation,    "📜")
        self.btn_hash_history = sideButton("View Hash History", QtWidgets.QStyle.SP_FileDialogDetailedView, "🔍")

        for b in [self.btn_home, self.btn_upload, self.btn_transfer, self.btn_files,
                  self.btn_history, self.btn_logs, self.btn_hash_history, self.btn_doc]:
            sideLayout.addWidget(b)

        sideLayout.addStretch()

        # Divider line
        div = QtWidgets.QFrame()
        div.setFrameShape(QtWidgets.QFrame.HLine)
        div.setStyleSheet("background: rgba(255,255,255,0.20); max-height:1px;")
        sideLayout.addWidget(div)
        sideLayout.addSpacing(8)

        self.logoutBtn = QtWidgets.QPushButton("Logout")
        self.logoutBtn.setFixedHeight(46)
        self.logoutBtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.logoutBtn.setStyleSheet("""
            QPushButton {
                background: #e53935;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
                text-align: center;
                padding-left: 0px;
            }
            QPushButton:hover {
                background: #c62828;
                color: white;
            }
        """)
        self.logoutBtn.clicked.connect(self.do_logout)
        sideLayout.addWidget(self.logoutBtn)

        bodyLayout.addWidget(sidebar)

        self.stack = QtWidgets.QStackedWidget()
        bodyLayout.addWidget(self.stack)

        self.setup_ui_pages()
        self.load_stored_data()

        self.btn_home.clicked.connect(self.go_home)
        self.btn_upload.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_transfer.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.btn_files.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.btn_logs.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.btn_hash_history.clicked.connect(self.show_hash_history_page)
        self.btn_history.clicked.connect(lambda: self.stack.setCurrentIndex(6))
        self.btn_doc.clicked.connect(self.show_case_form)
        self.upload_finished.connect(self.show_message_box)
        self.update_progress.connect(self.handle_ui_progress)
        self.show_gdrive_link.connect(self.show_gdrive_success)
        self.sig_notification.connect(self._add_notification_safe)
        self.original_hash   = ''
        self.temp_case_id    = 'N/A'
        self.temp_investigator = 'N/A'
        self.load_notifications_to_menu()



    def setup_ui_pages(self):
        # --- 1. HOME PAGE (LIGHT THEME UI) ---
        pg1 = QtWidgets.QWidget()
        pg1.setObjectName("HomePage")
        pg1.setStyleSheet("""
            #HomePage {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eff6ff, stop:0.5 #f8faff, stop:1 #eff6ff);
            }
        """)

        l1 = QtWidgets.QVBoxLayout(pg1)
        l1.setContentsMargins(35, 25, 35, 25)
        l1.setSpacing(20)

        # Header row
        hdr_row = QtWidgets.QHBoxLayout()

        # Header left: icon + title block
        hdr_left = QtWidgets.QHBoxLayout()
        hdr_left.setSpacing(10)
        hdr_icon = QtWidgets.QLabel("⚡")
        hdr_icon.setStyleSheet("font-size:26px; background:transparent;")
        hdr_left.addWidget(hdr_icon)

        hdr_text_block = QtWidgets.QVBoxLayout()
        hdr_text_block.setSpacing(1)
        header = QtWidgets.QLabel("Forensic Dashboard Overview")
        header.setStyleSheet("""
            font-size: 24px; font-weight: bold;
            color: #1e3a5f; background: transparent; letter-spacing:0.5px;
        """)
        hdr_text_block.addWidget(header)
        hdr_left.addLayout(hdr_text_block)
        hdr_row.addLayout(hdr_left)

        hdr_row.addStretch()

        # Date/time badge
        time_badge = QtWidgets.QFrame()
        time_badge.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 10px;
                border: 1px solid #bfdbfe;
            }
        """)
        time_badge_layout = QtWidgets.QHBoxLayout(time_badge)
        time_badge_layout.setContentsMargins(12, 6, 12, 6)
        time_lbl = QtWidgets.QLabel()
        time_lbl.setStyleSheet("font-size:12px; color:#4a5568; background:transparent; font-weight:bold;")
        from datetime import datetime
        time_lbl.setText(datetime.now().strftime("%d %b %Y  |  %H:%M"))
        time_badge_layout.addWidget(time_lbl)

        hdr_row.addWidget(time_badge)
        hdr_row.addSpacing(8)
        l1.addLayout(hdr_row)

        # Thin accent line under header
        accent_line = QtWidgets.QFrame()
        accent_line.setFrameShape(QtWidgets.QFrame.HLine)
        accent_line.setFixedHeight(2)
        accent_line.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1a56db, stop:0.5 #3b82f6, stop:1 transparent); border:none;")
        l1.addWidget(accent_line)

        # ---- STAT CARDS ----
        def home_card(title, emoji, value_color, border_color, bg_color):
            f = QtWidgets.QFrame()
            f.setFixedSize(185, 135)
            f.setStyleSheet(f"""
                QFrame {{
                    background: {bg_color};
                    border-radius: 16px;
                    border: 1.5px solid {border_color};
                }}
            """)
            shadow = QtWidgets.QGraphicsDropShadowEffect()
            shadow.setBlurRadius(18); shadow.setOffset(0, 3)
            shadow.setColor(QtGui.QColor(100, 120, 180, 55))
            f.setGraphicsEffect(shadow)

            v = QtWidgets.QVBoxLayout(f)
            v.setContentsMargins(18, 14, 18, 14)
            v.setSpacing(4)

            top = QtWidgets.QHBoxLayout()
            emo = QtWidgets.QLabel(emoji)
            emo.setStyleSheet("font-size:22px; background:transparent; border:none;")
            top.addWidget(emo)
            top.addStretch()

            lbl_value = QtWidgets.QLabel("0")
            lbl_value.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            lbl_value.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {value_color}; border: none; background: transparent;")
            top.addWidget(lbl_value)
            v.addLayout(top)

            v.addStretch()

            # Bottom divider
            div = QtWidgets.QFrame()
            div.setFrameShape(QtWidgets.QFrame.HLine)
            div.setFixedHeight(1)
            div.setStyleSheet(f"background: {border_color}; border:none; opacity:0.4;")
            v.addWidget(div)

            lbl_title = QtWidgets.QLabel(title.upper())
            lbl_title.setAlignment(QtCore.Qt.AlignLeft)
            lbl_title.setWordWrap(True)
            lbl_title.setStyleSheet(f"font-size: 10px; font-weight: bold; color: #64748b; border: none; background: transparent; letter-spacing:1.2px; padding-top:3px;")
            v.addWidget(lbl_title)

            return f, lbl_value

        card_files,   self.lbl_stat_files     = home_card("Files Prepared",  "📁", "#0ea5e9", "#bae6fd", "#f0f9ff")
        card_trans,   self.lbl_stat_transfers  = home_card("Total Transfers", "📡", "#6366f1", "#c7d2fe", "#eef2ff")
        card_success, self.lbl_stat_success    = home_card("Success Rate",    "✅", "#16a34a", "#bbf7d0", "#f0fdf4")
        card_susp,    self.lbl_stat_suspicious = home_card("Suspicious",      "⚠️", "#d97706", "#fde68a", "#fffbeb")
        card_fail,    self.lbl_stat_failed     = home_card("Failed",          "❌", "#dc2626", "#fecaca", "#fff5f5")

        h_layout = QtWidgets.QHBoxLayout()
        h_layout.setSpacing(16)
        h_layout.setAlignment(QtCore.Qt.AlignLeft)
        for c in [card_files, card_trans, card_success, card_susp, card_fail]:
            h_layout.addWidget(c)
        h_layout.addStretch()
        l1.addLayout(h_layout)

        # ---- RECENT ACTIVITY PANEL ----
        activity_panel = QtWidgets.QFrame()
        activity_panel.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 16px;
                border: 1.5px solid #bfdbfe;
            }
        """)
        shadow2 = QtWidgets.QGraphicsDropShadowEffect()
        shadow2.setBlurRadius(22); shadow2.setOffset(0, 4)
        shadow2.setColor(QtGui.QColor(100, 120, 180, 45))
        activity_panel.setGraphicsEffect(shadow2)

        apl = QtWidgets.QVBoxLayout(activity_panel)
        apl.setContentsMargins(22, 16, 22, 16)
        apl.setSpacing(10)

        act_hdr = QtWidgets.QHBoxLayout()

        # Panel title with left accent bar
        act_title_frame = QtWidgets.QFrame()
        act_title_frame.setStyleSheet("background:transparent; border:none;")
        act_title_layout = QtWidgets.QHBoxLayout(act_title_frame)
        act_title_layout.setContentsMargins(0, 0, 0, 0)
        act_title_layout.setSpacing(10)

        accent_bar = QtWidgets.QFrame()
        accent_bar.setFixedSize(4, 22)
        accent_bar.setStyleSheet("background: #1a56db; border-radius: 2px; border:none;")
        act_title_layout.addWidget(accent_bar)

        lbl_act = QtWidgets.QLabel("Recent Forensic Activity")
        lbl_act.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e3a5f; background:transparent;")
        act_title_layout.addWidget(lbl_act)

        act_hdr.addWidget(act_title_frame)
        act_hdr.addStretch()

        apl.addLayout(act_hdr)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setStyleSheet("background: #e2e8f0; max-height:1px; border:none;")
        apl.addWidget(sep)

        self.activity_list = QtWidgets.QListWidget()
        self.activity_list.setStyleSheet("""
            QListWidget {
                font-size: 13px; border: none;
                background: transparent; color: #374151;
                outline: none;
            }
            QListWidget::item {
                padding: 7px 6px;
                border-bottom: 1px solid #f1f5f9;
                border-radius: 6px;
                color: #374151;
            }
            QListWidget::item:hover {
                background: #f0f4ff;
                color: #1e3a5f;
            }
            QScrollBar:vertical {
                background: #f8faff; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #c7d2fe; border-radius: 3px;
            }
        """)
        apl.addWidget(self.activity_list)

        l1.addWidget(activity_panel, 1)
        self.stack.addWidget(pg1)

        # ================= 2. UPLOAD & ENCRYPT (NEW DARK UI) =================
        pg2 = QtWidgets.QWidget()
        pg2.setStyleSheet("background: #eff6ff;")
        l2 = QtWidgets.QVBoxLayout(pg2)
        l2.setContentsMargins(40, 30, 40, 30)

        encrypt_card = QtWidgets.QFrame()
        encrypt_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 18px;
                border: 1.5px solid #bfdbfe;
            }
        """)
        encrypt_layout = QtWidgets.QVBoxLayout(encrypt_card)
        encrypt_layout.setContentsMargins(30, 28, 30, 28)
        encrypt_layout.setSpacing(22)

        header_widget = QtWidgets.QWidget()
        header_widget.setStyleSheet("background:transparent;")
        header_h_layout = QtWidgets.QHBoxLayout(header_widget)
        header_h_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QtWidgets.QLabel("🔒")
        icon_label.setStyleSheet("font-size: 30px; background: transparent;")
        header_h_layout.addWidget(icon_label)

        header_title = QtWidgets.QLabel("Secure Encryption Engine")
        header_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background: transparent; letter-spacing:1px;")
        header_h_layout.addWidget(header_title)
        header_h_layout.addStretch()
        badge = QtWidgets.QLabel("  AES-256  ")
        badge.setStyleSheet("""
            font-size:11px; font-weight:bold; color:#1a56db;
            background: #dbeafe;
            border: 1px solid #93c5fd;
            border-radius: 10px; padding: 3px 8px;
        """)
        header_h_layout.addWidget(badge)
        encrypt_layout.addWidget(header_widget)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("background: rgba(255,255,255,0.20); max-height:1px;")
        encrypt_layout.addWidget(line)

        GS = """
            QGroupBox {
                font-weight: bold; color: #1a56db;
                border: 1.5px solid #93c5fd;
                border-radius: 12px; margin-top: 12px;
                padding-top: 15px; font-size: 13px;
                background: #eff6ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 15px; padding: 0 8px;
            }
        """

        file_section = QtWidgets.QGroupBox("📁  1. FORENSIC DATA SOURCE")
        file_section.setStyleSheet(GS)
        file_layout = QtWidgets.QHBoxLayout(file_section)
        file_layout.setContentsMargins(15, 20, 15, 15)
        file_layout.setSpacing(15)

        self.in_path = QtWidgets.QLineEdit()
        self.in_path.setFixedHeight(48)
        self.in_path.setPlaceholderText("📁  Select forensic file to encrypt...")
        self.in_path.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #93c5fd;
                border-radius: 10px;
                padding: 10px 15px;
                font-size: 13px;
                background: #f8fbff;
                color: #1e3a5f;
            }
            QLineEdit:focus {
                border: 1.5px solid #1a56db;
                background: #eff6ff;
            }
        """)
        file_layout.addWidget(self.in_path)

        btn_br = QtWidgets.QPushButton("📂  Browse")
        btn_br.setFixedSize(120, 48)
        btn_br.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                border: 1.5px solid #1a56db;
                border-radius: 10px;
                font-weight: bold;
                font-size: 13px;
                color: #1a56db;
            }
            QPushButton:hover {
                background: #1a56db;
                color: #ffffff;
                border-color: #1a56db;
            }
        """)
        btn_br.clicked.connect(self.do_browse)
        file_layout.addWidget(btn_br)
        encrypt_layout.addWidget(file_section)

        key_section = QtWidgets.QGroupBox("🔑  2. SECURITY TOKEN (AES-256 KEY)")
        key_section.setStyleSheet(GS)
        key_layout = QtWidgets.QHBoxLayout(key_section)
        key_layout.setContentsMargins(15, 20, 15, 15)
        key_layout.setSpacing(15)

        self.in_key = QtWidgets.QLineEdit()
        self.in_key.setFixedHeight(48)
        self.in_key.setPlaceholderText("🔑  Enter 32-character AES key or click Generate")
        self.in_key.setStyleSheet("""
            QLineEdit {
                border: 1px solid rgba(59,130,246,0.35);
                border-radius: 10px;
                padding: 10px 15px;
                font-size: 13px;
                font-family: monospace;
                background: #f8fbff;
                color: #1a56db;
            }
            QLineEdit:focus {
                border: 1.5px solid #1a56db;
                background: #eff6ff;
            }
        """)
        key_layout.addWidget(self.in_key)

        self.btn_gk = QtWidgets.QPushButton("✨  Generate")
        self.btn_gk.setFixedSize(120, 48)
        self.btn_gk.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                border: 1.5px solid #60a5fa;
                border-radius: 10px;
                font-weight: bold;
                font-size: 13px;
                color: #2563eb;
            }
            QPushButton:hover {
                background: #2563eb;
                border-color: #2563eb;
                color: white;
            }
        """)
        self.btn_gk.clicked.connect(self.do_key)
        key_layout.addWidget(self.btn_gk)
        encrypt_layout.addWidget(key_section)

        btn_proc = QtWidgets.QPushButton("  🔒   START SECURE ENCRYPTION")
        btn_proc.setFixedHeight(58)
        btn_proc.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0369a1, stop:1 #00d4ff);
                color: #f8fafc;
                font-size: 15px;
                font-weight: bold;
                border-radius: 12px;
                border: none;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00d4ff, stop:1 #0369a1);
            }
        """)
        btn_proc.clicked.connect(self.do_encrypt_logic)
        encrypt_layout.addWidget(btn_proc)

        l2.addWidget(encrypt_card)
        l2.addStretch()
        self.stack.addWidget(pg2)

        # ================= 3. TRANSFER DATA (CLEAN PROFESSIONAL) =================
        pg3 = QtWidgets.QWidget()
        pg3.setStyleSheet("background: #eff6ff;")
        l3 = QtWidgets.QVBoxLayout(pg3)
        l3.setContentsMargins(40, 30, 40, 30)
        
        transfer_card = QtWidgets.QFrame()
        transfer_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 20px;
                border: 1.5px solid #bfdbfe;
            }
        """)
        transfer_layout = QtWidgets.QVBoxLayout(transfer_card)
        transfer_layout.setContentsMargins(35, 30, 35, 35)
        transfer_layout.setSpacing(30)
        
        # Title
        title_label = QtWidgets.QLabel("Transfer Protocol Selection")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a56db;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        transfer_layout.addWidget(title_label)
        
        # Row 1: USB and HDD
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(30)
        row1.setAlignment(QtCore.Qt.AlignCenter)
        
        usb_btn = QtWidgets.QPushButton("💾  USB")
        usb_btn.setFixedSize(180, 55)
        usb_btn.setCursor(QtCore.Qt.PointingHandCursor)
        usb_btn.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                border: 1.5px solid #1a56db;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                color: #1a56db;
            }
            QPushButton:hover {
                background: #1a56db;
                color: white;
            }
        """)
        usb_btn.clicked.connect(lambda: self.do_transfer_logic("USB"))
        row1.addWidget(usb_btn)
        
        hdd_btn = QtWidgets.QPushButton("💽  HDD")
        hdd_btn.setFixedSize(180, 55)
        hdd_btn.setCursor(QtCore.Qt.PointingHandCursor)
        hdd_btn.setStyleSheet("""
            QPushButton {
                background: #f0f6ff;
                border: 1.5px solid #3b82f6;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                color: #2563eb;
            }
            QPushButton:hover {
                background: #2563eb;
                color: white;
            }
        """)
        hdd_btn.clicked.connect(lambda: self.do_transfer_logic("HDD"))
        row1.addWidget(hdd_btn)
        transfer_layout.addLayout(row1)
        
        # Row 2: LAN and Email
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(30)
        row2.setAlignment(QtCore.Qt.AlignCenter)
        
        lan_btn = QtWidgets.QPushButton("🌐  LAN")
        lan_btn.setFixedSize(180, 55)
        lan_btn.setCursor(QtCore.Qt.PointingHandCursor)
        lan_btn.setStyleSheet("""
            QPushButton {
                background: #eef2ff;
                border: 1.5px solid #6366f1;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                color: #4f46e5;
            }
            QPushButton:hover {
                background: #4f46e5;
                color: white;
            }
        """)
        lan_btn.clicked.connect(lambda: self.do_transfer_logic("LAN"))
        row2.addWidget(lan_btn)
        
        email_btn = QtWidgets.QPushButton("📧  Email")
        email_btn.setFixedSize(180, 55)
        email_btn.setCursor(QtCore.Qt.PointingHandCursor)
        email_btn.setStyleSheet("""
            QPushButton {
                background: #fef2f2;
                border: 1.5px solid #dc2626;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                color: #dc2626;
            }
            QPushButton:hover {
                background: #dc2626;
                color: white;
            }
        """)
        email_btn.clicked.connect(lambda: self.do_transfer_logic("Email"))
        row2.addWidget(email_btn)
        transfer_layout.addLayout(row2)
        
        # Row 3: Google Drive (centered)
        row3 = QtWidgets.QHBoxLayout()
        row3.setAlignment(QtCore.Qt.AlignCenter)
        
        gdrive_btn = QtWidgets.QPushButton("☁️  Google Drive")
        gdrive_btn.setFixedSize(200, 55)
        gdrive_btn.setCursor(QtCore.Qt.PointingHandCursor)
        gdrive_btn.setStyleSheet("""
            QPushButton {
                background: #fff7ed;
                border: 1.5px solid #f97316;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
                color: #ea6d0a;
            }
            QPushButton:hover {
                background: #f97316;
                color: white;
            }
        """)
        gdrive_btn.clicked.connect(lambda: self.do_transfer_logic("Google Drive"))
        row3.addWidget(gdrive_btn)
        transfer_layout.addLayout(row3)
        
        # Progress Section
        progress_frame = QtWidgets.QFrame()
        progress_frame.setStyleSheet("""
            QFrame {
                background: #eff6ff;
                border-radius: 12px;
                margin-top: 10px;
            }
        """)
        progress_layout = QtWidgets.QVBoxLayout(progress_frame)
        progress_layout.setContentsMargins(20, 15, 20, 15)
        progress_layout.setSpacing(10)
        
        # Status with icon
        status_layout = QtWidgets.QHBoxLayout()
        status_icon = QtWidgets.QLabel("⚡")
        status_icon.setStyleSheet("font-size: 14px;")
        status_layout.addWidget(status_icon)
        
        self.lbl_t = QtWidgets.QLabel("Status: Ready to transfer")
        self.lbl_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a56db;")
        status_layout.addWidget(self.lbl_t)
        status_layout.addStretch()
        progress_layout.addLayout(status_layout)
        
        # Progress bar with percentage text
        self.p_bar = QtWidgets.QProgressBar()
        self.p_bar.setFixedHeight(18)
        self.p_bar.setFormat("%p%")  # This shows percentage
        self.p_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #dbeafe;
                border-radius: 9px;
                text-align: center;
                font-size: 11px;
                font-weight: bold;
                color: #1a56db;
            }
            QProgressBar::chunk {
                background-color: #1a56db;
                border-radius: 9px;
            }
        """)
        progress_layout.addWidget(self.p_bar)
        
        transfer_layout.addWidget(progress_frame)
        
        l3.addWidget(transfer_card)
        l3.addStretch()
        self.stack.addWidget(pg3)

        # ================= 4. MY FILES (NEW DARK UI) =================
        pg4 = QtWidgets.QWidget()
        pg4.setStyleSheet("background: #eff6ff;")
        l4 = QtWidgets.QVBoxLayout(pg4)
        l4.setContentsMargins(30, 28, 30, 28)
        l4.setSpacing(14)

        files_hdr = QtWidgets.QHBoxLayout()
        files_title = QtWidgets.QLabel("📁  My Encrypted Files")
        files_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background:transparent;")
        files_hdr.addWidget(files_title)
        files_hdr.addStretch()
        files_badge = QtWidgets.QLabel("  AES-256 VAULT  ")
        files_badge.setStyleSheet("""
            font-size:11px; font-weight:bold; color:#34d399;
            background: rgba(52,211,153,0.10); border: 1px solid rgba(52,211,153,0.30);
            border-radius:10px; padding:3px 8px;
        """)
        files_hdr.addWidget(files_badge)
        l4.addLayout(files_hdr)

        # --- Search bar + Refresh button row ---
        files_search_row = QtWidgets.QHBoxLayout()
        files_search_row.setSpacing(10)

        self.files_search_input = QtWidgets.QLineEdit()
        self.files_search_input.setPlaceholderText("🔍  Search files by name, method, size or date...")
        self.files_search_input.setFixedHeight(40)
        self.files_search_input.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #93c5fd;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
                background: #ffffff;
                color: #1e3a5f;
            }
            QLineEdit:focus {
                border: 1.5px solid #1a56db;
                background: #eff6ff;
            }
        """)

        files_refresh_btn = QtWidgets.QPushButton("🔄  Refresh")
        files_refresh_btn.setFixedSize(110, 40)
        files_refresh_btn.setCursor(QtCore.Qt.PointingHandCursor)
        files_refresh_btn.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                color: #1a56db;
                border: 1.5px solid #1a56db;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1a56db;
                color: #ffffff;
                border-color: #1a56db;
            }
        """)

        files_search_row.addWidget(self.files_search_input)
        files_search_row.addWidget(files_refresh_btn)
        l4.addLayout(files_search_row)

        self.tab_files = QtWidgets.QTableWidget(0, 5)
        self.tab_files.setColumnCount(5)
        self.tab_files.setHorizontalHeaderLabels(["Filename", "Method", "Size", "Date", "Action"])
        self.tab_files.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tab_files.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border-radius: 12px;
                border: 1.5px solid #bfdbfe;
                color: #1e3a5f;
                gridline-color: #dbeafe;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #1a56db;
                padding: 10px;
                font-weight: bold;
                color: #ffffff;
                border: none;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #dbeafe; color: #1a56db; }
        """)

        # Search filter logic
        def filter_files_table(text):
            for row in range(self.tab_files.rowCount()):
                match = False
                for col in range(self.tab_files.columnCount() - 1):  # skip Action col
                    item = self.tab_files.item(row, col)
                    if item and text.lower() in item.text().lower():
                        match = True
                        break
                self.tab_files.setRowHidden(row, not match)

        self.files_search_input.textChanged.connect(filter_files_table)

        # Refresh button logic
        def refresh_files_table():
            self.tab_files.setRowCount(0)
            if os.path.exists(self.FILES_STORAGE):
                with open(self.FILES_STORAGE, 'r') as f:
                    try:
                        for item in json.load(f):
                            self._add_file_row(
                                item.get('filename',''),
                                item.get('method','AES-256'),
                                item.get('size','N/A'),
                                item.get('date','')
                            )
                    except Exception as e:
                        print(f"Refresh error: {e}")
            self.files_search_input.clear()
            self.update_dashboard_stats()

        files_refresh_btn.clicked.connect(refresh_files_table)

        l4.addWidget(self.tab_files)
        self.stack.addWidget(pg4)

        # ================= 5. FORENSIC LOGS (NEW DARK UI) =================
        pg_logs = QtWidgets.QWidget()
        pg_logs.setStyleSheet("background: #eff6ff;")
        l_logs = QtWidgets.QVBoxLayout(pg_logs)
        l_logs.setContentsMargins(30, 28, 30, 28)
        l_logs.setSpacing(14)

        logs_header = QtWidgets.QHBoxLayout()
        logs_title = QtWidgets.QLabel("📜  Detailed Forensic Audit Logs")
        logs_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background:transparent;")
        logs_header.addWidget(logs_title)
        logs_header.addStretch()

        export_btn = QtWidgets.QPushButton("📎  Export to CSV")
        export_btn.setFixedSize(155, 38)
        export_btn.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                color: #1a56db;
                border: 1.5px solid #1a56db;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1a56db;
                color: #ffffff;
                border-color: #1a56db;
            }
        """)
        export_btn.clicked.connect(self.export_logs_to_csv)
        logs_header.addWidget(export_btn)
        l_logs.addLayout(logs_header)

        self.log_table = QtWidgets.QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["Event ID", "Activity Description", "Security Level"])
        self.log_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.log_table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border-radius: 12px;
                border: 1.5px solid #bfdbfe;
                color: #1e3a5f;
                gridline-color: #dbeafe;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #1a56db;
                padding: 10px;
                font-weight: bold;
                color: #ffffff;
                border: none;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #dbeafe; color: #1a56db; }
        """)

        l_logs.addWidget(self.setup_search_bar(self.log_table, "Search logs..."))
        l_logs.addWidget(self.log_table)
        self.stack.addWidget(pg_logs)

        # ================= 6. INTEGRITY CHECK (NEW DARK UI) =================
        pg_int = QtWidgets.QWidget()
        pg_int.setStyleSheet("background: #eff6ff;")
        l_int = QtWidgets.QVBoxLayout(pg_int)
        l_int.setContentsMargins(80, 40, 80, 40)

        int_box = QtWidgets.QGroupBox("🔒  Data Integrity Verification")
        int_box.setMinimumHeight(560)
        int_box.setStyleSheet("""
            QGroupBox {
                font-size: 17px; font-weight: bold; color: #1a56db;
                padding-top: 35px;
                border: 1.5px solid #93c5fd;
                border-radius: 16px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px;
                background: #ffffff;
            }
        """)

        il = QtWidgets.QVBoxLayout(int_box)
        il.setContentsMargins(40, 40, 40, 40)
        il.setSpacing(16)

        self.in_check_path = QtWidgets.QLineEdit()
        self.in_check_path.setPlaceholderText("  Select file to verify integrity...")
        self.in_check_path.setFixedHeight(46)
        self.in_check_path.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #93c5fd; border-radius: 8px;
                font-size: 14px; padding-left: 12px;
                background: #f8fbff; color: #1e3a5f;
            }
            QLineEdit:focus { border: 1.5px solid #1a56db; }
        """)

        btn_sel = QtWidgets.QPushButton("📁  Select File")
        btn_sel.setFixedHeight(46)
        btn_sel.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                border: 1.5px solid #1a56db;
                border-radius: 8px;
                font-weight: bold;
                color: #1a56db;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #1a56db;
                color: #ffffff;
                border-color: #1a56db;
            }
        """)
        btn_sel.clicked.connect(self.select_file_for_hash)

        btn_calc = QtWidgets.QPushButton("🔄  Generate Forensic Hash")
        btn_calc.setFixedHeight(52)
        btn_calc.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0369a1,stop:1 #00d4ff);
                color: #f8fafc;
                font-weight: bold;
                font-size: 15px;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00d4ff,stop:1 #0369a1);
            }
        """)
        btn_calc.clicked.connect(self.calculate_hash_logic)

        self.out_hash = QtWidgets.QLabel("Status: System Ready")
        self.out_hash.setWordWrap(True)
        self.out_hash.setMinimumHeight(110)
        self.out_hash.setAlignment(QtCore.Qt.AlignCenter)
        self.out_hash.setStyleSheet("""
            padding: 15px;
            background: #eff6ff;
            border-radius: 10px;
            color: #1d4ed8;
            border: 1px dashed rgba(0,212,255,0.35);
            font-family: 'Consolas'; font-size: 14px;
        """)

        btn_copy = QtWidgets.QPushButton("📋  Copy Hash to Clipboard")
        btn_copy.setFixedHeight(42)
        btn_copy.setCursor(QtCore.Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                color: #1a56db;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
                border: 1.5px solid #1a56db;
            }
            QPushButton:hover {
                background: #1a56db;
                border-color: #1a56db;
                color: white;
            }
        """)
        btn_copy.clicked.connect(self.copy_hash_to_clipboard)

        il.addWidget(self.in_check_path)
        il.addWidget(btn_sel)
        il.addWidget(btn_calc)
        il.addWidget(self.out_hash)
        il.addWidget(btn_copy)
        il.addStretch()

        l_int.addWidget(int_box)
        l_int.addStretch()
        self.stack.addWidget(pg_int)

        # ================= 7. TRANSFER HISTORY (NEW DARK UI) =================
        pg_hist = QtWidgets.QWidget()
        pg_hist.setStyleSheet("background: #eff6ff;")
        l_hist = QtWidgets.QVBoxLayout(pg_hist)
        l_hist.setContentsMargins(30, 28, 30, 28)
        l_hist.setSpacing(14)

        hist_header = QtWidgets.QHBoxLayout()
        hist_title = QtWidgets.QLabel("📊  Transfer History Logs")
        hist_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background:transparent;")
        hist_header.addWidget(hist_title)
        hist_header.addStretch()

        clear_btn = QtWidgets.QPushButton("🗑️  Clear All History")
        clear_btn.setFixedSize(160, 38)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239,68,68,0.12);
                color: #f87171;
                border: 1px solid rgba(239,68,68,0.35);
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(239,68,68,0.25);
                border-color: #ef4444;
                color: white;
            }
        """)
        clear_btn.clicked.connect(self.clear_transfer_history)
        hist_header.addWidget(clear_btn)
        l_hist.addLayout(hist_header)

        self.tab_hist = QtWidgets.QTableWidget(0, 5)
        self.tab_hist.setColumnCount(5)
        self.tab_hist.setHorizontalHeaderLabels(["Timestamp", "File", "Protocol", "Destination", "Status"])
        self.tab_hist.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tab_hist.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border-radius: 12px;
                border: 1.5px solid #bfdbfe;
                color: #1e3a5f;
                gridline-color: #dbeafe;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #1a56db;
                padding: 10px;
                font-weight: bold;
                color: #ffffff;
                border: none;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #dbeafe; color: #1a56db; }
        """)

        l_hist.addWidget(self.setup_search_bar(self.tab_hist, "Search history..."))
        l_hist.addWidget(self.tab_hist)
        self.stack.addWidget(pg_hist)

        # ================= 8. HASH HISTORY PAGE (stack index 7) =================
        pg_hash_hist = QtWidgets.QWidget()
        pg_hash_hist.setStyleSheet("background: #eff6ff;")
        l_hash_hist = QtWidgets.QVBoxLayout(pg_hash_hist)
        l_hash_hist.setContentsMargins(30, 28, 30, 28)
        l_hash_hist.setSpacing(14)

        hh_header = QtWidgets.QHBoxLayout()
        hh_icon = QtWidgets.QLabel("🔍")
        hh_icon.setStyleSheet("font-size:22px; background:transparent;")
        hh_header.addWidget(hh_icon)
        hh_title = QtWidgets.QLabel("Hash Verification History")
        hh_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background:transparent;")
        hh_header.addWidget(hh_title)
        hh_header.addStretch()
        l_hash_hist.addLayout(hh_header)

        hh_line = QtWidgets.QFrame()
        hh_line.setFrameShape(QtWidgets.QFrame.HLine)
        hh_line.setFixedHeight(2)
        hh_line.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1a56db, stop:0.5 #3b82f6, stop:1 transparent); border:none;")
        l_hash_hist.addWidget(hh_line)

        self.hash_hist_table = QtWidgets.QTableWidget(0, 3)
        self.hash_hist_table.setHorizontalHeaderLabels(["Event ID", "Activity", "Level"])
        self.hash_hist_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.hash_hist_table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border-radius: 12px;
                border: 1.5px solid #bfdbfe;
                color: #1e3a5f;
                gridline-color: #dbeafe;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #1a56db;
                padding: 10px;
                font-weight: bold;
                color: #ffffff;
                border: none;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #dbeafe; color: #1a56db; }
        """)
        l_hash_hist.addWidget(self.setup_search_bar(self.hash_hist_table, "Search hash history..."))
        l_hash_hist.addWidget(self.hash_hist_table)
        self.stack.addWidget(pg_hash_hist)

    def show_message_box(self, title, msg): QtWidgets.QMessageBox.information(self, title, msg)
    def show_msg(self, title, msg):         QtWidgets.QMessageBox.information(self, title, msg)
    def handle_ui_progress(self, v, t):    self.p_bar.setValue(v); self.lbl_t.setText(t)
    def get_current_drives(self):
        return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

    def do_logout(self):
        # ── Update logout_time in login_history ───────────────
        try:
            conn = sqlite3.connect(DB_PATH)
            cur  = conn.cursor()
            cur.execute(
                "UPDATE login_history SET logout_time=? "
                "WHERE id = ("
                "  SELECT id FROM login_history "
                "  WHERE username=? AND logout_time IS NULL "
                "  ORDER BY id DESC LIMIT 1"
                ")",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.user_name)
            )
            conn.commit(); conn.close()
        except Exception as e:
            print(f"[logout_time] {e}")
        self.close()
        try:
            from app import MainAppWindow
            self.landing = MainAppWindow(); self.landing.showMaximized()
        except Exception as e:
            print(f"Logout error: {e}")

    def go_home(self):
        self.update_dashboard_stats(); self.stack.setCurrentIndex(0)

    def save_data_to_file(self, filename, data):
        try:
            existing = []
            if os.path.exists(filename):
                with open(filename, 'r') as f: existing = json.load(f)
            existing.append(data)
            with open(filename, 'w') as f: json.dump(existing, f, indent=4)
        except Exception as e:
            print(f"Save error: {e}")

    def _add_file_row(self, filename, method, size, date):
        """Add a row to tab_files with a delete button in the Action column."""
        r = self.tab_files.rowCount()
        self.tab_files.insertRow(r)
        self.tab_files.setItem(r, 0, QtWidgets.QTableWidgetItem(filename))
        self.tab_files.setItem(r, 1, QtWidgets.QTableWidgetItem(method))
        self.tab_files.setItem(r, 2, QtWidgets.QTableWidgetItem(size))
        self.tab_files.setItem(r, 3, QtWidgets.QTableWidgetItem(date))

        del_btn = QtWidgets.QPushButton("🗑️  Delete")
        del_btn.setCursor(QtCore.Qt.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239,68,68,0.12);
                color: #f87171;
                border: 1px solid rgba(239,68,68,0.35);
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: rgba(239,68,68,0.28);
                border-color: #ef4444;
                color: white;
            }
        """)

        def make_delete(row_ref):
            def do_delete():
                # Find current row index of this button
                btn = self.sender()
                for i in range(self.tab_files.rowCount()):
                    w = self.tab_files.cellWidget(i, 4)
                    if w == btn:
                        confirm = QtWidgets.QMessageBox.question(
                            self, "Delete Record",
                            f"Delete record '{self.tab_files.item(i, 0).text()}' from list?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            QtWidgets.QMessageBox.No
                        )
                        if confirm == QtWidgets.QMessageBox.Yes:
                            self.tab_files.removeRow(i)
                            self._save_files_storage()
                            self.update_dashboard_stats()
                        break
            return do_delete

        del_btn.clicked.connect(make_delete(r))
        self.tab_files.setCellWidget(r, 4, del_btn)

    def _save_files_storage(self):
        """Re-save FILES_STORAGE from current table rows."""
        try:
            data = []
            for i in range(self.tab_files.rowCount()):
                data.append({
                    "filename": self.tab_files.item(i, 0).text() if self.tab_files.item(i, 0) else "",
                    "method":   self.tab_files.item(i, 1).text() if self.tab_files.item(i, 1) else "",
                    "size":     self.tab_files.item(i, 2).text() if self.tab_files.item(i, 2) else "",
                    "date":     self.tab_files.item(i, 3).text() if self.tab_files.item(i, 3) else "",
                })
            with open(self.FILES_STORAGE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Save files storage error: {e}")

    def load_stored_data(self):
        if os.path.exists(self.FILES_STORAGE):
            with open(self.FILES_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        self._add_file_row(
                            item.get('filename',''),
                            item.get('method','AES-256'),
                            item.get('size','N/A'),
                            item.get('date','')
                        )
                except Exception as e: print(f"Files load: {e}")
        if os.path.exists(self.HISTORY_STORAGE):
            with open(self.HISTORY_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        r = self.tab_hist.rowCount(); self.tab_hist.insertRow(r)
                        self.tab_hist.setItem(r,0,QtWidgets.QTableWidgetItem(item.get('time','')))
                        self.tab_hist.setItem(r,1,QtWidgets.QTableWidgetItem(item.get('file','')))
                        self.tab_hist.setItem(r,2,QtWidgets.QTableWidgetItem(item.get('protocol','')))
                        self.tab_hist.setItem(r,3,QtWidgets.QTableWidgetItem(item.get('destination','N/A')))
                        st = item.get('status',''); si = QtWidgets.QTableWidgetItem(st)
                        if "Success" in st: si.setForeground(QtGui.QColor("#16a34a"))
                        elif "Suspicious" in st:
                            si.setForeground(QtGui.QColor("#991b1b"))
                            fnt=QtGui.QFont(); fnt.setBold(True); si.setFont(fnt)
                        elif "Failed" in st: si.setForeground(QtGui.QColor("#ef4444"))
                        self.tab_hist.setItem(r,4,si)
                except Exception as e: print(f"History load: {e}")
        if os.path.exists(self.LOGS_STORAGE):
            with open(self.LOGS_STORAGE, 'r') as f:
                try:
                    for item in json.load(f):
                        r = self.log_table.rowCount(); self.log_table.insertRow(r)
                        self.log_table.setItem(r,0,QtWidgets.QTableWidgetItem(item.get('event_id','')))
                        self.log_table.setItem(r,1,QtWidgets.QTableWidgetItem(item.get('activity','')))
                        self.log_table.setItem(r,2,QtWidgets.QTableWidgetItem(item.get('level','')))
                        self.activity_list.addItem(f"● {item.get('activity','')}")
                except Exception as e: print(f"Logs load: {e}")
        self.update_dashboard_stats()

    def update_dashboard_stats(self):
        self.lbl_stat_files.setText(str(self.tab_files.rowCount()))
        n = self.tab_hist.rowCount(); self.lbl_stat_transfers.setText(str(n))
        s = su = f = 0
        for i in range(n):
            it = self.tab_hist.item(i, 4)
            if it:
                t = it.text()
                if "Success" in t: s += 1
                elif "Suspicious" in t: su += 1
                elif "Failed" in t: f += 1
        self.lbl_stat_suspicious.setText(str(su)); self.lbl_stat_failed.setText(str(f))
        self.lbl_stat_success.setText(f"{int((s/n)*100)}%" if n > 0 else "0%")

    def do_browse(self):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Forensic File")
        if fp: self.in_path.setText(fp); self.original_selection_path = fp

    def do_key(self):
        if not self.in_path.text().strip():
            QtWidgets.QMessageBox.warning(self, "Required", "⚠️ Select a file first!"); return
        if self.in_key.text().strip():
            r = QtWidgets.QMessageBox.question(self,'Change Key?','Replace existing key?',
                QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if r == QtWidgets.QMessageBox.No: return
        key = ''.join(random.choices("0123456789abcdef", k=32))
        self.in_key.setText(key)
        self.add_forensic_log("New AES key generated for session.", "LOW")

    def do_encrypt_logic(self):
        input_path = self.in_path.text()
        key_text   = self.in_key.text()
        filename   = os.path.basename(input_path) if input_path else "Unknown"

        if not input_path or not key_text:
            QtWidgets.QMessageBox.warning(self,"Input Error","Provide both file and 32-char key."); return
        if len(key_text) != 32:
            QtWidgets.QMessageBox.warning(self,"Key Error","AES key must be exactly 32 characters."); return
        try:
            sha = hashlib.sha256()
            with open(input_path, 'rb') as f:
                for block in iter(lambda: f.read(4096), b""): sha.update(block)
            self.original_hash = sha.hexdigest()

            fsz      = os.path.getsize(input_path)
            fsz_str  = f"{fsz/1024:.2f} KB" if fsz < 1024*1024 else f"{fsz/(1024*1024):.2f} MB"
            orig_name = os.path.basename(input_path)
            enc_name  = f"ENCRYPTED_{orig_name}.aes"
            dest      = os.path.join(self.VAULT_DIR, enc_name)

            with open(dest + ".key.txt", 'w') as kf: kf.write(key_text)

            key    = key_text.encode(); iv = os.urandom(16)
            with open(input_path, 'rb') as f: data = f.read()
            padder = padding.PKCS7(128).padder()
            padded = padder.update(data) + padder.finalize()
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            enc    = cipher.encryptor()
            with open(dest, 'wb') as f: f.write(iv + enc.update(padded) + enc.finalize())

            self.selected_file_path = dest
            date_str = QtCore.QDate.currentDate().toString()

            self._add_file_row(enc_name, "AES-256", fsz_str, date_str)
            self.save_data_to_file(self.FILES_STORAGE,
                {"filename":enc_name,"method":"AES-256","size":fsz_str,"date":date_str})

            write_audit_log(
                username=self.user_name, role="Sender",
                action="FILE_ENCRYPTED", method="AES-256",
                file_name=enc_name,
                details=f"SHA-256: {self.original_hash} | Original: {orig_name}"
            )

            # ── forensic_files table ──────────────────────────────
            # try:
            #     conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
            #     cur  = conn.cursor()
            #     cur.execute(
            #         "INSERT INTO forensic_files "
            #         "(case_id, file_name, original_hash, file_size, sender_name) "
            #         "VALUES (?, ?, ?, ?, ?)",
            #         (getattr(self, 'temp_case_id', 'N/A'),
            #          orig_name, self.original_hash, fsz_str, self.user_name)
            #     )
            #     conn.commit(); conn.close()
            # except Exception as e:
            #     print(f"[forensic_files] {e}")

            self.activity_list.addItem(f"● File Secured: {enc_name}")
            QtWidgets.QMessageBox.information(self, "Encrypted ✅",
                f"'{orig_name}' encrypted successfully!\n\n"
                f"SHA-256 Hash: {self.original_hash[:32]}...\n"
                f"Saved to Vault: {dest}")

            QtCore.QTimer.singleShot(300, self.show_case_form)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self,"Encryption Failed",str(e))

    def do_transfer_logic(self, method):
        if not self.selected_file_path:
            QtWidgets.QMessageBox.warning(self,"Error","Encrypt a file first."); return

        fn  = os.path.basename(self.selected_file_path).lower()
        fsz = os.path.getsize(self.selected_file_path)
        status = "Success"
        if any(fn.endswith(e) for e in ['.exe','.bat','.py','.msi','.sh','.cmd','.js']):
            status = "Suspicious (Unsafe)"
        elif fsz == 0:
            status = "Failed (Empty File)"
        if status != "Success":
            QtWidgets.QMessageBox.critical(self,"Forensic Alert",f"'{fn}' is {status}.")
            self.add_notification(f"{method} Transfer",f"Result: {status}",status)
            self.add_to_history(method,status); return

        receiver_email, ok = QtWidgets.QInputDialog.getText(
            self, 'Identify Receiver',
            f'Transfer Method: {method}\n\n'
            'Enter \'s registered email address\n'
            '(must match the email they used to sign up in SDTF):'
        )
        if not ok or not receiver_email.strip():
            self.lbl_t.setText("Status: Cancelled"); return
        receiver_email = receiver_email.strip()

        result = self._create_db_record(receiver_email, method)
        if result is None:
            return
        receiver_name, transfer_id = result

        self.lbl_t.setText(f"Status: Initiating {method}...")
        self.p_bar.setValue(0)

        if method == "Email":
            self._send_blind_notification(receiver_email, receiver_name)
        elif method in ["USB", "HDD"]:
            self.existing_drives = self.get_current_drives()
            self.monitor_timer   = QtCore.QTimer()
            self.monitor_timer.timeout.connect(lambda: self.detect_new_hardware(method))
            self.monitor_timer.start(1000)
            QtWidgets.QMessageBox.information(
                self, "Hardware Scan",
                f"DB record created for: {receiver_name}\n\n"
                f"Now plug in your {method}.\nFile will be copied automatically."
            )
        elif method == "LAN":
            ip, ok2 = QtWidgets.QInputDialog.getText(
                self, 'LAN Transfer', 'Enter Receiver IP Address:'
            )
            if ok2 and ip:
                threading.Thread(
                    target=self.perform_lan_transfer, args=(ip,), daemon=True
                ).start()
            else:
                self.lbl_t.setText("Status: Cancelled")
        elif method == "Google Drive":
            threading.Thread(
                target=self.perform_gdrive_upload,
                args=(receiver_email, receiver_name),
                daemon=True
            ).start()

    # ════════════════════════════════════════════════════════════
    # _create_db_record — STEP 3 APPLIED
    # Added: is_revoked and is_approved checks before transfer
    # ════════════════════════════════════════════════════════════
    def _create_db_record(self, receiver_email, method):
        """
        Shared logic for ALL transfer methods.
        NEW in Step 3: blocks transfer if receiver is revoked or unapproved.
        Returns (receiver_name, transfer_id) on success, None on failure.
        """
        # ── STEP 1: Look up receiver ──────────────────────────────
        try:
            conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, public_key, is_approved, is_revoked "
                "FROM users WHERE email = ?",
                (receiver_email,)
            )
            row = cursor.fetchone()
            conn.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "DB Error", f"Could not query database:\n{e}"
            )
            return None

        if not row:
            QtWidgets.QMessageBox.warning(
                self, "Receiver Not Found",
                f"No registered account found for:\n{receiver_email}\n\n"
                "The receiver must sign up in this app first."
            )
            return None

        receiver_name, public_key_pem, is_approved, is_revoked = row
        public_key_pem = decrypt_field(public_key_pem)

        # ── STEP 2: Account status checks ────────────────────────
        if is_revoked:
            QtWidgets.QMessageBox.critical(
                self, "Transfer Blocked — Account Revoked",
                f"The account for '{receiver_name}' ({receiver_email}) "
                f"has been revoked by the administrator.\n\n"
                "You cannot send files to a revoked account.\n\n"
                "Contact the system administrator if this is unexpected."
            )
            write_audit_log(
                username=self.user_name, role="Sender",
                action="TRANSFER_BLOCKED_REVOKED", method=method,
                file_name=os.path.basename(self.selected_file_path),
                details=f"Blocked: receiver {receiver_email} is revoked"
            )
            write_anomaly_alert(
                "TRANSFER_TO_REVOKED_ACCOUNT",
                f"{self.user_name} attempted to send to revoked account: {receiver_email}",
                "HIGH"
            )
            return None

        if not is_approved:
            QtWidgets.QMessageBox.warning(
                self, "Transfer Blocked — Receiver Pending Approval",
                f"The account for '{receiver_name}' ({receiver_email}) "
                f"has not yet been approved by the administrator.\n\n"
                "Files can only be sent to fully approved accounts.\n\n"
                "Ask the receiver to request approval from the SuperAdmin first."
            )
            write_audit_log(
                username=self.user_name, role="Sender",
                action="TRANSFER_BLOCKED_UNAPPROVED", method=method,
                file_name=os.path.basename(self.selected_file_path),
                details=f"Blocked: receiver {receiver_email} is pending approval"
            )
            return None

        # ── STEP 3: Validate public key ───────────────────────────
        if not is_valid_public_key(public_key_pem):
            QtWidgets.QMessageBox.critical(
                self, "No Public Key",
                f"Receiver '{receiver_name}' has no RSA key.\n"
                "Ask them to re-register their account."
            )
            return None

        # ── STEP 4: Read AES key ──────────────────────────────────
        key_file = self.selected_file_path + ".key.txt"
        if not os.path.exists(key_file):
            QtWidgets.QMessageBox.critical(
                self, "Key File Missing",
                f"Key file not found:\n{key_file}\n\nRe-encrypt the file."
            )
            return None

        with open(key_file, 'r') as kf:
            aes_key = kf.read().strip()

        # ── STEP 5: RSA-encrypt AES key ───────────────────────────
        try:
            encrypted_aes_key = encrypt_aes_key(aes_key, public_key_pem)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "RSA Encryption Failed", f"Could not encrypt AES key:\n{e}"
            )
            return None

        # ── STEP 6: Write vault_transfers + session_keys ──────────
        file_name     = os.path.basename(self.selected_file_path)
        original_hash = getattr(self, 'original_hash', 'N/A')
        case_id       = getattr(self, 'temp_case_id', 'N/A')
        investigator  = getattr(self, 'temp_investigator', 'N/A')

        try:
            conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vault_transfers
                    (sender_name, receiver_email, vault_path,
                     encrypted_aes_key, original_hash, file_name,
                     method, status, case_id, investigator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.user_name, receiver_email,
                self.selected_file_path, encrypted_aes_key,
                encrypt_field(original_hash), file_name, method, "PENDING",
                case_id, investigator
            ))
            transfer_id = cursor.lastrowid

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_keys (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    transfer_id     INTEGER UNIQUE,
                    receiver_email  TEXT NOT NULL,
                    file_name       TEXT NOT NULL,
                    aes_key         TEXT NOT NULL,
                    original_hash   TEXT NOT NULL,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transfer_id) REFERENCES vault_transfers(id)
                )
            ''')
            cursor.execute('''
                INSERT OR REPLACE INTO session_keys
                    (transfer_id, receiver_email, file_name, aes_key, original_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (transfer_id, receiver_email, file_name, encrypt_field(aes_key), encrypt_field(original_hash)))

            conn.commit(); conn.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "DB Error", f"Could not create vault record:\n{e}"
            )
            return None

        write_audit_log(
            username=self.user_name, role="Sender",
            action="VAULT_TRANSFER_CREATED", method=method,
            file_name=file_name,
            details=f"Receiver: {receiver_email} | Case: {case_id} | Hash: {original_hash[:20]}..."
        )

        # ── chain_of_custody table ────────────────────────────────
        try:
            conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
            cur  = conn.cursor()
            cur.execute(
                "INSERT INTO chain_of_custody "
                "(case_id, action, performed_by, location_device) "
                "VALUES (?, ?, ?, ?)",
                (case_id,
                 f"FILE_TRANSFERRED_VIA_{method.upper().replace(' ','_')}",
                 self.user_name, method)
            )
            conn.commit(); conn.close()
        except Exception as e:
            print(f"[chain_of_custody] {e}")

        # ── system_monitor_logs table ─────────────────────────────
        write_system_log(
            event_source=method,
            event_type="TRANSFER_START",
            details=f"File: {file_name} | Sender: {self.user_name} | Receiver: {receiver_email}"
        )

        return receiver_name, transfer_id

    def _send_blind_notification(self, receiver_email, receiver_name):
        import ssl, time
        case_id   = getattr(self, 'temp_case_id', 'N/A')
        file_name = os.path.basename(self.selected_file_path)
        self.lbl_t.setText("Status: Sending notification email...")
        self.p_bar.setValue(20)
        try:
            socket.create_connection(("8.8.8.8",53),timeout=3)
        except OSError:
            QtWidgets.QMessageBox.information(self,"Vault Record Created",
                f"File secured in Vault for: {receiver_name}\n\nNo internet — email skipped.")
            self.lbl_t.setText("Status: Vault record created (offline) ✅")
            self.p_bar.setValue(100)
            self.add_to_history("Email (Vault)","Success",destination=receiver_email)
            self.add_notification("Vault Transfer",f"Record created for {receiver_name}","Success")
            return
        try:
            ctx    = ssl.create_default_context()
            server = smtplib.SMTP_SSL('smtp.gmail.com',465,context=ctx,timeout=30)
            server.login(self.SENDER_EMAIL, self.SENDER_PASSWORD)
            from email.message import EmailMessage
            msg = EmailMessage()
            msg['From']    = self.SENDER_EMAIL
            msg['To']      = receiver_email
            msg['Subject'] = "[SDTF Security Alert] New Forensic Package Assigned to You"
            msg.set_content(
                f"Hello {receiver_name},\n\n"
                "A secure forensic file has been assigned to your account in the SDTF Vault.\n\n"
                "To retrieve: Open SDTF → Log in → Receive Data → Vault Fetch\n\n"
                f"Sender: {self.user_name}\nCase Reference: {case_id}\n\n"
                "--- SDTF Automated Security System ---"
            )
            server.send_message(msg); server.quit()
            for i in range(20,101):
                self.p_bar.setValue(i); QtWidgets.QApplication.processEvents(); time.sleep(0.01)
            self.lbl_t.setText("Status: Vault transfer complete ✅")
            self.add_forensic_log(f"Vault transfer to {receiver_email}","LOW",file_name)
            self.add_notification("Vault Transfer",f"Notified {receiver_name}","Success")
            self.add_to_history("Email (Vault)","Success",destination=receiver_email)
            QtWidgets.QMessageBox.information(self,"Vault Transfer Complete ✅",
                f"File secured for: {receiver_name}\nNotification sent to: {receiver_email}")
        except smtplib.SMTPAuthenticationError:
            self.p_bar.setValue(0)
            QtWidgets.QMessageBox.warning(self,"Notification Failed — Vault Record Saved",
                "Gmail auth failed. Vault record IS created. Receiver CAN still fetch from app.")
            self.add_to_history("Email (Vault)","Success (No Notification)",destination=receiver_email)
        except Exception as e:
            self.p_bar.setValue(0)
            QtWidgets.QMessageBox.warning(self,"Notification Failed — Vault Record Saved",
                f"Email failed:\n{e}\n\nVault record created. Receiver can fetch from app.")
            self.add_to_history("Email (Vault)","Success (No Notification)",destination=receiver_email)

    def perform_lan_transfer(self, ip):
        try:
            if not self.selected_file_path or not os.path.exists(self.selected_file_path):
                self.add_notification("LAN","Failed: file not found","Failed"); return
            fsz       = os.path.getsize(self.selected_file_path)
            orig_name = os.path.basename(self.selected_file_path)
            QtCore.QMetaObject.invokeMethod(self.lbl_t,"setText",
                QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Status: Connecting to {ip}..."))
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((ip, 5000))
            handshake = f"{fsz}|{orig_name}".encode('utf-8')
            client.send(handshake)
            ack = client.recv(1024)
            if ack != b"ACK_SIZE":
                client.close()
                QtCore.QMetaObject.invokeMethod(self.lbl_t,"setText",
                    QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str,"Status: Handshake failed ❌"))
                return
            sent = 0
            with open(self.selected_file_path, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk: break
                    client.sendall(chunk); sent += len(chunk)
                    pct = int((sent / fsz) * 100)
                    QtCore.QMetaObject.invokeMethod(self.p_bar,"setValue",
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, pct))
                    QtCore.QMetaObject.invokeMethod(self.lbl_t,"setText",
                        QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Status: Sending... {pct}%"))
            client.close()
            QtCore.QMetaObject.invokeMethod(self.lbl_t,"setText",
                QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str,"Status: LAN Transfer Success! ✅"))
            QtCore.QMetaObject.invokeMethod(self.p_bar,"setValue",
                QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, 100))
            self.add_notification("LAN", f"Sent to {ip}", "Success")
            self.add_to_history("LAN", "Success", destination=ip)
        except Exception as e:
            QtCore.QMetaObject.invokeMethod(self.lbl_t,"setText",
                QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str,"Status: LAN Failed ❌"))
            self.add_notification("LAN", f"Failed: {e}", "Failed")
            self.add_to_history("LAN", "Failed", destination=ip)

    def detect_new_hardware(self, method):
        cur = self.get_current_drives()
        new = [d for d in cur if d not in self.existing_drives]
        if new: self.monitor_timer.stop(); self.copy_file_to_drive(new[0], method)

    def copy_file_to_drive(self, drive, method):
        try:
            fname  = os.path.basename(self.selected_file_path)
            folder = os.path.join(drive,"Forensic_Transfers")
            if not os.path.exists(folder): os.makedirs(folder)
            for i in range(0,101,20):
                QtCore.QThread.msleep(50); self.p_bar.setValue(i)
                self.lbl_t.setText(f"Status: Copying to {method}... {i}%")
                QtWidgets.QApplication.processEvents()
            shutil.copy2(self.selected_file_path, os.path.join(folder,fname))
            self.p_bar.setValue(100); self.lbl_t.setText(f"Status: {method} Complete ✅")
            self.add_to_history(method,"Success",destination=folder)
            self.add_notification(f"{method}",f"Copied to {folder}","Success")
            write_system_log(
                event_source=method,
                event_type="TRANSFER_COMPLETE",
                details=f"File copied to {folder}"
            )
            QtWidgets.QMessageBox.information(self,"Success",f"File on {method}.\n{folder}")
        except PermissionError:
            self.lbl_t.setText("Status: Permission Denied ❌")
            QtWidgets.QMessageBox.critical(self,"Error","Permission denied. Run as Administrator.")
        except Exception as e:
            self.lbl_t.setText("Status: Copy Failed ❌")
            QtWidgets.QMessageBox.critical(self,"Error",str(e))

    def perform_gdrive_upload(self, receiver_email="", receiver_name=""):
        try:
            name = os.path.basename(self.selected_file_path)
            self.update_progress.emit(10,"Status: Authenticating G-Drive...")
            gauth = GoogleAuth(); gauth.LocalWebserverAuth(); drive = PDrive(gauth)
            self.update_progress.emit(50,f"Status: Uploading {name}...")
            gf = drive.CreateFile({'title':name})
            gf.SetContentFile(self.selected_file_path); gf.Upload()
            gf.InsertPermission({'type':'anyone','value':'anyone','role':'reader'})
            self.update_progress.emit(100,"Status: G-Drive Upload Complete ✅")
            self.show_gdrive_link.emit(gf['alternateLink'])
            self.add_to_history("Google Drive","Success",destination=receiver_email or "Google Cloud")
            self.add_notification("Google Drive",f"Uploaded for {receiver_name or 'receiver'}","Success")
            write_audit_log(username=self.user_name, role="Sender",
                action="GDRIVE_UPLOAD", method="Google Drive", file_name=name,
                details=f"Receiver: {receiver_email} | Link: {gf['alternateLink'][:30]}...")
        except Exception as e:
            self.update_progress.emit(0,"Status: G-Drive Error ❌")
            self.add_notification("Google Drive",f"Failed: {e}","Failed")


    @QtCore.pyqtSlot(str)
    def show_gdrive_success(self, link):
        msg = QtWidgets.QMessageBox(self); msg.setWindowTitle("Upload Successful")
        msg.setText(f"<b>File Uploaded!</b><br>Share link:<br><a href='{link}'>{link}</a>")
        cb = msg.addButton("Copy Link",QtWidgets.QMessageBox.ActionRole)
        msg.addButton(QtWidgets.QMessageBox.Ok); msg.exec_()
        if msg.clickedButton() == cb:
            QtWidgets.QApplication.clipboard().setText(link)

    def show_case_form(self):
        if not self.selected_file_path:
            QtWidgets.QMessageBox.warning(self, "Warning", "Encrypt a file first!")
            return

        fname     = os.path.basename(self.selected_file_path)
        fsize     = os.path.getsize(self.selected_file_path)
        fsize_str = f"{fsize/1024:.2f} KB" if fsize < 1024*1024 else f"{fsize/(1024*1024):.2f} MB"
        fhash     = getattr(self, 'original_hash', 'N/A')
        ftime     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Forensic Chain of Custody")
        dlg.setMinimumWidth(560)
        dlg.setStyleSheet("""
            QDialog { background:#f8fafc; font-family:'Segoe UI'; }
            QLabel.section { font-size:13px; font-weight:bold; color:#1a56db; padding-top:6px; }
            QLineEdit, QComboBox, QTextEdit {
                border:1.5px solid #93c5fd; border-radius:7px;
                padding:7px 10px; font-size:13px;
                background:#ffffff; color:#1e3a5f;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border:1.5px solid #1a56db; background:#eff6ff;
            }
        """)

        root = QtWidgets.QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────
        hdr = QtWidgets.QFrame()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1a56db, stop:1 #0ea5e9);"
            "border-top-left-radius:8px; border-top-right-radius:8px; }"
        )
        hl = QtWidgets.QHBoxLayout(hdr)
        hl.setContentsMargins(18, 0, 18, 0)
        hl_icon = QtWidgets.QLabel("🔗")
        hl_icon.setStyleSheet("font-size:22px; background:transparent;")
        hl_title = QtWidgets.QLabel("Forensic Chain of Custody")
        hl_title.setStyleSheet("color:white; font-size:16px; font-weight:bold; background:transparent;")
        hl.addWidget(hl_icon)
        hl.addSpacing(8)
        hl.addWidget(hl_title)
        hl.addStretch()
        root.addWidget(hdr)

        # ── Scrollable body ───────────────────────────────────────
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:#f8fafc; border:none; }")
        body_w = QtWidgets.QWidget()
        body_w.setStyleSheet("background:#f8fafc;")
        body = QtWidgets.QVBoxLayout(body_w)
        body.setContentsMargins(24, 18, 24, 10)
        body.setSpacing(8)
        scroll.setWidget(body_w)
        root.addWidget(scroll)

        inp_style = (
            "border:1.5px solid #93c5fd; border-radius:7px; "
            "padding:7px 10px; font-size:13px; "
            "background:#ffffff; color:#1e3a5f;"
        )

        def section_hdr(emoji, text):
            f = QtWidgets.QFrame()
            f.setStyleSheet(
                "QFrame { background:#eff6ff; border-radius:6px; "
                "border-left:3px solid #1a56db; }"
            )
            fl = QtWidgets.QHBoxLayout(f)
            fl.setContentsMargins(10, 6, 10, 6)
            lbl = QtWidgets.QLabel(f"{emoji}  {text}")
            lbl.setStyleSheet("font-size:12px; font-weight:bold; color:#1a56db; background:transparent;")
            fl.addWidget(lbl)
            return f

        def lbl(text):
            l = QtWidgets.QLabel(text)
            l.setStyleSheet("font-size:12px; color:#374151; font-weight:bold; background:transparent;")
            return l

        # ── Section 1: Case Information ───────────────────────────
        body.addWidget(section_hdr("📁", "CASE INFORMATION"))

        body.addWidget(lbl("Case Identifier (e.g. Case 001):"))
        ci = QtWidgets.QLineEdit()
        ci.setPlaceholderText("e.g. Case 001")
        ci.setStyleSheet(inp_style)
        body.addWidget(ci)

        body.addWidget(lbl("Case Name / Title:"))
        case_name = QtWidgets.QLineEdit()
        case_name.setPlaceholderText("e.g. Cyber Fraud Investigation 2025")
        case_name.setStyleSheet(inp_style)
        body.addWidget(case_name)

        body.addWidget(lbl("Case Type:"))
        case_type = QtWidgets.QComboBox()
        case_type.addItems([
            "-- Select Case Type --",
            "Cybercrime", "Financial Fraud", "Digital Forensics",
            "Data Breach", "Insider Threat", "Intellectual Property", "Other"
        ])
        case_type.setStyleSheet(inp_style)
        body.addWidget(case_type)

        # ── Section 2: Investigator & Classification ──────────────
        body.addWidget(section_hdr("👤", "INVESTIGATOR & CLASSIFICATION"))

        body.addWidget(lbl("Authorized Investigator Name:"))
        inv = QtWidgets.QLineEdit()
        inv.setPlaceholderText("Min 3 characters")
        inv.setStyleSheet(inp_style)
        body.addWidget(inv)

        body.addWidget(lbl("Investigator Badge / ID:"))
        badge_id = QtWidgets.QLineEdit()
        badge_id.setPlaceholderText("e.g. INV-2025-047")
        badge_id.setStyleSheet(inp_style)
        body.addWidget(badge_id)

        body.addWidget(lbl("Organization / Department:"))
        org = QtWidgets.QLineEdit()
        org.setPlaceholderText("e.g. Cyber Crime Unit, Federal Bureau")
        org.setStyleSheet(inp_style)
        body.addWidget(org)

        body.addWidget(lbl("Evidence Classification:"))
        cls = QtWidgets.QComboBox()
        cls.addItems(["-- Select Classification --", "Top Secret", "Confidential", "Internal", "Restricted"])
        cls.setStyleSheet(inp_style)
        body.addWidget(cls)

        # ── Section 3: Transfer Details ───────────────────────────
        body.addWidget(section_hdr("📤", "TRANSFER DETAILS"))

        body.addWidget(lbl("Intended Receiver Name:"))
        receiver_name_f = QtWidgets.QLineEdit()
        receiver_name_f.setPlaceholderText("Full name of the receiver")
        receiver_name_f.setStyleSheet(inp_style)
        body.addWidget(receiver_name_f)

        body.addWidget(lbl("Purpose of Transfer:"))
        purpose = QtWidgets.QTextEdit()
        purpose.setPlaceholderText("Briefly describe why this evidence is being transferred...")
        purpose.setFixedHeight(70)
        purpose.setStyleSheet(inp_style)
        body.addWidget(purpose)

        # ── Section 4: Evidence Info (auto-filled) ────────────────
        body.addWidget(section_hdr("🔒", "EVIDENCE (AUTO-FILLED)"))

        for label_txt, val_txt in [
            ("File Name:", fname),
            ("File Size:", fsize_str),
            ("SHA-256 Hash:", fhash),
            ("Timestamp:", ftime),
        ]:
            row_w = QtWidgets.QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_l = QtWidgets.QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(8)
            key_lbl = QtWidgets.QLabel(label_txt)
            key_lbl.setFixedWidth(110)
            key_lbl.setStyleSheet("font-size:12px; color:#374151; font-weight:bold; background:transparent;")
            val_lbl = QtWidgets.QLabel(val_txt)
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet(
                "font-size:12px; color:#1e3a5f; background:#eff6ff; "
                "border-radius:5px; padding:4px 8px; border:1px solid #bfdbfe;"
            )
            row_l.addWidget(key_lbl)
            row_l.addWidget(val_lbl, 1)
            body.addWidget(row_w)

        body.addStretch()

        # ── Footer buttons ────────────────────────────────────────
        foot = QtWidgets.QFrame()
        foot.setStyleSheet("background:#f1f5f9; border-top:2px solid #e2e8f0;")
        foot.setFixedHeight(62)
        foot_l = QtWidgets.QHBoxLayout(foot)
        foot_l.setContentsMargins(20, 10, 20, 10)
        foot_l.addStretch()

        btn_pdf = QtWidgets.QPushButton("💾   Save & Generate PDF")
        btn_pdf.setFixedHeight(40)
        btn_pdf.setMinimumWidth(200)
        btn_pdf.setCursor(QtCore.Qt.PointingHandCursor)
        btn_pdf.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #16a34a, stop:1 #22c55e); color:white; font-weight:bold; "
            "font-size:13px; border-radius:8px; } "
            "QPushButton:hover { background:#15803d; }"
        )

        btn_proceed = QtWidgets.QPushButton("✅   Verify & Proceed")
        btn_proceed.setFixedHeight(40)
        btn_proceed.setMinimumWidth(180)
        btn_proceed.setCursor(QtCore.Qt.PointingHandCursor)
        btn_proceed.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1a56db, stop:1 #0ea5e9); color:white; font-weight:bold; "
            "font-size:13px; border-radius:8px; } "
            "QPushButton:hover { background:#1e40af; }"
        )

        btn_cancel = QtWidgets.QPushButton("✕  Cancel")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setMinimumWidth(90)
        btn_cancel.setCursor(QtCore.Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background:white; color:#ef4444; font-weight:bold; "
            "font-size:13px; border:2px solid #ef4444; border-radius:8px; } "
            "QPushButton:hover { background:#fef2f2; }"
        )
        btn_cancel.clicked.connect(dlg.close)

        foot_l.addWidget(btn_pdf)
        foot_l.addSpacing(10)
        foot_l.addWidget(btn_proceed)
        foot_l.addSpacing(10)
        foot_l.addWidget(btn_cancel)
        root.addWidget(foot)

        # ── Validation helper ─────────────────────────────────────
        def get_validated():
            c = ci.text().strip()
            i = inv.text().strip()
            if not c or not i or cls.currentIndex() == 0:
                QtWidgets.QMessageBox.critical(dlg, "Error", "Case ID, Investigator Name, and Classification are mandatory!")
                return None
            if "case" not in c.lower():
                QtWidgets.QMessageBox.critical(dlg, "Error", "Case ID must contain 'Case'!")
                return None
            if len(i) < 3:
                QtWidgets.QMessageBox.critical(dlg, "Error", "Investigator name must be at least 3 characters!")
                return None
            return True

        # ── PDF generation ────────────────────────────────────────
        def save_pdf():
            if not get_validated():
                return
            dest_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg,
                "Save Chain of Custody Report (PDF)",
                f"ChainOfCustody_{ci.text().strip().replace('/','_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "PDF Files (*.pdf);;All Files (*)"
            )
            if not dest_path:
                return
            try:
                if not _REPORTLAB_OK:
                    QtWidgets.QMessageBox.critical(
                        dlg, "Missing Library",
                        "reportlab library not found.\n\nInstall it:\n  pip install reportlab"
                    )
                    return

                A4          = _RL_A4
                colors      = _RL_colors
                cm          = _RL_cm
                doc         = _RL_Doc(
                    dest_path, pagesize=A4,
                    leftMargin=2*cm, rightMargin=2*cm,
                    topMargin=2*cm, bottomMargin=2*cm
                )
                BLUE  = colors.HexColor("#1a56db")
                LBLUE = colors.HexColor("#eff6ff")
                DGRAY = colors.HexColor("#1e293b")
                LGRAY = colors.HexColor("#f1f5f9")
                BORDER= colors.HexColor("#e2e8f0")
                GREEN = colors.HexColor("#16a34a")
                WHITE = colors.white

                def hdr_para(txt):
                    return _RL_Para(
                        f'<font color="#1a56db"><b>{txt}</b></font>',
                        _RL_PS("sh", fontSize=11, spaceAfter=4, leading=16)
                    )

                def kv_table(pairs):
                    data = []
                    for k, v in pairs:
                        data.append([
                            _RL_Para(f'<b><font color="#374151">{k}</font></b>',
                                     _RL_PS("k", fontSize=10, leading=14)),
                            _RL_Para(f'<font color="#1e293b">{v}</font>',
                                     _RL_PS("v", fontSize=10, leading=14))
                        ])
                    t = _RL_Table(data, colWidths=[5*cm, 11*cm])
                    t.setStyle(_RL_TableStyle([
                        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]),
                        ("GRID",           (0,0), (-1,-1), 0.4, BORDER),
                        ("VALIGN",         (0,0), (-1,-1), "TOP"),
                        ("TOPPADDING",     (0,0), (-1,-1), 7),
                        ("BOTTOMPADDING",  (0,0), (-1,-1), 7),
                        ("LEFTPADDING",    (0,0), (-1,-1), 10),
                    ]))
                    return t

                story = []

                # Title block
                title_data = [
                    [_RL_Para('<font color="white"><b>SECURE FORENSIC DATA SHARING FRAMEWORK</b></font>',
                              _RL_PS("t1", fontSize=14, alignment=_RL_CENTER, leading=20))],
                    [_RL_Para('<font color="#bae6fd">Chain of Custody Report</font>',
                              _RL_PS("t2", fontSize=11, alignment=_RL_CENTER, leading=16))],
                    [_RL_Para(f'<font color="#e0f2fe">Generated: {datetime.now().strftime("%d %B %Y  —  %H:%M:%S")}</font>',
                              _RL_PS("t3", fontSize=9, alignment=_RL_CENTER))],
                ]
                title_t = _RL_Table(title_data, colWidths=[16*cm])
                title_t.setStyle(_RL_TableStyle([
                    ("BACKGROUND",     (0,0), (-1,-1), BLUE),
                    ("TOPPADDING",     (0,0), (-1,-1), 10),
                    ("BOTTOMPADDING",  (0,0), (-1,-1), 8),
                    ("LEFTPADDING",    (0,0), (-1,-1), 16),
                ]))
                story.append(title_t)
                story.append(_RL_Spacer(1, 0.4*cm))

                # Case Information
                story.append(hdr_para("📁  CASE INFORMATION"))
                story.append(kv_table([
                    ("Case ID",       ci.text().strip()),
                    ("Case Name",     case_name.text().strip() or "N/A"),
                    ("Case Type",     case_type.currentText() if case_type.currentIndex() > 0 else "N/A"),
                ]))
                story.append(_RL_Spacer(1, 0.35*cm))

                # Investigator & Classification
                story.append(hdr_para("👤  INVESTIGATOR & CLASSIFICATION"))
                story.append(kv_table([
                    ("Investigator",   inv.text().strip()),
                    ("Badge / ID",     badge_id.text().strip() or "N/A"),
                    ("Organization",   org.text().strip() or "N/A"),
                    ("Classification", cls.currentText()),
                ]))
                story.append(_RL_Spacer(1, 0.35*cm))

                # Transfer Details
                story.append(hdr_para("📤  TRANSFER DETAILS"))
                story.append(kv_table([
                    ("Sender",          self.user_name),
                    ("Intended Receiver", receiver_name_f.text().strip() or "N/A"),
                    ("Purpose",          purpose.toPlainText().strip() or "N/A"),
                ]))
                story.append(_RL_Spacer(1, 0.35*cm))

                # Evidence Info
                story.append(hdr_para("🔒  EVIDENCE DETAILS"))
                story.append(kv_table([
                    ("File Name",   fname),
                    ("File Size",   fsize_str),
                    ("SHA-256 Hash", fhash),
                    ("Timestamp",   ftime),
                ]))
                story.append(_RL_Spacer(1, 0.5*cm))

                story.append(_RL_HR(width="100%", thickness=1, color=BORDER))
                story.append(_RL_Spacer(1, 0.2*cm))
                story.append(_RL_Para(
                    f'<font color="#94a3b8" size="8">SFDS — Report ID: SFDS-{datetime.now().strftime("%Y%m%d%H%M%S")} — Sender: {self.user_name}</font>',
                    _RL_PS("foot", fontSize=8, alignment=_RL_CENTER)
                ))

                doc.build(story)

                write_audit_log(
                    username=self.user_name, role="Sender",
                    action="CASE_REPORT_GENERATED", method="PDF",
                    file_name=os.path.basename(dest_path),
                    details=f"Case ID: {ci.text().strip()}"
                )
                QtWidgets.QMessageBox.information(
                    dlg, "PDF Saved ✅",
                    f"Chain of Custody PDF saved successfully!\n\n{dest_path}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "PDF Failed", f"Error generating PDF:\n{e}")

        # ── Verify & Proceed ──────────────────────────────────────
        def validate():
            if not get_validated():
                return
            self.temp_case_id     = ci.text().strip()
            self.temp_investigator = inv.text().strip()

            try:
                conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
                cur  = conn.cursor()
                cur.execute(
                    "INSERT INTO forensic_files "
                    "(case_id, file_name, original_hash, file_size, sender_name) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (self.temp_case_id,
                     os.path.basename(self.selected_file_path).replace(
                         'ENCRYPTED_', '').replace('.aes', ''),
                     encrypt_field(getattr(self, 'original_hash', 'N/A')),
                     f"{os.path.getsize(self.selected_file_path)/1024:.2f} KB"
                     if os.path.exists(self.selected_file_path) else 'N/A',
                     self.user_name)
                )
                conn.commit(); conn.close()
            except Exception as e:
                print(f"[forensic_files] {e}")

            # ── manifest_details table ────────────────────────────
            try:
                key_file = self.selected_file_path + ".key.txt"
                aes_key  = (open(key_file).read().strip()
                            if os.path.exists(key_file) else "N/A")
                conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
                cur  = conn.cursor()
                cur.execute(
                    "INSERT INTO manifest_details "
                    "(case_id, aes_key, investigator_name, creation_date) "
                    "VALUES (?, ?, ?, ?)",
                    (self.temp_case_id, encrypt_field(aes_key),
                     self.temp_investigator,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit(); conn.close()
            except Exception as e:
                print(f"[manifest_details] {e}")

            dlg.accept()

        btn_pdf.clicked.connect(save_pdf)
        btn_proceed.clicked.connect(validate)

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.stack.setCurrentIndex(2)

    def select_file_for_hash(self):
        f,_ = QtWidgets.QFileDialog.getOpenFileName(self,"Select File")
        if f: self.in_check_path.setText(f)

    def calculate_hash_logic(self):
        path = self.in_check_path.text()
        if os.path.exists(path):
            h = hashlib.sha256()
            with open(path,"rb") as f:
                for b in iter(lambda:f.read(4096),b""): h.update(b)
            self.out_hash.setText(f"<b>SHA-256 Hash:</b><br>{h.hexdigest()}")
            self.add_forensic_log(f"Integrity Check on {os.path.basename(path)}","MEDIUM")
        else:
            QtWidgets.QMessageBox.warning(self,"Error","File not found!")

    def copy_hash_to_clipboard(self):
        t = self.out_hash.text()
        if "SHA-256 Hash:" in t:
            QtWidgets.QApplication.clipboard().setText(t.split("<br>")[-1])
            QtWidgets.QMessageBox.information(self,"Copied","Hash copied!")
        else:
            QtWidgets.QMessageBox.warning(self,"Error","No hash generated yet.")

    def add_to_history(self, method, status, destination="N/A"):
        ts = datetime.now().strftime("%H:%M:%S")
        fn = os.path.basename(self.selected_file_path) if self.selected_file_path else "Unknown"
        r  = self.tab_hist.rowCount(); self.tab_hist.insertRow(r)
        self.tab_hist.setItem(r,0,QtWidgets.QTableWidgetItem(ts))
        self.tab_hist.setItem(r,1,QtWidgets.QTableWidgetItem(fn))
        self.tab_hist.setItem(r,2,QtWidgets.QTableWidgetItem(method))
        self.tab_hist.setItem(r,3,QtWidgets.QTableWidgetItem(destination))
        si = QtWidgets.QTableWidgetItem(status)
        if "Suspicious" in status:
            si.setForeground(QtGui.QColor("#dc2626")); fnt=QtGui.QFont(); fnt.setBold(True); si.setFont(fnt)
        elif "Failed" in status: si.setForeground(QtGui.QColor("#f97316"))
        else:                    si.setForeground(QtGui.QColor("#16a34a"))
        self.tab_hist.setItem(r,4,si)
        self.save_data_to_file(self.HISTORY_STORAGE,
            {"time":ts,"file":fn,"protocol":method,"destination":destination,"status":status})
        write_audit_log(username=self.user_name, role="Sender",
            action=f"TRANSFER_{status.upper().replace(' ','_')}",
            method=method, file_name=fn, details=f"Destination: {destination}")
        self.update_dashboard_stats()

    def add_forensic_log(self, activity, level, file_name="N/A"):
        try:
            eid = f"EVT-{random.randint(1000,9999)}"
            r   = self.log_table.rowCount(); self.log_table.insertRow(r)
            self.log_table.setItem(r,0,QtWidgets.QTableWidgetItem(eid))
            self.log_table.setItem(r,1,QtWidgets.QTableWidgetItem(activity))
            self.log_table.setItem(r,2,QtWidgets.QTableWidgetItem(level))
            self.activity_list.addItem(f"● {activity}")
            self.save_data_to_file(self.LOGS_STORAGE,
                {"event_id":eid,"activity":activity,"level":level,"file":file_name})
        except Exception as e: print(f"Log error: {e}")

    def log_to_ws_db(self, action, method, file_name, details=""):
        write_audit_log(username=self.user_name, role="Sender",
            action=action, method=method, file_name=file_name, details=details)

    def _add_notification_safe(self, message, status):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"time": ts, "msg": message, "status": status}
        notifs = []
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f:
                    notifs = json.load(f)
            except:
                notifs = []
        notifs.insert(0, entry)
        with open(self.NOTIF_STORAGE, 'w') as f:
            json.dump(notifs[:50], f, indent=4)
        self.notif_count += 1
        self.notif_btn.setCounter(self.notif_count)
        if self.notif_panel.isVisible():
            self.notif_panel.populate(notifs)
            self.notif_count = 0
            self.notif_btn.setCounter(0)

    def add_notification(self, title, message, status):
        icon = "✅" if status == "Success" else ("🚨" if "Suspicious" in status else "❌")
        full_msg = f"{icon} {title}: {message}"
        self.sig_notification.emit(full_msg, status)

    def load_notifications_to_menu(self):
        notifs = []
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f:
                    notifs = json.load(f)
            except:
                notifs = []
        self.notif_count = len(notifs)
        self.notif_btn.setCounter(self.notif_count)

    def _toggle_notif_panel(self):
        if self.notif_panel.isVisible():
            self.notif_panel.hide()
            return
        notifs = []
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f:
                    notifs = json.load(f)
            except:
                notifs = []
        self.notif_panel.populate(notifs)
        self.notif_panel.show_below(self.notif_btn)
        self.notif_count = 0
        self.notif_btn.setCounter(0)

    def _clear_all_notifications(self):
        try:
            with open(self.NOTIF_STORAGE, 'w') as f:
                json.dump([], f)
        except:
            pass
        self.notif_count = 0
        self.notif_btn.setCounter(0)
        self.notif_panel.populate([])

    def mark_as_read(self):
        self.unread_count = 0

    def clear_transfer_history(self):
        confirm = QtWidgets.QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all transfer history?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if confirm == QtWidgets.QMessageBox.Yes:
            self.tab_hist.setRowCount(0)
            try:
                with open(self.HISTORY_STORAGE, 'w') as f:
                    json.dump([], f)
            except Exception as e:
                print(f"Clear history error: {e}")
            self.update_dashboard_stats()

    # ── Helper: generic search bar for any QTableWidget ──────────────
    def setup_search_bar(self, table, placeholder="Search..."):
        container = QtWidgets.QWidget()
        container.setStyleSheet("background: transparent;")
        row = QtWidgets.QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        search = QtWidgets.QLineEdit()
        search.setPlaceholderText(f"🔍  {placeholder}")
        search.setFixedHeight(40)
        search.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #93c5fd;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 13px;
                background: #ffffff;
                color: #1e3a5f;
            }
            QLineEdit:focus {
                border: 1.5px solid #1a56db;
                background: #eff6ff;
            }
        """)

        def filter_table(text):
            for r in range(table.rowCount()):
                match = any(
                    table.item(r, c) and text.lower() in table.item(r, c).text().lower()
                    for c in range(table.columnCount())
                )
                table.setRowHidden(r, not match)

        search.textChanged.connect(filter_table)
        row.addWidget(search)
        return container

    # ── Export Forensic Logs to CSV ───────────────────────────────────
    def export_logs_to_csv(self):
        import csv
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Logs", "forensic_logs.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = [
                    self.log_table.horizontalHeaderItem(c).text()
                    for c in range(self.log_table.columnCount())
                ]
                writer.writerow(headers)
                for r in range(self.log_table.rowCount()):
                    row_data = []
                    for c in range(self.log_table.columnCount()):
                        item = self.log_table.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QtWidgets.QMessageBox.information(self, "Export Successful", f"Logs exported to:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(e))

    # ── Hash History Page ─────────────────────────────────────────────
    def show_hash_history_page(self):
        # Refresh the hash history table with latest data then switch stack page
        self.hash_hist_table.setRowCount(0)
        for r in range(self.log_table.rowCount()):
            act_item = self.log_table.item(r, 1)
            if act_item and ("hash" in act_item.text().lower() or "integrity" in act_item.text().lower()):
                nr = self.hash_hist_table.rowCount()
                self.hash_hist_table.insertRow(nr)
                for c in range(3):
                    src = self.log_table.item(r, c)
                    self.hash_hist_table.setItem(nr, c, QtWidgets.QTableWidgetItem(src.text() if src else ""))
        self.stack.setCurrentIndex(7)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    # Block direct execution — must go through app.py login
    from PyQt5.QtWidgets import QMessageBox
    msg = QMessageBox()
    msg.setWindowTitle("Access Denied")
    msg.setIcon(QMessageBox.Critical)
    msg.setText(
        "This module cannot be run directly.\n\n"
        "Please launch the application through:\n"
        "    python app.py"
    )
    msg.exec_()
    sys.exit(1)