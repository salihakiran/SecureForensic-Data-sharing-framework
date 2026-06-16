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
import sqlite3
from datetime import datetime
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

# ── ENCRYPTION IMPORTS ──────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Error: 'cryptography' library missing. Run: pip install cryptography")

# RSA engine — decrypts AES key using receiver's local private key
from key_exchange import decrypt_aes_key

# Field-level encryption for keys/hashes stored in the DB
from db_crypto import encrypt_field, decrypt_field

# Shared audit log — writes to users.db so admin dashboard can read it
from app import write_audit_log, write_anomaly_alert, write_system_log, DB_PATH


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
# NOTIFICATION PANEL — styled like sender's
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
            "stop:0 #0284c7, stop:1 #0ea5e9); "
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
            QScrollBar::handle:vertical:hover { background:#0284c7; }
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
            "Info":    ("#e0f2fe", "#0284c7", "ℹ️"),
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


# ═══════════════════════════════════════════════════════════════
# RECEIVER DASHBOARD — main window with SENDER-LIKE UI
# ═══════════════════════════════════════════════════════════════
class ReceiverDashboard(QtWidgets.QMainWindow):

    sig_status = QtCore.pyqtSignal(str)
    sig_progress = QtCore.pyqtSignal(int)
    sig_refresh_vault = QtCore.pyqtSignal()
    sig_refresh_stats = QtCore.pyqtSignal()
    sig_notification = QtCore.pyqtSignal(str, str)

    def __init__(self, name="Receiver"):
        super().__init__()

        # ── STORAGE PATHS ────────────────────────────────────────
        self.user_name = name
        _base = os.path.dirname(os.path.abspath(__file__))
        self.HISTORY_STORAGE = os.path.join(_base, "receive_history_record.json")
        self.NOTIF_STORAGE = os.path.join(_base, "notifications_record.json")
        self.RECEIVED_DIR = os.path.join(_base, "Received_Forensic_Packages")
        self.current_hw_method = "HDD/USB"

        # ── STATE FLAGS ──────────────────────────────────────────
        self.waiting_for_hdd = False
        self.existing_drives = [
            f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")
        ]
        self._pending_hash = None
        self._pending_file = None

        if not os.path.exists(self.RECEIVED_DIR):
            os.makedirs(self.RECEIVED_DIR)

        self.setWindowTitle("Secure Forensic Data Sharing Framework - Receiver Panel")
        self.showMaximized()
        self.setStyleSheet("QMainWindow { background: #f0f6ff; }")

        mainWidget = QtWidgets.QWidget()
        mainWidget.setStyleSheet("background: #f0f6ff;")
        self.setCentralWidget(mainWidget)
        mainLayout = QtWidgets.QVBoxLayout(mainWidget)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        # ================= TOP RIBBON (SAME AS SENDER) =================
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

        # ================= SIDEBAR (SAME AS SENDER) =================
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

        def sideButton(text, emoji=""):
            btn = QtWidgets.QPushButton(f"  {emoji}  {text}")
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

        self.btn_home = sideButton("Dashboard Overview", "🏠")
        self.btn_methods = sideButton("Receive Data", "📡")
        self.btn_vault = sideButton("Received Vault", "📁")
        self.btn_decrypt = sideButton("Decryption Module", "🔓")
        self.btn_integrity = sideButton("Integrity Check", "🔍")
        self.btn_history = sideButton("Receive History", "📊")
        self.btn_report = sideButton("Case Report", "📋")

        for b in [self.btn_home, self.btn_methods, self.btn_vault,
                  self.btn_decrypt, self.btn_integrity, self.btn_history, self.btn_report]:
            sideLayout.addWidget(b)

        sideLayout.addStretch()

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

        self.btn_home.clicked.connect(
            lambda: (self.stack.setCurrentIndex(0), self.update_dashboard_stats())
        )
        self.btn_methods.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_vault.clicked.connect(
            lambda: (self.stack.setCurrentIndex(2), self.refresh_vault_table())
        )
        self.btn_decrypt.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.btn_integrity.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.btn_history.clicked.connect(
            lambda: (self.stack.setCurrentIndex(5), self.load_history_data())
        )
        self.btn_report.clicked.connect(self.open_case_report_dialog)

        # ── SIGNAL CONNECTIONS ──────────────────────────────────────
        self.sig_status.connect(self.lbl_t.setText)
        self.sig_progress.connect(self.p_bar.setValue)
        self.sig_refresh_vault.connect(self.refresh_vault_table)
        self.sig_refresh_stats.connect(self.update_dashboard_stats)
        self.sig_notification.connect(self._add_notification_safe)

        # ── HARDWARE MONITOR ───────────────────────────────────────
        self.monitor_timer = QtCore.QTimer()
        self.monitor_timer.timeout.connect(self.detect_new_hardware)
        self.monitor_timer.start(2000)

        # ── INITIAL DATA LOAD ──────────────────────────────────────
        self.load_notifications_to_menu()
        self.load_activity_logs()
        self.update_dashboard_stats()

    # ═══════════════════════════════════════════════════════════
    # UI PAGES — SENDER-LIKE STYLING
    # ═══════════════════════════════════════════════════════════
    def setup_ui_pages(self):
        # --- 1. HOME PAGE (SAME AS SENDER) ---
        pg0 = QtWidgets.QWidget()
        pg0.setObjectName("HomePage")
        pg0.setStyleSheet("""
            #HomePage {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eff6ff, stop:0.5 #f8faff, stop:1 #eff6ff);
            }
        """)

        l0 = QtWidgets.QVBoxLayout(pg0)
        l0.setContentsMargins(35, 25, 35, 25)
        l0.setSpacing(20)

        # Header row
        hdr_row = QtWidgets.QHBoxLayout()
        hdr_left = QtWidgets.QHBoxLayout()
        hdr_left.setSpacing(10)
        hdr_icon = QtWidgets.QLabel("📥")
        hdr_icon.setStyleSheet("font-size:26px; background:transparent;")
        hdr_left.addWidget(hdr_icon)

        hdr_text_block = QtWidgets.QVBoxLayout()
        hdr_text_block.setSpacing(1)
        header = QtWidgets.QLabel("Receiver Dashboard Overview")
        header.setStyleSheet("""
            font-size: 24px; font-weight: bold;
            color: #1e3a5f; background: transparent; letter-spacing:0.5px;
        """)
        hdr_text_block.addWidget(header)
        hdr_left.addLayout(hdr_text_block)
        hdr_row.addLayout(hdr_left)

        hdr_row.addStretch()

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
        time_lbl.setText(datetime.now().strftime("%d %b %Y  |  %H:%M"))
        time_badge_layout.addWidget(time_lbl)

        hdr_row.addWidget(time_badge)
        hdr_row.addSpacing(8)
        l0.addLayout(hdr_row)

        accent_line = QtWidgets.QFrame()
        accent_line.setFrameShape(QtWidgets.QFrame.HLine)
        accent_line.setFixedHeight(2)
        accent_line.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1a56db, stop:0.5 #3b82f6, stop:1 transparent); border:none;")
        l0.addWidget(accent_line)

        # ---- STAT CARDS (SAME AS SENDER) ----
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

        card_rcvd,   self.lbl_stat_rcvd   = home_card("Files Received", "📁", "#0ea5e9", "#bae6fd", "#f0f9ff")
        card_data,   self.lbl_stat_size   = home_card("Total Data (MB)", "💾", "#6366f1", "#c7d2fe", "#eef2ff")
        card_dec,    self.lbl_stat_dec    = home_card("Decrypted Files", "🔓", "#16a34a", "#bbf7d0", "#f0fdf4")
        card_int,    self.lbl_stat_int    = home_card("Integrity Passed", "✅", "#16a34a", "#bbf7d0", "#f0fdf4")
        card_fail,   self.lbl_stat_failed = home_card("Failed/Corrupt", "❌", "#dc2626", "#fecaca", "#fff5f5")

        h_layout = QtWidgets.QHBoxLayout()
        h_layout.setSpacing(16)
        h_layout.setAlignment(QtCore.Qt.AlignLeft)
        for c in [card_rcvd, card_data, card_dec, card_int, card_fail]:
            h_layout.addWidget(c)
        h_layout.addStretch()
        l0.addLayout(h_layout)

        # ---- RECENT ACTIVITY PANEL (SAME AS SENDER) ----
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
        """)
        apl.addWidget(self.activity_list)

        l0.addWidget(activity_panel, 1)
        self.stack.addWidget(pg0)

        # ================= 2. RECEIVE DATA (SENDER-LIKE STYLE) =================
        pg1 = QtWidgets.QWidget()
        pg1.setStyleSheet("background: #eff6ff;")
        l1 = QtWidgets.QVBoxLayout(pg1)
        l1.setContentsMargins(40, 30, 40, 30)

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

        title_label = QtWidgets.QLabel("Data Acquisition Protocols")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1a56db;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        transfer_layout.addWidget(title_label)


        # Row 1: USB and HDD
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(30)
        row1.setAlignment(QtCore.Qt.AlignCenter)

        usb_btn = QtWidgets.QPushButton("💾  USB Import")
        usb_btn.setFixedSize(200, 55)
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
        usb_btn.clicked.connect(lambda: self.handle_method("USB Import"))
        row1.addWidget(usb_btn)

        hdd_btn = QtWidgets.QPushButton("💽  HDD Scan")
        hdd_btn.setFixedSize(200, 55)
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
        hdd_btn.clicked.connect(lambda: self.handle_method("HDD Scan"))
        row1.addWidget(hdd_btn)
        transfer_layout.addLayout(row1)

        # Row 2: LAN and Email
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(30)
        row2.setAlignment(QtCore.Qt.AlignCenter)

        lan_btn = QtWidgets.QPushButton("🌐  LAN Listener")
        lan_btn.setFixedSize(200, 55)
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
        lan_btn.clicked.connect(lambda: self.handle_method("LAN Listener"))
        row2.addWidget(lan_btn)

        email_btn = QtWidgets.QPushButton("📧  Email Fetch")
        email_btn.setFixedSize(200, 55)
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
        email_btn.clicked.connect(lambda: self.handle_method("Email Fetch"))
        row2.addWidget(email_btn)
        transfer_layout.addLayout(row2)

        # Row 3: Google Drive
        row3 = QtWidgets.QHBoxLayout()
        row3.setAlignment(QtCore.Qt.AlignCenter)

        gdrive_btn = QtWidgets.QPushButton("☁️  Google Drive")
        gdrive_btn.setFixedSize(220, 55)
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
        gdrive_btn.clicked.connect(lambda: self.handle_method("Google Drive"))
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

        status_layout = QtWidgets.QHBoxLayout()
        status_icon = QtWidgets.QLabel("⚡")
        status_icon.setStyleSheet("font-size: 14px;")
        status_layout.addWidget(status_icon)

        self.lbl_t = QtWidgets.QLabel("Status: Ready to receive data")
        self.lbl_t.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a56db;")
        status_layout.addWidget(self.lbl_t)
        status_layout.addStretch()
        progress_layout.addLayout(status_layout)

        self.p_bar = QtWidgets.QProgressBar()
        self.p_bar.setFixedHeight(18)
        self.p_bar.setFormat("%p%")
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

        l1.addWidget(transfer_card)
        l1.addStretch()
        self.stack.addWidget(pg1)

        # ================= 3. RECEIVED VAULT (SENDER-LIKE) =================
        pg2 = QtWidgets.QWidget()
        pg2.setStyleSheet("background: #eff6ff;")
        l2 = QtWidgets.QVBoxLayout(pg2)
        l2.setContentsMargins(30, 28, 30, 28)
        l2.setSpacing(14)

        files_hdr = QtWidgets.QHBoxLayout()
        files_title = QtWidgets.QLabel("📁  Received Evidence Vault")
        files_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background:transparent;")
        files_hdr.addWidget(files_title)
        files_hdr.addStretch()
        l2.addLayout(files_hdr)

        # Search bar + Refresh row
        files_search_row = QtWidgets.QHBoxLayout()
        files_search_row.setSpacing(10)

        self.vault_search = QtWidgets.QLineEdit()
        self.vault_search.setPlaceholderText("🔍  Search files by name, method, size...")
        self.vault_search.setFixedHeight(40)
        self.vault_search.setStyleSheet("""
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

        refresh_btn = QtWidgets.QPushButton("🔄  Refresh")
        refresh_btn.setFixedSize(110, 40)
        refresh_btn.setCursor(QtCore.Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
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
        refresh_btn.clicked.connect(self.refresh_vault_table)

        files_search_row.addWidget(self.vault_search)
        files_search_row.addWidget(refresh_btn)
        l2.addLayout(files_search_row)

        self.tab_vault = QtWidgets.QTableWidget(0, 5)
        self.tab_vault.setColumnCount(5)
        self.tab_vault.setHorizontalHeaderLabels(["Filename", "Size (KB)", "Status", "Received Via", "Action"])
        self.tab_vault.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tab_vault.setStyleSheet("""
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

        self.vault_search.textChanged.connect(self.filter_vault)
        l2.addWidget(self.tab_vault)

        # Clear All button at bottom
        clear_vault_btn = QtWidgets.QPushButton("🗑️  Clear All Vault Files")
        clear_vault_btn.setFixedHeight(40)
        clear_vault_btn.setStyleSheet("""
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
        clear_vault_btn.clicked.connect(self.clear_vault_files)
        l2.addWidget(clear_vault_btn)

        self.stack.addWidget(pg2)

        # ================= 4. DECRYPTION MODULE =================
        # ================= 4. DECRYPTION MODULE (UPDATED & FIXED) =================
        pg3 = QtWidgets.QWidget()
        pg3.setStyleSheet("background: #eff6ff;")
        l3 = QtWidgets.QVBoxLayout(pg3)
        l3.setContentsMargins(40, 30, 40, 30)

        dec_card = QtWidgets.QFrame()
        dec_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 18px;
                border: 1.5px solid #bfdbfe;
            }
        """)
        dec_layout = QtWidgets.QVBoxLayout(dec_card)
        dec_layout.setContentsMargins(30, 28, 30, 28)
        dec_layout.setSpacing(20)

        # Header Section (Extra lines removed)
        header_widget = QtWidgets.QWidget()
        header_h_layout = QtWidgets.QHBoxLayout(header_widget)
        header_h_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QtWidgets.QLabel("🔓")
        icon_label.setStyleSheet("font-size: 30px; background: transparent;")
        header_h_layout.addWidget(icon_label)
        
        header_title = QtWidgets.QLabel("Decryption Engine")
        header_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b; background: transparent;")
        header_h_layout.addWidget(header_title)
        header_h_layout.addStretch()
        dec_layout.addWidget(header_widget)

        # Common GroupBox Style
        GS = """
            QGroupBox {
                font-weight: bold; color: #1a56db; border: 1.5px solid #93c5fd;
                border-radius: 12px; margin-top: 10px; padding-top: 15px; background: #eff6ff;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
        """

        # 1. File Source Section
        file_section = QtWidgets.QGroupBox("📁 1. FORENSIC DATA SOURCE")
        file_section.setStyleSheet(GS)
        file_l = QtWidgets.QHBoxLayout(file_section)
        self.dec_path = QtWidgets.QLineEdit() # Existing variable name
        self.dec_path.setPlaceholderText("Select encrypted package (.bin)...")
        self.dec_path.setStyleSheet("height: 40px; border-radius: 8px; padding: 7px; border: 1px solid #cbd5e1; background: white;")
        btn_browse = QtWidgets.QPushButton("Browse")
        btn_browse.setFixedSize(100, 35)
        btn_browse.setStyleSheet("background: #1a56db; color: white; font-weight: bold; border-radius: 6px;")
        
        # Connection to your existing function
        btn_browse.clicked.connect(self.select_file_for_dec) 
        
        file_l.addWidget(self.dec_path)
        file_l.addWidget(btn_browse)
        dec_layout.addWidget(file_section)

        # 2. AES Key Section (Keeping it exactly as requested)
        key_section = QtWidgets.QGroupBox("🔑 2. DECRYPTION KEY")
        key_section.setStyleSheet(GS)
        key_l = QtWidgets.QVBoxLayout(key_section)
        self.dec_key = QtWidgets.QLineEdit() # Existing variable name
        self.dec_key.setPlaceholderText("🔑 Key will appear here after selecting file...")
        self.dec_key.setStyleSheet("height: 40px; border-radius: 8px; padding: 7px; border: 1px solid #cbd5e1; background: #f8fafc;")
        key_l.addWidget(self.dec_key)
        dec_layout.addWidget(key_section)

        # 3. New Box for Start Secure Decryption (Separate button at the bottom)
        self.btn_start_dec = QtWidgets.QPushButton("🚀 Start Secure Decryption")
        self.btn_start_dec.setFixedHeight(55)
        self.btn_start_dec.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_start_dec.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a56db, stop:1 #2563eb);
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 12px;
                border: none;
            }
            QPushButton:hover {
                background: #1e40af;
            }
            QPushButton:pressed {
                background: #1e3a8a;
            }
        """)
        
        # Connection to your existing decryption function
        self.btn_start_dec.clicked.connect(self.run_decryption)
        
        dec_layout.addWidget(self.btn_start_dec)

        l3.addWidget(dec_card)
        l3.addStretch()
        self.stack.addWidget(pg3)

        # ================= 5. INTEGRITY CHECK =================
        pg4 = QtWidgets.QWidget()
        pg4.setStyleSheet("background: #eff6ff;")
        l4 = QtWidgets.QVBoxLayout(pg4)
        l4.setContentsMargins(80, 40, 80, 40)

        int_box = QtWidgets.QGroupBox("🔒  Data Integrity Verification")
        int_box.setMinimumHeight(380)
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

        self.hash_input = QtWidgets.QLineEdit()
        self.hash_input.setPlaceholderText("  Select decrypted file to verify...")
        self.hash_input.setFixedHeight(46)
        self.hash_input.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #93c5fd; border-radius: 8px;
                font-size: 14px; padding-left: 12px;
                background: #f8fbff; color: #1e3a5f;
            }
            QLineEdit:focus { border: 1.5px solid #1a56db; }
        """)

        btn_sel = QtWidgets.QPushButton("📁  Select Decrypted File")
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

        self.expected_hash = QtWidgets.QLineEdit()
        self.expected_hash.setPlaceholderText("  Paste Sender's Original SHA-256 Hash Here...")
        self.expected_hash.setFixedHeight(46)
        self.expected_hash.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #93c5fd; border-radius: 8px;
                font-size: 14px; padding-left: 12px;
                background: #f8fbff; color: #1e3a5f;
            }
            QLineEdit:focus { border: 1.5px solid #1a56db; }
        """)

        self.hash_display = QtWidgets.QLabel("Status: Awaiting verification...")
        self.hash_display.setWordWrap(True)
        self.hash_display.setMinimumHeight(55)
        self.hash_display.setMaximumHeight(55)
        self.hash_display.setAlignment(QtCore.Qt.AlignCenter)
        self.hash_display.setStyleSheet("""
            padding: 10px;
            background: #eff6ff;
            border-radius: 8px;
            color: #1d4ed8;
            border: 1px dashed rgba(0,212,255,0.35);
            font-family: 'Consolas'; font-size: 14px;
        """)

        btn_vi = QtWidgets.QPushButton("🔄  VERIFY INTEGRITY")
        btn_vi.setFixedHeight(52)
        btn_vi.setStyleSheet("""
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
        btn_vi.clicked.connect(self.run_integrity_check)

        for w in [self.hash_input, btn_sel, self.expected_hash, self.hash_display, btn_vi]:
            il.addWidget(w)

        l4.addWidget(int_box)
        l4.addStretch()
        self.stack.addWidget(pg4)

        # ================= 6. RECEIVE HISTORY (SENDER-LIKE) =================
        pg5 = QtWidgets.QWidget()
        pg5.setStyleSheet("background: #eff6ff;")
        l5 = QtWidgets.QVBoxLayout(pg5)
        l5.setContentsMargins(30, 28, 30, 28)
        l5.setSpacing(14)

        hist_header = QtWidgets.QHBoxLayout()
        hist_title = QtWidgets.QLabel("📊  Receive History Logs")
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
        clear_btn.clicked.connect(self.clear_history)
        hist_header.addWidget(clear_btn)
        l5.addLayout(hist_header)

        self.hist_search = QtWidgets.QLineEdit()
        self.hist_search.setPlaceholderText("🔍  Search history by file, method or status...")
        self.hist_search.setFixedHeight(40)
        self.hist_search.setStyleSheet("""
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
        self.hist_search.textChanged.connect(self.filter_history)
        l5.addWidget(self.hist_search)

        self.tab_hist = QtWidgets.QTableWidget(0, 4)
        self.tab_hist.setColumnCount(4)
        self.tab_hist.setHorizontalHeaderLabels(["Timestamp", "Received File", "Method", "Status"])
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

        l5.addWidget(self.tab_hist)
        self.stack.addWidget(pg5)

    # ═══════════════════════════════════════════════════════════
    # ALL BACKEND METHODS BELOW REMAIN EXACTLY THE SAME
    # (NO CHANGES TO ANY LOGIC)
    # ═══════════════════════════════════════════════════════════

    def handle_method(self, name):
        """Routes to the correct receive method based on button clicked"""
        try:
            if name == "USB Import":
                self.waiting_for_hdd = True
                self.current_hw_method = "USB Import"
                self.existing_drives = [
                    f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")
                ]
                self.lbl_t.setText("Status: Waiting for USB drive to be plugged...")
                self.p_bar.setValue(0)
                QtWidgets.QMessageBox.information(
                    self, "USB Import",
                    "Monitoring Active!\n\nPlug in your USB drive.\n"
                    "System will fetch only the LATEST forensic package."
                )
            elif name == "HDD Scan":
                self.waiting_for_hdd = True
                self.current_hw_method = "HDD Scan"
                self.existing_drives = [
                    f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")
                ]
                self.lbl_t.setText("Status: Waiting for HDD to be connected...")
                self.p_bar.setValue(0)
                QtWidgets.QMessageBox.information(
                    self, "HDD Scan",
                    "Monitoring Active!\n\nConnect your External HDD.\n"
                    "System will fetch only the LATEST forensic package."
                )
            elif name == "LAN Listener":
                self.activity_list.addItem("● LAN: Starting Listener on Port 5000...")
                threading.Thread(target=self.start_lan_server, daemon=True).start()
                QtWidgets.QMessageBox.information(
                    self, "LAN Mode", "Listening for incoming files from Sender..."
                )
            elif name == "Email Fetch":
                self.activity_list.addItem("● Vault: Checking for pending forensic packages...")
                self.lbl_t.setText("Status: Querying Vault...")
                self.p_bar.setValue(10)
                threading.Thread(
                    target=self.fetch_from_vault, daemon=True
                ).start()
            elif name == "Google Drive":
                url, ok = QtWidgets.QInputDialog.getText(
                    self, "Google Drive Pull", "Enter Google Drive Share Link:"
                )
                if ok and url:
                    self.lbl_t.setText("Status: Connecting to Google Drive...")
                    self.p_bar.setValue(10)
                    threading.Thread(
                        target=self.download_from_gdrive, args=(url,), daemon=True
                    ).start()
        except Exception as e:
            self.add_to_receive_history("Error Occurred", name, "Failed")
            self.update_dashboard_stats()
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to execute {name}: {e}")

    def detect_new_hardware(self, method="HDD/USB"):
        current = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        new = [d for d in current if d not in self.existing_drives]

        if self.waiting_for_hdd and new:
            target = new[0]
            folder = os.path.join(target, "Forensic_Transfers")

            if os.path.exists(folder):
                files = [
                    os.path.join(folder, f)
                    for f in os.listdir(folder) if f.endswith(".aes")
                ]
                if files:
                    self.waiting_for_hdd = False
                    latest = max(files, key=os.path.getmtime)
                    dst = os.path.join(self.RECEIVED_DIR, os.path.basename(latest))
                    threading.Thread(
                        target=self.copy_with_progress, args=(latest, dst, self.current_hw_method), daemon=True
                    ).start()
                    self.activity_list.addItem(f"● [HDD] Fetching: {os.path.basename(latest)}")
                else:
                    self.lbl_t.setText("Status: No .aes files found on drive.")
            else:
                self.lbl_t.setText("Status: 'Forensic_Transfers' folder not found on drive.")

        self.existing_drives = current

    def copy_with_progress(self, src, dst, method="HDD/USB"):
        import time
        try:
            total = os.path.getsize(src)
            copied = 0
            with open(src, 'rb') as fs, open(dst, 'wb') as fd:
                while True:
                    chunk = fs.read(65536)
                    if not chunk:
                        break
                    fd.write(chunk)
                    copied += len(chunk)
                    pct = int((copied / total) * 100)
                    self.sig_progress.emit(pct)
                    self.sig_status.emit(f"Status: Receiving from HDD... {pct}%")
                    if total < 10 * 1024 * 1024:
                        time.sleep(0.02)

            fname = os.path.basename(dst)
            self.sig_progress.emit(100)
            self.sig_status.emit(f"Status: {method} File Received Successfully ✅")
            self.add_to_receive_history(fname, method, "Success")

            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE vault_transfers SET status = "FETCHED",
                    fetched_at = ?
                    WHERE file_name = ? AND status = "PENDING"
                ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fname))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[USB] vault_transfers update error: {e}")

            self.sig_refresh_vault.emit()
            self.sig_refresh_stats.emit()
        except Exception as e:
            print(f"HDD Copy Error: {e}")
            self.sig_status.emit("Status: HDD Transfer Failed ❌")

    def start_lan_server(self):
        server = None
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', 5000))
            server.listen(1)

            self.sig_progress.emit(0)
            self.sig_status.emit("Status: Waiting for Sender on LAN...")

            conn, addr = server.accept()
            conn.settimeout(30.0)

            total = 0
            save_name = f"LAN_RECV_{datetime.now().strftime('%H%M%S')}.aes"

            try:
                handshake = conn.recv(1024).decode('utf-8').strip()
                if '|' in handshake:
                    parts = handshake.split('|', 1)
                    if parts[0].isdigit():
                        total = int(parts[0])
                        save_name = parts[1].strip()
                elif handshake.isdigit():
                    total = int(handshake)
                conn.send(b"ACK_SIZE")
                self.sig_status.emit(f"Status: Receiving '{save_name}' ({total} bytes)...")
            except Exception as e:
                print(f"[LAN] Handshake error: {e}")
                conn.send(b"ACK_SIZE")

            path = os.path.join(self.RECEIVED_DIR, save_name)
            received = 0
            with open(path, "wb") as f:
                while True:
                    chunk = conn.recv(16384)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if total > 0:
                        pct = min(int((received / total) * 100), 99)
                        self.sig_progress.emit(pct)
                        self.sig_status.emit(f"Status: Receiving... {pct}%")
            conn.close()

            if received > 0:
                self.sig_progress.emit(100)
                self.sig_status.emit(f"Status: LAN Transfer Complete ✅")
                self.add_to_receive_history(save_name, "LAN", "Success")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur_db = conn.cursor()
                    cur_db.execute('''
                        UPDATE vault_transfers
                        SET status = "FETCHED", fetched_at = ?
                        WHERE file_name = ? AND status = "PENDING"
                    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), save_name))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[LAN] vault_transfers update error: {e}")
                write_audit_log(
                    username=self.user_name, role="Receiver",
                    action="LAN_FILE_RECEIVED", method="LAN",
                    file_name=save_name,
                    details=f"From: {addr[0]} | Size: {received} bytes"
                )
                self.sig_refresh_vault.emit()
                self.sig_refresh_stats.emit()
                self.sig_notification.emit(f"LAN file received: {save_name}", "Success")
            else:
                self.sig_status.emit("Status: LAN Transfer Failed ❌")
        except Exception as e:
            print(f"LAN Error: {e}")
            self.sig_status.emit("Status: LAN Error ❌")
        finally:
            if server:
                server.close()

    def fetch_from_vault(self):
        import time
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE name = ?", (self.user_name,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                self.sig_status.emit("Status: User not found in database ❌")
                return
            receiver_email = row[0]
            cursor.execute('''
                SELECT id, sender_name, vault_path, encrypted_aes_key,
                       original_hash, file_name, case_id, investigator
                FROM vault_transfers
                WHERE receiver_email = ? AND status = "PENDING"
                ORDER BY created_at ASC
            ''', (receiver_email,))
            pending = cursor.fetchall()
            conn.close()
            if not pending:
                self.sig_status.emit("Status: No pending files in Vault ✅")
                self.sig_progress.emit(0)
                return
            self.sig_status.emit(f"Status: Found {len(pending)} pending file(s)...")
            self.sig_progress.emit(20)
            fetched_count = 0
            for record in pending:
                (transfer_id, sender_name, vault_path,
                 encrypted_aes_key, original_hash,
                 file_name, case_id, investigator) = record
                original_hash = decrypt_field(original_hash)
                if not os.path.exists(vault_path):
                    print(f"[Vault] File missing on disk: {vault_path}")
                    continue
                dest_path = os.path.join(self.RECEIVED_DIR, file_name)
                try:
                    shutil.copy2(vault_path, dest_path)
                except Exception as e:
                    print(f"[Vault] Copy failed: {e}")
                    continue
                self.sig_status.emit(f"Status: Decrypting key for {file_name}...")
                self.sig_progress.emit(50)
                try:
                    aes_key = decrypt_aes_key(encrypted_aes_key, self.user_name)
                except FileNotFoundError:
                    self.sig_status.emit("Status: Private key missing ❌")
                    QtWidgets.QMessageBox.critical(
                        None, "Private Key Missing",
                        f"No private key found for '{self.user_name}'.\n\n"
                        "This happens if you registered on a different machine.\n"
                        "Solution: Re-register your account on this machine."
                    )
                    return
                except ValueError as e:
                    self.sig_status.emit("Status: Key decryption failed ❌")
                    print(f"[Vault] RSA error: {e}")
                    continue
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS session_keys (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            transfer_id INTEGER UNIQUE,
                            receiver_email TEXT NOT NULL,
                            file_name TEXT NOT NULL,
                            aes_key TEXT NOT NULL,
                            original_hash TEXT NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (transfer_id) REFERENCES vault_transfers(id)
                        )
                    ''')
                    cursor.execute('''
                        INSERT OR IGNORE INTO session_keys
                            (transfer_id, receiver_email, file_name, aes_key, original_hash)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (transfer_id, receiver_email, file_name, encrypt_field(aes_key), encrypt_field(original_hash)))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[Vault] session_keys error: {e}")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE vault_transfers
                        SET status = "FETCHED", fetched_at = ?
                        WHERE id = ?
                    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), transfer_id))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"[Vault] DB update error: {e}")
                write_audit_log(
                    username=self.user_name, role="Receiver",
                    action="VAULT_FILE_FETCHED", method="Email (Vault)",
                    file_name=file_name,
                    details=f"From: {sender_name} | Case: {case_id} | Hash: {original_hash[:20]}..."
                )
                write_system_log(
                    event_source="Email (Vault)",
                    event_type="FILE_FETCHED",
                    details=f"File: {file_name} | From: {sender_name} | Receiver: {self.user_name}"
                )
                self.add_to_receive_history(file_name, "Email (Vault)", "Success")
                fetched_count += 1
                time.sleep(0.3)
            self.sig_progress.emit(100)
            if fetched_count > 0:
                self.sig_status.emit(f"Status: {fetched_count} file(s) fetched from Vault ✅")
                self.sig_refresh_vault.emit()
                self.sig_refresh_stats.emit()
                self.sig_notification.emit(f"{fetched_count} new forensic file(s) received", "Success")
            else:
                self.sig_status.emit("Status: No new files could be fetched")
        except Exception as e:
            print(f"[Vault Fetch Error] {e}")
            self.sig_status.emit("Status: Vault fetch error ❌")

    def download_from_gdrive(self, url):
        import time
        import requests

        dest = None
        try:
            # ── Step 1: Extract file ID from any Drive link format ──
            file_id = ""
            if '/d/' in url:
                file_id = url.split('/d/')[1].split('/')[0]
            elif 'id=' in url:
                file_id = url.split('id=')[-1].split('&')[0]
            elif 'open?id=' in url:
                file_id = url.split('open?id=')[-1].split('&')[0]

            if not file_id:
                self.sig_status.emit("Status: Invalid Google Drive link ❌")
                self.sig_progress.emit(0)
                return

            self.sig_status.emit("Status: Connecting to Google Drive...")
            self.sig_progress.emit(10)

            # ── Step 2: Build direct download URL ───────────────────
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            session = requests.Session()

            # First request — may get a virus-scan warning page for large files
            response = session.get(download_url, stream=True, timeout=30)

            # ── Step 3: Handle Google's large-file confirmation page ─
            # Google returns an HTML page with a confirm token for files > ~40MB
            if 'text/html' in response.headers.get('Content-Type', ''):
                confirm_token = None
                for key, value in response.cookies.items():
                    if key.startswith('download_warning'):
                        confirm_token = value
                        break
                if confirm_token is None:
                    # Try parsing from response body
                    body = response.text
                    if 'confirm=' in body:
                        import re
                        match = re.search(r'confirm=([0-9A-Za-z_\-]+)', body)
                        if match:
                            confirm_token = match.group(1)

                if confirm_token:
                    download_url = (
                        f"https://drive.google.com/uc?export=download"
                        f"&id={file_id}&confirm={confirm_token}"
                    )
                    response = session.get(download_url, stream=True, timeout=30)
                else:
                    # Newer Google Drive — try v3 export URL
                    download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
                    response = session.get(download_url, stream=True, timeout=30)

            response.raise_for_status()

            # ── Step 4: Determine filename from headers if possible ──
            fname = f"GDrive_{random.randint(1000, 9999)}.aes"
            cd = response.headers.get('Content-Disposition', '')
            if 'filename=' in cd:
                import re
                match = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)', cd)
                if match:
                    fname = match.group(1).strip().strip('"').strip("'")

            dest = os.path.join(self.RECEIVED_DIR, fname)

            # ── Step 5: Stream download with real progress bar ───────
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 65536  # 64 KB chunks

            self.sig_status.emit("Status: Downloading from Google Drive...")
            self.sig_progress.emit(15)

            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 90) + 5  # 5%→95%
                        else:
                            # Unknown size: animate progress slowly up to 90%
                            pct = min(int(15 + (downloaded / (1024 * 1024)) * 5), 90)
                        self.sig_progress.emit(pct)
                        self.sig_status.emit(
                            f"Status: Downloading... "
                            f"{downloaded // 1024} KB"
                            + (f" / {total_size // 1024} KB" if total_size else "")
                        )

            # ── Step 6: Verify downloaded file is not empty/HTML ────
            if not os.path.exists(dest) or os.path.getsize(dest) == 0:
                raise Exception("Downloaded file is empty — check sharing permissions.")

            # Quick check: if Google returned an HTML error page instead of file
            with open(dest, 'rb') as f:
                header_bytes = f.read(10)
            if header_bytes.startswith(b'<!DOCTYPE') or header_bytes.startswith(b'<html'):
                os.remove(dest)
                raise Exception(
                    "Google returned an HTML page instead of the file.\n"
                    "Make sure the file is shared as 'Anyone with the link can view'."
                )

            # ── Step 7: Success ──────────────────────────────────────
            self.sig_progress.emit(100)
            self.sig_status.emit(f"✅  File Received Successfully — {fname}")
            self.add_to_receive_history(fname, "Google Drive", "Success")
            write_audit_log(
                username=self.user_name, role="Receiver",
                action="GDRIVE_FILE_RECEIVED", method="Google Drive",
                file_name=fname,
                details=f"File ID: {file_id} | Size: {downloaded} bytes"
            )
            self.sig_refresh_vault.emit()
            self.sig_refresh_stats.emit()
            self.sig_notification.emit(f"Google Drive file received: {fname}", "Success")

        except Exception as e:
            print(f"[G-Drive Error] {e}")
            # Clean up partial download if it exists
            if dest and os.path.exists(dest):
                try:
                    os.remove(dest)
                except Exception:
                    pass
            self.sig_status.emit(f"Status: G-Drive Failed — {str(e)[:60]} ❌")
            self.sig_progress.emit(0)
            self.add_to_receive_history("Unknown", "Google Drive", "Failed")

    def select_file_for_dec(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select AES File", self.RECEIVED_DIR)
        if not f:
            return
        self.dec_path.setText(f)
        file_name = os.path.basename(f)
        self.dec_key.clear()
        self.dec_key.setStyleSheet(
            "padding:12px; font-size:15px; border:1px solid #cbd5e1; "
            "border-radius:8px; background:#f8fafc;"
        )
        self.dec_key.setPlaceholderText("🔑 Enter 32-character AES Key...")
        self.dec_key.setEnabled(True)
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE name = ?", (self.user_name,))
            user_row = cursor.fetchone()
            if not user_row:
                conn.close()
                return
            current_user_email = user_row[0]
            cursor.execute('''
                SELECT aes_key, original_hash, receiver_email
                FROM session_keys
                WHERE file_name = ?
                ORDER BY id DESC LIMIT 1
            ''', (file_name,))
            key_row = cursor.fetchone()
            conn.close()
        except Exception as e:
            print(f"[Identity Gate Error] {e}")
            return
        if not key_row:
            self.dec_key.setPlaceholderText("🔑 File received via USB/LAN — enter key manually")
            return
        aes_key, original_hash, authorized_email = key_row
        aes_key = decrypt_field(aes_key)
        original_hash = decrypt_field(original_hash)
        if current_user_email.lower() != authorized_email.lower():
            self.dec_key.clear()
            self.dec_key.setEnabled(False)
            self.dec_key.setStyleSheet(
                "padding:12px; font-size:15px; border:2px solid #ef4444; "
                "border-radius:8px; background:#fef2f2; color:#ef4444;"
            )
            self.dec_key.setPlaceholderText("🚫 Access Denied — this file is not assigned to you")
            self.dec_path.clear()
            write_audit_log(
                username=self.user_name, role="Receiver",
                action="UNAUTHORIZED_KEY_ACCESS", method="Decryption Module",
                file_name=file_name,
                details=f"Attempted by: {current_user_email} | Authorized: {authorized_email}"
            )
            write_anomaly_alert(
                "UNAUTHORIZED_DECRYPTION_ATTEMPT",
                f"{self.user_name} ({current_user_email}) tried to decrypt "
                f"file assigned to {authorized_email} | File: {file_name}",
                "CRITICAL"
            )
            QtWidgets.QMessageBox.critical(
                self, "🚫 Access Denied",
                f"This file was not sent to your account.\n\n"
                f"File is assigned to a different receiver.\n\n"
                "This unauthorized access attempt has been logged."
            )
            return
        self.dec_key.setText(aes_key)
        self.dec_key.setEnabled(True)
        self.dec_key.setStyleSheet(
            "padding:12px; font-size:15px; border:2px solid #16a34a; "
            "border-radius:8px; background:#f0fdf4;"
        )
        self._pending_hash = original_hash
        self._pending_file = file_name

    def run_decryption(self):
        path = self.dec_path.text().strip()
        key = self.dec_key.text().strip()
        if not path:
            QtWidgets.QMessageBox.warning(self, "File Missing", "⚠️ Select a file to decrypt.")
            return
        if not key:
            QtWidgets.QMessageBox.warning(
                self, "Key Missing",
                "⚠️ No AES key found.\n\n"
                "If you fetched via Vault, browse the file again — key is auto-filled.\n"
                "Otherwise enter the 32-character key manually."
            )
            return
        if len(key) != 32:
            QtWidgets.QMessageBox.warning(self, "Invalid Key", f"⚠️ Key must be 32 characters. (Current: {len(key)})")
            return
        try:
            with open(path, 'rb') as f:
                data = f.read()
            iv, encrypted = data[:16], data[16:]
            cipher = Cipher(
                algorithms.AES(key.encode()), modes.CBC(iv), backend=default_backend()
            )
            decryptor = cipher.decryptor()
            padded = decryptor.update(encrypted) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            original = unpadder.update(padded) + unpadder.finalize()
            out = os.path.join(
                self.RECEIVED_DIR,
                "DECRYPTED_" + os.path.basename(path).replace(".aes", "")
            )
            with open(out, 'wb') as f:
                f.write(original)
            try:
                conn = sqlite3.connect('users.db')
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE vault_transfers SET status = "DECRYPTED"
                    WHERE file_name = ? AND status = "FETCHED"
                ''', (os.path.basename(path),))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Decrypt] DB update error: {e}")
            write_audit_log(
                username=self.user_name, role="Receiver",
                action="FILE_DECRYPTED", method="AES-256",
                file_name=os.path.basename(out),
                details=f"Source: {os.path.basename(path)}"
            )

            # ── forensic_receipts table ───────────────────────────
            try:
                conn = sqlite3.connect(DB_PATH)
                cur  = conn.cursor()
                cur.execute(
                    "INSERT INTO forensic_receipts "
                    "(generated_by, hash_confirmed, receipt_path) "
                    "VALUES (?, ?, ?)",
                    (self.user_name,
                     encrypt_field(getattr(self, '_pending_hash', 'N/A') or 'N/A'),
                     out)
                )
                conn.commit(); conn.close()
            except Exception as e:
                print(f"[forensic_receipts] {e}")

            # ── system_monitor_logs table ─────────────────────────
            write_system_log(
                event_source="Decryption",
                event_type="FILE_DECRYPTED",
                details=f"File: {os.path.basename(out)} | Receiver: {self.user_name}"
            )
            self._pending_hash = None
            self._pending_file = None
            self.refresh_vault_table()
            self.sig_notification.emit(f"Decryption Success: {os.path.basename(path)}", "Success")
            QtWidgets.QMessageBox.information(
                self, "Decryption Success ✅",
                f"File decrypted successfully!\n"
                f"Saved as: {os.path.basename(out)}\n\n"
                "To verify file integrity go to:\n"
                "Integrity Check → Browse the decrypted file."
            )
            self.open_case_report_dialog(decrypted_file=out)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Decryption Failed", f"Error:\n{e}")
            self.sig_notification.emit("Decryption Failed!", "Failed")

    def select_file_for_hash(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Decrypted File", self.RECEIVED_DIR)
        if not f:
            return
        file_name = os.path.basename(f)
        if file_name.endswith(".aes"):
            self.hash_display.setText(
                "⚠️ Wrong file selected!\n\n"
                "Integrity check must be performed on the DECRYPTED file.\n\n"
                "Steps:\n"
                "1. Go to Decryption Module first\n"
                "2. Decrypt the .aes file\n"
                "3. Come back here and browse the DECRYPTED file"
            )
            self.hash_display.setStyleSheet(
                "background:#78350f; color:#fbbf24; padding:15px; "
                "border-radius:12px; font-weight:bold;"
            )
            return
        self.hash_input.setText(f)
        self.expected_hash.clear()
        self.expected_hash.setStyleSheet(
            "padding:12px; font-size:15px; border:1px solid #cbd5e1; "
            "border-radius:8px; background:#f8fafc;"
        )
        self.expected_hash.setPlaceholderText("Paste Sender's Hash Here...")
        self.expected_hash.setReadOnly(False)
        if file_name.startswith("DECRYPTED_ENCRYPTED_"):
            stripped = file_name[len("DECRYPTED_ENCRYPTED_"):]
        else:
            stripped = file_name
        aes_lookup_name = f"ENCRYPTED_{stripped}.aes"
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE name = ?", (self.user_name,))
            user_row = cursor.fetchone()
            if not user_row:
                conn.close()
                self.expected_hash.setPlaceholderText("User not found in DB — paste hash manually")
                return
            current_user_email = user_row[0]
            cursor.execute('''
                SELECT original_hash, receiver_email
                FROM session_keys
                WHERE file_name = ?
                ORDER BY id DESC LIMIT 1
            ''', (aes_lookup_name,))
            hash_row = cursor.fetchone()
            conn.close()
        except Exception as e:
            print(f"[Hash Lookup Error] {e}")
            return
        if not hash_row:
            self.expected_hash.setPlaceholderText("File received via USB/LAN — paste sender's SHA-256 hash manually")
            self.hash_display.setText("ℹ️ No vault record found for this file.\nPaste the sender's SHA-256 hash manually above.")
            self.hash_display.setStyleSheet("background:#1e293b; color:#94a3b8; padding:15px; border-radius:12px;")
            return
        original_hash, authorized_email = hash_row
        original_hash = decrypt_field(original_hash)
        if current_user_email.lower() != authorized_email.lower():
            self.hash_input.clear()
            self.expected_hash.clear()
            self.expected_hash.setReadOnly(True)
            self.expected_hash.setStyleSheet(
                "padding:12px; font-size:15px; border:2px solid #ef4444; "
                "border-radius:8px; background:#fef2f2; color:#ef4444;"
            )
            self.expected_hash.setPlaceholderText("🚫 Access Denied — file not assigned to you")
            self.hash_display.setText("🚫 ACCESS DENIED — Unauthorized access attempt logged.")
            self.hash_display.setStyleSheet(
                "background:#7f1d1d; color:#fca5a5; padding:15px; "
                "border-radius:12px; font-weight:bold;"
            )
            write_audit_log(
                username=self.user_name, role="Receiver",
                action="UNAUTHORIZED_HASH_ACCESS", method="Integrity Check",
                file_name=file_name,
                details=f"Attempted by: {current_user_email} | Authorized: {authorized_email}"
            )
            return
        self.expected_hash.setText(original_hash)
        self.expected_hash.setReadOnly(True)
        self.expected_hash.setStyleSheet(
            "padding:12px; font-size:15px; border:2px solid #16a34a; "
            "border-radius:8px; background:#f0fdf4; color:#15803d;"
        )
        self.hash_display.setText("✅ Hash loaded from secure vault database.\nClick Verify Integrity to check the file.")
        self.hash_display.setStyleSheet("background:#14532d; color:#86efac; padding:15px; border-radius:12px;")

    def run_integrity_check(self):
        path = self.hash_input.text().strip()
        expected = self.expected_hash.text().strip().lower()
        if not expected:
            self.hash_display.setText("⚠️ No hash available — browse a file first.")
            self.hash_display.setStyleSheet("background:#78350f; color:#fbbf24; padding:15px; border-radius:12px; font-weight:bold;")
            return
        if not os.path.exists(path):
            self.hash_display.setText("⚠️ Select a valid file first.")
            self.hash_display.setStyleSheet("background:#1e293b; color:#fbbf24; padding:15px; border-radius:12px;")
            return
        try:
            sha = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha.update(chunk)
            computed = sha.hexdigest().lower()
            file_name = os.path.basename(path)
            if computed == expected:
                self.hash_display.setText(f"✅ INTEGRITY MATCHED!\n\nFile: {file_name}\nHash: {computed[:32]}...")
                self.hash_display.setStyleSheet("background:#14532d; color:#4ade80; padding:15px; border-radius:12px; font-weight:bold;")
                self.log_activity(f"Integrity PASSED: {file_name}")
                write_audit_log(
                    username=self.user_name, role="Receiver",
                    action="INTEGRITY_PASSED", method="Manual Check",
                    file_name=file_name,
                    details=f"Hash: {computed[:20]}..."
                )
                # ── integrity_audit table ─────────────────────────
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur  = conn.cursor()
                    cur.execute(
                        "INSERT INTO integrity_audit "
                        "(sender_hash, receiver_hash, integrity_status) "
                        "VALUES (?, ?, ?)",
                        (encrypt_field(expected), encrypt_field(computed), "MATCH")
                    )
                    conn.commit(); conn.close()
                except Exception as e:
                    print(f"[integrity_audit] {e}")
            else:
                self.hash_display.setText(f"❌ HASH MISMATCH — File may be tampered!\n\nExpected: {expected[:32]}...\nComputed: {computed[:32]}...")
                self.hash_display.setStyleSheet("background:#7f1d1d; color:#f87171; padding:15px; border-radius:12px; font-weight:bold;")
                self.log_activity(f"Integrity FAILED: {file_name}")
                write_audit_log(
                    username=self.user_name, role="Receiver",
                    action="INTEGRITY_FAILED", method="Manual Check",
                    file_name=file_name,
                    details=f"Expected: {expected[:20]} | Got: {computed[:20]}"
                )
                # ── integrity_audit table ─────────────────────────
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur  = conn.cursor()
                    cur.execute(
                        "INSERT INTO integrity_audit "
                        "(sender_hash, receiver_hash, integrity_status) "
                        "VALUES (?, ?, ?)",
                        (encrypt_field(expected), encrypt_field(computed), "MISMATCH")
                    )
                    conn.commit(); conn.close()
                except Exception as e:
                    print(f"[integrity_audit] {e}")
                # ── anomaly_alerts table ──────────────────────────
                write_anomaly_alert(
                    "INTEGRITY_MISMATCH",
                    f"File tampered: {file_name} | "
                    f"Expected: {expected[:20]} | Got: {computed[:20]}",
                    "CRITICAL"
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Hash calculation failed: {e}")

    @QtCore.pyqtSlot()
    def refresh_vault_table(self):
        self.tab_vault.setSortingEnabled(False)
        self.tab_vault.setRowCount(0)
        self.tab_vault.setColumnCount(5)
        self.tab_vault.setHorizontalHeaderLabels(["Filename", "Size (KB)", "Status", "Received Via", "Action"])
        method_map = {}
        history_items = []
        downloaded_set = set()
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    for item in json.load(f):
                        fname = item.get('file', '')
                        proto = item.get('protocol', 'Direct')
                        if "Download" in proto:
                            downloaded_set.add(fname)
                            downloaded_set.add(fname.replace("DECRYPTED_", ""))
                            if "(" in proto:
                                proto = proto.split("(")[1].replace(")", "")
                        method_map[fname] = proto
                        method_map[fname.replace(".aes", "")] = proto
                        method_map["DECRYPTED_" + fname] = proto
                        method_map["DECRYPTED_" + fname.replace(".aes", "")] = proto
                        history_items.append((fname, proto))
            except:
                pass

        def get_method(filename):
            if filename in method_map:
                return method_map[filename]
            base = filename.replace("DECRYPTED_", "").replace(".aes", "")
            for hname, hproto in history_items:
                hbase = hname.replace("DECRYPTED_", "").replace(".aes", "")
                if base and hbase and (base in hbase or hbase in base):
                    return hproto
            return "Email Fetch" if "email" in filename.lower() else "Direct"

        if not os.path.exists(self.RECEIVED_DIR):
            return
        for filename in os.listdir(self.RECEIVED_DIR):
            row = self.tab_vault.rowCount()
            self.tab_vault.insertRow(row)
            size = os.path.getsize(os.path.join(self.RECEIVED_DIR, filename)) // 1024
            self.tab_vault.setItem(row, 0, QtWidgets.QTableWidgetItem(filename))
            self.tab_vault.setItem(row, 1, QtWidgets.QTableWidgetItem(str(size)))
            is_encrypted = filename.endswith(".aes")
            st_text = "🔒 Encrypted" if is_encrypted else "✅ Decrypted"
            st_item = QtWidgets.QTableWidgetItem(st_text)
            st_item.setTextAlignment(QtCore.Qt.AlignCenter)
            font_st = QtGui.QFont("Segoe UI", 10)
            font_st.setBold(True)
            st_item.setFont(font_st)
            if is_encrypted:
                st_item.setForeground(QtGui.QColor("#0284c7"))
            else:
                st_item.setForeground(QtGui.QColor("#16a34a"))
            self.tab_vault.setItem(row, 2, st_item)
            self.tab_vault.setItem(row, 3, QtWidgets.QTableWidgetItem(get_method(filename)))
            is_done = filename in downloaded_set
            btn = QtWidgets.QPushButton("📥 Downloaded" if is_done else "📥 Download")
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            if is_done:
                btn.setStyleSheet(
                    "QPushButton { background:#16a34a; color:white; font-weight:bold; "
                    "border-radius:4px; padding:4px 10px; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background:#0284c7; color:white; font-weight:bold; "
                    "border-radius:4px; padding:4px 10px; } "
                    "QPushButton:hover { background:#0369a1; }"
                )
                btn.clicked.connect(lambda ch, fn=filename: self.download_file(fn))
            self.tab_vault.setCellWidget(row, 4, btn)

    def clear_vault_files(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Clear All Files",
            "Are you sure you want to delete ALL files from the vault?\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for f in os.listdir(self.RECEIVED_DIR):
                    os.remove(os.path.join(self.RECEIVED_DIR, f))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Could not clear files: {e}")
                return
            self.tab_vault.setRowCount(0)

    def filter_vault(self, text):
        for row in range(self.tab_vault.rowCount()):
            match = False
            for col in range(self.tab_vault.columnCount() - 1):
                item = self.tab_vault.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.tab_vault.setRowHidden(row, not match)

    def download_file(self, filename):
        if filename.endswith(".aes"):
            QtWidgets.QMessageBox.warning(self, "Forensic Alert", "⚠️ Decrypt the file first before downloading!")
            return
        src = os.path.join(self.RECEIVED_DIR, filename)
        dst, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Forensic File", filename)
        if dst:
            try:
                shutil.copy2(src, dst)
                QtWidgets.QMessageBox.information(self, "Download Complete", f"File saved to:\n{dst}")
                self.add_to_receive_history(filename, "Download", "Success")
                self.refresh_vault_table()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Download failed: {e}")

    def add_to_receive_history(self, file, protocol, status="Success"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not file or file == "N/A":
            status = "Failed"
        elif any(k in file.lower() for k in ["virus", "malware", "hack", "exploit", "shell", "attack"]):
            status = "Suspicious"
        record = {"time": ts, "file": file, "protocol": protocol, "status": status}
        data = []
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    data = json.load(f)
            except:
                data = []
        data.append(record)
        with open(self.HISTORY_STORAGE, 'w') as f:
            json.dump(data, f, indent=4)
        write_audit_log(
            username=self.user_name, role="Receiver",
            action=f"FILE_{status.upper()}", method=protocol,
            file_name=file, details=f"Status: {status}"
        )
        self.sig_notification.emit(f"File {file} — {status}", status)

    def clear_history(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all receive history?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                with open(self.HISTORY_STORAGE, 'w') as f:
                    json.dump([], f)
            except Exception:
                pass
            self.tab_hist.setRowCount(0)

    def filter_history(self, text):
        for row in range(self.tab_hist.rowCount()):
            match = False
            for col in range(self.tab_hist.columnCount()):
                item = self.tab_hist.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.tab_hist.setRowHidden(row, not match)

    def _make_status_item(self, st):
        si = QtWidgets.QTableWidgetItem(st)
        si.setTextAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont("Segoe UI", 10)
        font.setBold(True)
        si.setFont(font)
        if st == "Success":
            si.setForeground(QtGui.QColor("#16a34a"))
        elif st == "Failed":
            si.setForeground(QtGui.QColor("#ef4444"))
        elif st == "Suspicious":
            si.setForeground(QtGui.QColor("#7f1d1d"))
        return si

    @QtCore.pyqtSlot()
    def load_history_data(self):
        self.tab_hist.setSortingEnabled(False)
        self.tab_hist.setRowCount(0)
        if not os.path.exists(self.HISTORY_STORAGE):
            return
        try:
            with open(self.HISTORY_STORAGE, 'r') as f:
                for item in json.load(f):
                    row = self.tab_hist.rowCount()
                    self.tab_hist.insertRow(row)
                    self.tab_hist.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get('time', 'N/A')))
                    self.tab_hist.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get('file', 'N/A')))
                    self.tab_hist.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get('protocol', 'N/A')))
                    self.tab_hist.setItem(row, 3, self._make_status_item(item.get('status', 'Success')))
        except Exception as e:
            print(f"History load error: {e}")

    @QtCore.pyqtSlot()
    def update_dashboard_stats(self):
        received = 0
        total_kb = 0.0
        decrypted = 0
        passed = 0
        failed = 0
        if os.path.exists(self.HISTORY_STORAGE):
            try:
                with open(self.HISTORY_STORAGE, 'r') as f:
                    data = json.load(f)
                received = len(data)
                failed = sum(1 for i in data if i.get("status") == "Failed")
            except:
                pass
        if os.path.exists(self.RECEIVED_DIR):
            try:
                all_files = os.listdir(self.RECEIVED_DIR)
                for fn in all_files:
                    fp = os.path.join(self.RECEIVED_DIR, fn)
                    total_kb += os.path.getsize(fp) / 1024
                decrypted = sum(1 for fn in all_files if fn.startswith("DECRYPTED_"))
            except:
                pass
        AUDIT = "audit_log.json"
        if os.path.exists(AUDIT):
            try:
                with open(AUDIT, 'r') as f:
                    alog = json.load(f)
                passed = sum(1 for e in alog if "INTEGRITY" in e.get("action", "").upper() and e.get("status", "") == "Success")
            except:
                pass
        total_mb = round(total_kb / 1024, 2) if total_kb >= 1024 else round(total_kb / 1024, 2)
        mb_str = f"{total_mb:.1f}" if total_mb > 0 else "0"
        self.lbl_stat_rcvd.setText(str(received))
        self.lbl_stat_size.setText(mb_str)
        self.lbl_stat_dec.setText(str(decrypted))
        self.lbl_stat_int.setText(str(passed))
        self.lbl_stat_failed.setText(str(failed))
        self.load_activity_logs()

    def log_activity(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.activity_list.addItem(f"● [{ts}] {message}")
        self.activity_list.scrollToBottom()

    def load_activity_logs(self):
        self.activity_list.clear()
        if not os.path.exists(self.HISTORY_STORAGE):
            return
        try:
            with open(self.HISTORY_STORAGE, 'r') as f:
                data = json.load(f)
            for item in reversed(data[-30:]):
                ts = item.get('time', '')
                fn = item.get('file', '')
                meth = item.get('protocol', '')
                st = item.get('status', '')
                entry = f"● [{ts}]  {fn}"
                if meth:
                    entry += f"  —  {meth}"
                list_item = QtWidgets.QListWidgetItem(entry)
                list_item.setForeground(QtGui.QColor("#0f172a"))
                self.activity_list.addItem(list_item)
            self.activity_list.scrollToBottom()
        except Exception as e:
            print(f"Activity load error: {e}")

    @QtCore.pyqtSlot(str, str)
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

    def add_notification(self, message, status="Success"):
        self.sig_notification.emit(message, status)

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

    def open_case_report_dialog(self, decrypted_file=None):
        import hashlib
        auto_file = decrypted_file
        if not auto_file and os.path.exists(self.RECEIVED_DIR):
            files = [
                os.path.join(self.RECEIVED_DIR, f)
                for f in os.listdir(self.RECEIVED_DIR)
                if not f.endswith(".aes")
            ]
            if files:
                auto_file = max(files, key=os.path.getmtime)
        auto_method = "N/A"
        auto_hash = "N/A"
        auto_size = "N/A"
        auto_time = ""
        auto_fname = ""
        if auto_file and os.path.exists(auto_file):
            auto_fname = os.path.basename(auto_file)
            sz = os.path.getsize(auto_file)
            auto_size = f"{sz / 1024:.2f} KB"
            auto_time = datetime.fromtimestamp(os.path.getmtime(auto_file)).strftime("%Y-%m-%d %H:%M:%S")
            sha = hashlib.sha256()
            with open(auto_file, 'rb') as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    sha.update(chunk)
            auto_hash = sha.hexdigest()
            if os.path.exists(self.HISTORY_STORAGE):
                try:
                    import json as _json
                    with open(self.HISTORY_STORAGE, 'r') as fh:
                        hist = _json.load(fh)
                    base = auto_fname.replace("DECRYPTED_", "").replace(".aes", "")
                    for item in reversed(hist):
                        hbase = item.get("file", "").replace("DECRYPTED_", "").replace(".aes", "")
                        if base and hbase and (base in hbase or hbase in base):
                            auto_method = item.get("protocol", "N/A")
                            break
                except Exception:
                    pass
        from datetime import datetime as _dt
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Chain of Custody Report — Secure Forensic Data Sharing Framework")
        dlg.setStyleSheet("background:white; font-family:'Segoe UI',sans-serif;")
        dlg.setMinimumWidth(580)
        dlg.resize(620, 700)
        root = QtWidgets.QVBoxLayout(dlg)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        hdr = QtWidgets.QFrame()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0284c7, stop:1 #0ea5e9);"
        )
        hdr_l = QtWidgets.QHBoxLayout(hdr)
        hdr_l.setContentsMargins(20, 0, 20, 0)
        hdr_icon = QtWidgets.QLabel("📋")
        hdr_icon.setStyleSheet("font-size:22px;")
        hdr_title = QtWidgets.QLabel("CHAIN OF CUSTODY FORM")
        hdr_title.setStyleSheet("font-size:18px; font-weight:bold; color:white; padding-left:8px;")
        date_lbl = QtWidgets.QLabel(f"Date: {_dt.now().strftime('%d/%m/%Y  %H:%M')}")
        date_lbl.setStyleSheet("font-size:12px; color:#e0f2fe;")
        hdr_l.addWidget(hdr_icon)
        hdr_l.addWidget(hdr_title)
        hdr_l.addStretch()
        hdr_l.addWidget(date_lbl)
        root.addWidget(hdr)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: white; }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 10px;
                border-radius: 5px;
                margin: 4px 2px 4px 2px;
            }
            QScrollBar::handle:vertical {
                background: #94a3b8;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #0284c7; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical { background: none; }
        """)
        body_w = QtWidgets.QWidget()
        body_w.setStyleSheet("background:white;")
        body = QtWidgets.QVBoxLayout(body_w)
        body.setContentsMargins(30, 24, 30, 16)
        body.setSpacing(16)
        scroll.setWidget(body_w)
        root.addWidget(scroll, 1)

        def section_hdr(icon, text):
            f = QtWidgets.QFrame()
            f.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #eff6ff, stop:1 #f8fafc); "
                "border-radius:8px; border-left:4px solid #0284c7;"
            )
            fl = QtWidgets.QHBoxLayout(f)
            fl.setContentsMargins(14, 8, 14, 8)
            lbl = QtWidgets.QLabel(f"{icon}  {text}")
            lbl.setStyleSheet("font-size:13px; font-weight:bold; color:#0284c7; background:transparent;")
            fl.addWidget(lbl)
            return f

        def field_row(label, widget):
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(label)
            lbl.setFixedWidth(170)
            lbl.setStyleSheet("font-size:13px; color:#374151; font-weight:bold;")
            row.addWidget(lbl)
            row.addWidget(widget, 1)
            return row

        inp_style = (
            "padding:8px 12px; font-size:13px; border:1px solid #cbd5e1; "
            "border-radius:7px; background:#f8fafc;"
            "selection-background-color:#bae6fd;"
        )
        ro_style = (
            "padding:8px 12px; font-size:13px; border:1px solid #e2e8f0; "
            "border-radius:7px; background:#f1f5f9; color:#374151;"
        )
        body.addWidget(section_hdr("📁", "CASE INFORMATION"))
        case_id = QtWidgets.QLineEdit()
        case_id.setPlaceholderText("e.g., SFDS/CASE/2026/001")
        case_id.setStyleSheet(inp_style)
        case_name = QtWidgets.QLineEdit()
        case_name.setPlaceholderText("e.g., Encrypted Evidence Retrieval")
        case_name.setStyleSheet(inp_style)
        case_type = QtWidgets.QComboBox()
        case_type.addItems(["Cyber Crime", "Digital Forensics", "Encrypted Evidence Transfer", "Other"])
        case_type.setStyleSheet(
            "QComboBox { padding:8px 12px; font-size:13px; border:1px solid #cbd5e1; "
            "border-radius:7px; background:#f8fafc; color:#0f172a; } "
            "QComboBox::drop-down { border:none; } "
            "QComboBox QAbstractItemView { "
            "  background:white; color:#0f172a; "
            "  selection-background-color:#1e40af; "
            "  selection-color:white; "
            "  border:1px solid #cbd5e1; "
            "  outline:none; "
            "  padding:4px; "
            "} "
        )
        body.addLayout(field_row("Case ID  *", case_id))
        body.addLayout(field_row("Case Name:", case_name))
        body.addLayout(field_row("Case Type:", case_type))
        body.addWidget(section_hdr("🔒", "EVIDENCE DETAILS (RECEIVED)"))
        ev_file = QtWidgets.QLineEdit(auto_fname)
        ev_file.setStyleSheet(ro_style)
        ev_file.setReadOnly(True)
        ev_size = QtWidgets.QLineEdit(auto_size)
        ev_size.setStyleSheet(ro_style)
        ev_size.setReadOnly(True)
        ev_via = QtWidgets.QLineEdit(auto_method)
        ev_via.setStyleSheet(
            "padding:8px 12px; font-size:13px; border:1px solid #bae6fd; "
            "border-radius:7px; background:#f0f9ff; color:#0284c7; font-weight:bold;"
        )
        ev_via.setReadOnly(True)
        ev_hash = QtWidgets.QLineEdit(auto_hash)
        ev_hash.setStyleSheet(ro_style)
        ev_hash.setReadOnly(True)
        ev_time = QtWidgets.QLineEdit(auto_time)
        ev_time.setStyleSheet(ro_style)
        ev_time.setReadOnly(True)
        body.addLayout(field_row("File Name:", ev_file))
        body.addLayout(field_row("File Size:", ev_size))
        body.addLayout(field_row("Received Via:", ev_via))
        body.addLayout(field_row("SHA-256 Hash:", ev_hash))
        body.addLayout(field_row("Received Date/Time:", ev_time))
        body.addWidget(section_hdr("👤", "RECEIVER DETAILS"))
        rx_name = QtWidgets.QLineEdit(self.user_name)
        rx_name.setStyleSheet(ro_style)
        rx_name.setReadOnly(True)
        rx_org = QtWidgets.QLineEdit()
        rx_org.setPlaceholderText("Department / Agency / Institution Name")
        rx_org.setStyleSheet(inp_style)
        body.addLayout(field_row("Receiver Name *", rx_name))
        body.addLayout(field_row("Organization:", rx_org))
        body.addWidget(section_hdr("📝", "INVESTIGATOR REMARKS"))
        remarks = QtWidgets.QTextEdit()
        remarks.setPlaceholderText("Any observations about the received evidence, decryption status, or chain of custody notes...")
        remarks.setFixedHeight(90)
        remarks.setStyleSheet(inp_style)
        body.addWidget(remarks)
        body.addWidget(section_hdr("✅", "CERTIFICATION"))
        certify_cb = QtWidgets.QCheckBox("I hereby certify that the above information is true, accurate and complete.")
        certify_cb.setStyleSheet("font-size:13px; color:#374151; padding:6px 4px;")
        body.addWidget(certify_cb)
        body.addStretch()
        foot = QtWidgets.QFrame()
        foot.setStyleSheet("background:#f8fafc; border-top:2px solid #e2e8f0;")
        foot.setFixedHeight(65)
        foot_l = QtWidgets.QHBoxLayout(foot)
        foot_l.setContentsMargins(24, 12, 24, 12)
        foot_l.addStretch()
        btn_save = QtWidgets.QPushButton("💾   SAVE  &  GENERATE PDF REPORT")
        btn_save.setFixedHeight(42)
        btn_save.setMinimumWidth(260)
        btn_save.setCursor(QtCore.Qt.PointingHandCursor)
        btn_save.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0284c7, stop:1 #0ea5e9); color:white; font-weight:bold; "
            "font-size:14px; border-radius:9px; } "
            "QPushButton:hover { background:#0369a1; }"
        )
        btn_cancel = QtWidgets.QPushButton("✕   CANCEL")
        btn_cancel.setFixedHeight(42)
        btn_cancel.setMinimumWidth(110)
        btn_cancel.setCursor(QtCore.Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background:white; color:#ef4444; font-weight:bold; "
            "font-size:13px; border:2px solid #ef4444; border-radius:9px; } "
            "QPushButton:hover { background:#fef2f2; }"
        )
        btn_cancel.clicked.connect(dlg.close)
        foot_l.addWidget(btn_save)
        foot_l.addSpacing(14)
        foot_l.addWidget(btn_cancel)
        root.addWidget(foot)

        def save_report():
            if not case_id.text().strip():
                QtWidgets.QMessageBox.warning(dlg, "Missing Field", "⚠️ Please enter Case ID.")
                return
            if not certify_cb.isChecked():
                QtWidgets.QMessageBox.warning(dlg, "Certification Required", "⚠️ Please check the certification box before saving.")
                return
            dest, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg,
                "Save Chain of Custody Report (PDF)",
                f"ChainOfCustody_{case_id.text().replace('/','_')}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "PDF Files (*.pdf);;All Files (*)"
            )
            if not dest:
                return
            try:
                if not _REPORTLAB_OK:
                    QtWidgets.QMessageBox.critical(dlg, "Missing Library", "reportlab library not found.\n\nPlease install it:\n  pip install reportlab")
                    return
                A4 = _RL_A4
                colors = _RL_colors
                getSampleStyleSheet = _RL_styles
                ParagraphStyle = _RL_PS
                cm = _RL_cm
                SimpleDocTemplate = _RL_Doc
                Paragraph = _RL_Para
                Spacer = _RL_Spacer
                Table = _RL_Table
                TableStyle = _RL_TableStyle
                HRFlowable = _RL_HR
                TA_CENTER = _RL_CENTER
                TA_LEFT = _RL_LEFT
                doc = SimpleDocTemplate(dest, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
                BLUE = colors.HexColor("#0284c7")
                LBLUE = colors.HexColor("#eff6ff")
                DGRAY = colors.HexColor("#1e293b")
                MGRAY = colors.HexColor("#374151")
                LGRAY = colors.HexColor("#f1f5f9")
                BORDER = colors.HexColor("#e2e8f0")
                GREEN = colors.HexColor("#16a34a")
                WHITE = colors.white
                styles = getSampleStyleSheet()

                def hdr_para(txt):
                    return Paragraph(f'<font color="#0284c7"><b>{txt}</b></font>', ParagraphStyle("sh", fontSize=11, spaceAfter=4, leading=16))

                def kv_table(pairs):
                    data = []
                    for k, v in pairs:
                        data.append([Paragraph(f'<b><font color="#374151">{k}</font></b>', ParagraphStyle("k", fontSize=10, leading=14)), Paragraph(f'<font color="#1e293b">{v}</font>', ParagraphStyle("v", fontSize=10, leading=14))])
                    t = Table(data, colWidths=[5*cm, 11*cm])
                    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), LGRAY), ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]), ("GRID", (0,0), (-1,-1), 0.4, BORDER), ("VALIGN", (0,0), (-1,-1), "TOP"), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7), ("LEFTPADDING", (0,0), (-1,-1), 10)]))
                    return t

                story = []
                title_data = [[Paragraph('<font color="white"><b>SECURE FORENSIC DATA SHARING FRAMEWORK</b></font>', ParagraphStyle("t1", fontSize=14, alignment=TA_CENTER, leading=20))], [Paragraph('<font color="#bae6fd">Chain of Custody Report</font>', ParagraphStyle("t2", fontSize=11, alignment=TA_CENTER, leading=16))], [Paragraph(f'<font color="#e0f2fe">Generated: {_dt.now().strftime("%d %B %Y  —  %H:%M:%S")}</font>', ParagraphStyle("t3", fontSize=9, alignment=TA_CENTER))]]
                title_t = Table(title_data, colWidths=[16*cm])
                title_t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), BLUE), ("TOPPADDING", (0,0), (-1,-1), 10), ("BOTTOMPADDING", (0,0), (-1,-1), 8), ("LEFTPADDING", (0,0), (-1,-1), 16), ("ROUNDEDCORNERS", [6,6,6,6])]))
                story.append(title_t)
                story.append(Spacer(1, 0.5*cm))
                story.append(hdr_para("📁  CASE INFORMATION"))
                story.append(kv_table([("Case ID", case_id.text().strip()), ("Case Name", case_name.text().strip() or "N/A"), ("Case Type", case_type.currentText())]))
                story.append(Spacer(1, 0.4*cm))
                story.append(hdr_para("🔒  EVIDENCE DETAILS (RECEIVED)"))
                story.append(kv_table([("File Name", auto_fname or "N/A"), ("File Size", auto_size or "N/A"), ("Received Via", auto_method or "N/A"), ("SHA-256 Hash", auto_hash or "N/A"), ("Received Date/Time", auto_time or "N/A")]))
                story.append(Spacer(1, 0.4*cm))
                story.append(hdr_para("👤  RECEIVER DETAILS"))
                story.append(kv_table([("Receiver Name", self.user_name), ("Organization", rx_org.text().strip() or "N/A")]))
                story.append(Spacer(1, 0.4*cm))
                story.append(hdr_para("📝  INVESTIGATOR REMARKS"))
                rem_txt = remarks.toPlainText().strip() or "No remarks provided."
                rem_box = Table([[Paragraph(f'<font color="#374151">{rem_txt}</font>', ParagraphStyle("rem", fontSize=10, leading=15))]], colWidths=[16*cm])
                rem_box.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), WHITE), ("GRID", (0,0), (-1,-1), 0.4, BORDER), ("TOPPADDING", (0,0), (-1,-1), 10), ("BOTTOMPADDING", (0,0), (-1,-1), 10), ("LEFTPADDING", (0,0), (-1,-1), 12)]))
                story.append(rem_box)
                story.append(Spacer(1, 0.4*cm))
                story.append(hdr_para("✅  CERTIFICATION"))
                cert_data = [[Paragraph(f'<font color="#16a34a"><b>CERTIFIED</b></font>  <font color="#374151">I hereby certify that the above information is true, accurate and complete.</font>', ParagraphStyle("cert", fontSize=10, leading=15))], [Paragraph(f'<font color="#374151"><b>Certified by:</b>  {self.user_name}</font>', ParagraphStyle("certby", fontSize=10, leading=15))], [Paragraph(f'<font color="#374151"><b>Date & Time:</b>  {_dt.now().strftime("%Y-%m-%d  %H:%M:%S")}</font>', ParagraphStyle("certdt", fontSize=10, leading=15))]]
                cert_t = Table(cert_data, colWidths=[16*cm])
                cert_t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f0fdf4")), ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#bbf7d0")), ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8), ("LEFTPADDING", (0,0), (-1,-1), 12)]))
                story.append(cert_t)
                story.append(Spacer(1, 0.6*cm))
                story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
                story.append(Spacer(1, 0.2*cm))
                story.append(Paragraph(f'<font color="#94a3b8" size="8">Secure Forensic Data Sharing Framework  —  Report ID: SFDS-{_dt.now().strftime("%Y%m%d%H%M%S")}  —  Receiver: {self.user_name}</font>', ParagraphStyle("foot", fontSize=8, alignment=TA_CENTER)))
                doc.build(story)
                write_audit_log(username=self.user_name, role="Receiver", action="CASE_REPORT_GENERATED", method="PDF", file_name=os.path.basename(dest), details=f"Case ID: {case_id.text().strip()}")
                QtWidgets.QMessageBox.information(dlg, "PDF Report Saved ✅", f"Chain of Custody PDF saved successfully!\n\n{dest}")
                dlg.accept()
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Save Failed", f"Error generating PDF:\n{e}")
        btn_save.clicked.connect(save_report)
        dlg.exec_()

    def do_logout(self):
        self.monitor_timer.stop()
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
            self.landing = MainAppWindow()
            self.landing.showMaximized()
        except Exception as e:
            print(f"Logout error: {e}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
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