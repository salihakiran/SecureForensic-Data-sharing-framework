from PyQt5 import QtWidgets, QtCore, QtGui
import sys
import os
import sqlite3
import json
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from app import write_audit_log, push_notification, poll_notifications, DB_PATH


# ═══════════════════════════════════════════════════════════════
# NOTIF BELL — clean animated bell widget with red badge
# ═══════════════════════════════════════════════════════════════
class NotifBell(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.counter = 0
        self.setFixedSize(50, 50)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAttribute(QtCore.Qt.WA_Hover)

        self._bell = QtWidgets.QLabel("🔔", self)
        self._bell.setFixedSize(50, 50)
        self._bell.setAlignment(QtCore.Qt.AlignCenter)
        self._bell.setStyleSheet("font-size:26px; background:transparent;")

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
            "font-size:26px; background:rgba(255,255,255,0.15); border-radius:25px;"
        )

    def leaveEvent(self, e):
        self._bell.setStyleSheet("font-size:26px; background:transparent;")


# ═══════════════════════════════════════════════════════════════
# NOTIF PANEL — drop-down notification panel
# ═══════════════════════════════════════════════════════════════
class NotifPanel(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setFixedWidth(380)
        self.setStyleSheet(
            "NotifPanel { background:white; border-radius:14px; border:1px solid #e2e8f0; }"
        )
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QtWidgets.QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0078d7, stop:1 #0ea5e9); "
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

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFixedHeight(320)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { border:none; background:white; }
            QScrollBar:vertical { background:#f1f5f9; width:7px; border-radius:3px; margin:2px; }
            QScrollBar::handle:vertical { background:#cbd5e1; border-radius:3px; min-height:24px; }
            QScrollBar::handle:vertical:hover { background:#0078d7; }
        """)
        self.items_w = QtWidgets.QWidget()
        self.items_w.setStyleSheet("background:white;")
        self.items_l = QtWidgets.QVBoxLayout(self.items_w)
        self.items_l.setContentsMargins(10, 8, 10, 8)
        self.items_l.setSpacing(6)
        self.scroll.setWidget(self.items_w)
        root.addWidget(self.scroll)

        foot = QtWidgets.QFrame()
        foot.setFixedHeight(36)
        foot.setStyleSheet(
            "QFrame { background:#f8fafc; border-top:1px solid #e2e8f0; "
            "border-bottom-left-radius:14px; border-bottom-right-radius:14px; }"
        )
        fl = QtWidgets.QHBoxLayout(foot)
        fl.setContentsMargins(14, 0, 14, 0)
        self.foot_lbl = QtWidgets.QLabel("No notifications yet")
        self.foot_lbl.setStyleSheet("color:#94a3b8; font-size:11px; background:transparent;")
        fl.addWidget(self.foot_lbl)
        fl.addStretch()
        root.addWidget(foot)

    def populate(self, notifs):
        n = len(notifs)
        self.count_lbl.setText(str(n))
        self.count_lbl.setVisible(n > 0)
        self.foot_lbl.setText(
            f"{n} notification{'s' if n != 1 else ''}" if n else "No notifications yet"
        )
        while self.items_l.count():
            c = self.items_l.takeAt(0)
            if c.widget():
                c.widget().deleteLater()

        if not notifs:
            empty = QtWidgets.QLabel("🔕   No notifications yet")
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setStyleSheet("color:#94a3b8; font-size:13px; padding:40px 20px; background:transparent;")
            self.items_l.addWidget(empty)
            return

        STATUS_CFG = {
            "Success": ("#dcfce7", "#16a34a", "✅"),
            "Alert":   ("#fee2e2", "#dc2626", "🚨"),
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
            row.setFixedHeight(62)
            rl = QtWidgets.QHBoxLayout(row)
            rl.setContentsMargins(10, 8, 10, 8)
            rl.setSpacing(10)

            ic = QtWidgets.QLabel(icon)
            ic.setFixedSize(32, 32)
            ic.setAlignment(QtCore.Qt.AlignCenter)
            ic.setStyleSheet(f"background:{bg}; border-radius:16px; font-size:15px; border:none;")
            rl.addWidget(ic)

            tw = QtWidgets.QWidget()
            tw.setStyleSheet("background:transparent; border:none;")
            tl = QtWidgets.QVBoxLayout(tw)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)

            msg_txt = item.get("text", item.get("msg", "")).lstrip("✅❌⚠️🚨ℹ️ ")
            ml = QtWidgets.QLabel(msg_txt)
            ml.setWordWrap(True)
            ml.setStyleSheet("font-size:12px; font-weight:bold; color:#1e293b; background:transparent; border:none;")
            tl.addWidget(ml)

            tl2 = QtWidgets.QLabel("🕐 " + item.get("time", ""))
            tl2.setStyleSheet("font-size:10px; color:#94a3b8; background:transparent; border:none;")
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
# ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════
class AdminDashboard(QtWidgets.QMainWindow):
    def __init__(self, name="Master Admin", role="Admin"):
        super().__init__()
        self.user_name     = name
        self.user_role     = role
        self.is_super      = (role == "SuperAdmin")
        self.notif_count   = 0
        self.last_notif_id = 0
        self.NOTIF_STORAGE = "admin_notifications.json"
        self.BLOCKED_STORAGE = "blocked_threats.json"

        self.setWindowTitle(
            f"Secure Forensic — {'SuperAdmin' if self.is_super else 'Admin'} Panel"
        )
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QFrame#Sidebar { background-color: #0078d7; min-width:260px; max-width:260px; }
            QPushButton#NavBtn {
                text-align:left; padding-left:15px; border:none; border-radius:6px;
                font-size:13px; color:white; background:transparent;
                margin:2px 10px; height:42px;
            }
            QPushButton#NavBtn:hover   { background:#005a9e; }
            QPushButton#NavBtn:checked { background:#003f7f; font-weight:bold; }
            QTableWidget {
                background:white; border:1px solid #dee2e6; border-radius:8px;
            }
            QHeaderView::section {
                background:#0078d7; color:white; padding:10px;
                font-weight:bold; font-size:12px;
            }
            QGroupBox {
                background:white; border-radius:12px; border:1px solid #e2e8f0;
                font-size:15px; font-weight:bold; margin-top:16px; padding:20px;
            }
            QGroupBox::title { subcontrol-origin:margin; left:20px; color:#0078d7; }
        """)

        self.initUI()
        self._poll_timer = QtCore.QTimer()
        self._poll_timer.timeout.connect(self._poll_shared_notifications)
        self._poll_timer.start(5000)
        self.show_dashboard_overview()

        # Maximize only after the window has real content — calling this
        # too early (before initUI builds the central widget) makes Qt
        # compute the wrong "normal" geometry on some systems, so the
        # window visually opens small even though its state is "maximized".
        # singleShot(0, ...) defers it until the event loop is ready.
        QtCore.QTimer.singleShot(0, self.showMaximized)

    # ═══════════════════════════════════════════════════════════
    # DB HELPERS
    # ═══════════════════════════════════════════════════════════
    def _db(self, sql, params=()):
        if not os.path.exists(DB_PATH): return []
        try:
            conn = sqlite3.connect(DB_PATH)
            cur  = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f"[Admin DB] {e}")
            return []

    def _db_write(self, sql, params=()):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur  = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "DB Error", str(e))
            return False

    def fetch_audit_logs(self, condition="1=1", params=()):
        return self._db(
            f"SELECT username,role,action,method,file_name,details,timestamp "
            f"FROM audit_logs WHERE {condition} ORDER BY id DESC",
            params
        )

    def fetch_users(self, status_filter="all"):
        role_clause = (
            "role NOT IN ('SuperAdmin')" if self.is_super
            else "role IN ('Sender','Receiver')"
        )
        s = {
            "pending": "is_approved=0 AND is_revoked=0",
            "active":  "is_approved=1 AND is_revoked=0",
            "revoked": "is_revoked=1",
        }.get(status_filter, "1=1")
        return self._db(
            f"SELECT id,name,email,role,is_approved,is_revoked,created_at "
            f"FROM users WHERE ({s}) AND ({role_clause}) ORDER BY created_at DESC"
        )

    def _set_user(self, uid, field, val, action, username, role):
        ok = self._db_write(f"UPDATE users SET {field}=? WHERE id=?", (val, uid))
        if ok:
            write_audit_log(self.user_name, self.user_role, action,
                            "Admin Panel", details=f"{username} ({role})")
        return ok

    def approve_user(self, uid, name, role):
        if self._set_user(uid, "is_approved", 1, "USER_APPROVED", name, role):
            push_notification("Your account has been approved. You can now log in.",
                              role, "Success", target_user=name)
            self.add_notification(f"Approved: {name} ({role})", "Success")
            QtWidgets.QMessageBox.information(self, "Approved", f"'{name}' can now log in.")
            self.show_user_management()

    def revoke_user(self, uid, name, role):
        if QtWidgets.QMessageBox.question(
            self, "Confirm Revoke", f"Revoke '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            if self._set_user(uid, "is_revoked", 1, "USER_REVOKED", name, role):
                self.add_notification(f"Revoked: {name} ({role})", "Alert")
                QtWidgets.QMessageBox.information(self, "Revoked", f"'{name}' is revoked.")
                self.show_user_management()

    def reinstate_user(self, uid, name, role):
        if self._set_user(uid, "is_revoked", 0, "USER_REINSTATED", name, role):
            self._db_write("UPDATE users SET is_approved=1 WHERE id=?", (uid,))
            push_notification("Your account has been reinstated.",
                              role, "Success", target_user=name)
            self.add_notification(f"Reinstated: {name} ({role})", "Success")
            QtWidgets.QMessageBox.information(self, "Reinstated", f"'{name}' reinstated.")
            self.show_user_management()

    def delete_user(self, uid, name, role):
        if QtWidgets.QMessageBox.question(
            self, "Confirm Delete", f"Permanently delete '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) == QtWidgets.QMessageBox.Yes:
            if self._db_write("DELETE FROM users WHERE id=?", (uid,)):
                write_audit_log(self.user_name, self.user_role, "USER_DELETED",
                                "Admin Panel", details=f"{name} ({role})")
                self.add_notification(f"Deleted: {name} ({role})", "Alert")
                QtWidgets.QMessageBox.information(self, "Deleted", f"'{name}' deleted.")
                self.show_user_management()

    # ═══════════════════════════════════════════════════════════
    # UI INIT
    # ═══════════════════════════════════════════════════════════
    def initUI(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── TOP RIBBON ────────────────────────────────────────────
        ribbon = QtWidgets.QFrame()
        ribbon.setFixedHeight(68)
        ribbon.setStyleSheet("background:#0078d7; border-bottom:3px solid #005a9e;")
        rl = QtWidgets.QHBoxLayout(ribbon)
        rl.setContentsMargins(20, 0, 20, 0)

        title_lbl = QtWidgets.QLabel(
            f"SECURE FORENSIC  |  {'SUPERADMIN' if self.is_super else 'ADMIN'} PANEL"
        )
        title_lbl.setStyleSheet("font-size:19px; font-weight:bold; color:white;")
        rl.addWidget(title_lbl)
        rl.addStretch()

        self.notif_btn = NotifBell(self)
        self.notif_panel = NotifPanel(self)
        self.notif_panel.clear_btn.clicked.connect(self._clear_all_notifications)
        self.notif_btn.clicked.connect(self._toggle_notif_panel)
        rl.addWidget(self.notif_btn)
        rl.addSpacing(12)

        user_lbl = QtWidgets.QLabel(
            f"  {self.user_name}  ({'SuperAdmin' if self.is_super else 'Admin'})  "
        )
        user_lbl.setStyleSheet(
            "font-size:13px; font-weight:bold; color:white; "
            "background:#003f7f; padding:8px 12px; border-radius:8px;"
        )
        rl.addWidget(user_lbl)
        outer.addWidget(ribbon)

        # ── BODY ──────────────────────────────────────────────────
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        # ── SIDEBAR ───────────────────────────────────────────────
        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName("Sidebar")
        sl = QtWidgets.QVBoxLayout(sidebar)
        sl.setContentsMargins(10, 16, 10, 16)
        sl.setSpacing(4)

        logo = QtWidgets.QLabel("SECURE FORENSIC\nADMIN PANEL")
        logo.setAlignment(QtCore.Qt.AlignCenter)
        logo.setStyleSheet(
            "color:white; font-size:14px; font-weight:bold; padding:12px; "
            "border-bottom:1px solid #005a9e; margin-bottom:8px;"
        )
        sl.addWidget(logo)

        pending_count = len(self.fetch_users("pending"))
        pending_badge = f"  ({pending_count})" if pending_count else ""

        self._nav_btns = []
        nav_items = [
            ("   Dashboard Overview",              self.show_dashboard_overview),
            ("   Chain of Custody",                self.show_chain_of_custody),
            ("   Evidence Vault",                  self.show_evidence_vault),
            ("   Integrity Audit",                 self.show_integrity_audit),
            ("   Security Alerts",                 self.show_alerts),
            (f"   User Management{pending_badge}", self.show_user_management),
            ("   Settings",                        self.show_settings),
            ("   System Monitoring",               self.show_system_monitoring),
        ]

        for text, func in nav_items:
            btn = QtWidgets.QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setCheckable(True)
            btn.clicked.connect(func)
            sl.addWidget(btn)
            self._nav_btns.append(btn)

        sl.addStretch()

        id_lbl = QtWidgets.QLabel(
            f"{self.user_name}\n{'SuperAdmin' if self.is_super else 'Admin'}"
        )
        id_lbl.setAlignment(QtCore.Qt.AlignCenter)
        id_lbl.setStyleSheet(
            "color:#bfdbfe; font-size:12px; padding:8px; "
            "border-top:1px solid #005a9e;"
        )
        sl.addWidget(id_lbl)

        logout_btn = QtWidgets.QPushButton("   Logout")
        logout_btn.setObjectName("NavBtn")
        logout_btn.setStyleSheet(
            "background-color:#c0392b !important; color:white; "
            "font-weight:bold; margin-bottom:4px;"
        )
        logout_btn.clicked.connect(self.do_logout)
        sl.addWidget(logout_btn)
        body.addWidget(sidebar)

        # ── SCROLL CONTENT AREA ───────────────────────────────────
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._content_widget = QtWidgets.QWidget()
        self.content_layout  = QtWidgets.QVBoxLayout(self._content_widget)
        self.content_layout.setContentsMargins(28, 24, 28, 24)
        self.content_layout.setSpacing(18)
        scroll.setWidget(self._content_widget)
        body.addWidget(scroll, 1)

    # ── HELPERS ────────────────────────────────────────────────
    def _set_active_nav(self, index):
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == index)

    def _clear_content(self):
        # Clear all widgets from layout
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear nested layouts
                while item.layout().count():
                    subitem = item.layout().takeAt(0)
                    if subitem.widget():
                        subitem.widget().deleteLater()
        # Force garbage collection
        QtCore.QCoreApplication.processEvents()

    def _page_title(self, text, color="#1e293b"):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(f"font-size:22px; font-weight:bold; color:{color};")
        return lbl

    def _make_table(self, headers, data, danger_kw=None):
        if danger_kw is None:
            danger_kw = ["FAIL","MISMATCH","UNAUTHORIZED","DENIED","SUSPICIOUS","BLOCKED"]
        tbl = QtWidgets.QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().hide()
        tbl.setStyleSheet(
            "QTableWidget::item{padding:6px;}"
            "QTableWidget::item:alternate{background:#f8fafc;}"
        )
        for ri, row_data in enumerate(data):
            tbl.insertRow(ri)
            is_danger = bool(danger_kw) and any(
                any(k in str(v).upper() for k in danger_kw)
                for v in row_data
            )
            for ci, value in enumerate(row_data):
                item = QtWidgets.QTableWidgetItem(str(value) if value else "—")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if is_danger:
                    item.setForeground(QtGui.QColor("#c0392b"))
                tbl.setItem(ri, ci, item)
        return tbl

    def _stat_card(self, label, value, text_color, bg_color):
        f = QtWidgets.QFrame()
        f.setStyleSheet(
            f"background:{bg_color}; border-radius:12px; border:1px solid #e2e8f0;"
        )
        h = QtWidgets.QHBoxLayout(f)
        h.setContentsMargins(18, 12, 18, 12)
        vl = QtWidgets.QLabel(str(value))
        vl.setStyleSheet(f"font-size:32px; font-weight:bold; color:{text_color};")
        ll = QtWidgets.QLabel(label)
        ll.setStyleSheet(f"font-size:12px; color:{text_color}; font-weight:bold;")
        ll.setWordWrap(True)
        h.addWidget(vl); h.addWidget(ll); h.addStretch()
        return f

    def _cards_row(self, cards):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(14)
        for c in cards: row.addWidget(c)
        w = QtWidgets.QWidget(); w.setLayout(row)
        return w

    # ═══════════════════════════════════════════════════════════
    # PAGE 0 — DASHBOARD OVERVIEW
    # ═══════════════════════════════════════════════════════════
    def show_dashboard_overview(self):
        self._set_active_nav(0)
        self._clear_content()
        
        # Force complete cleanup - no overlapping
        QtCore.QCoreApplication.processEvents()

        self.content_layout.addWidget(self._page_title("Dashboard Overview"))

        # Stat cards
        total_files    = len(self._db("SELECT id FROM audit_logs WHERE action='FILE_ENCRYPTED'"))
        total_tx       = len(self._db("SELECT id FROM vault_transfers"))
        total_users    = len(self._db("SELECT id FROM users WHERE role NOT IN ('SuperAdmin')"))
        alerts_count   = len(self.fetch_audit_logs(
            "action LIKE '%FAIL%' OR action LIKE '%UNAUTHORIZED%' "
            "OR action LIKE '%DENIED%' OR action LIKE '%SUSPICIOUS%'"
        ))
        integrity_pass = len(self.fetch_audit_logs("action='INTEGRITY_PASSED'"))
        pending_count  = len(self.fetch_users("pending"))

        self.content_layout.addWidget(self._cards_row([
            self._stat_card("Files Encrypted",   total_files,    "#0369a1", "#eff6ff"),
            self._stat_card("Total Transfers",   total_tx,       "#065f46", "#f0fdf4"),
            self._stat_card("Registered Users",  total_users,    "#6d28d9", "#f5f3ff"),
            self._stat_card("Pending Approvals", pending_count,  "#92400e", "#fffbeb"),
            self._stat_card("Security Alerts",   alerts_count,   "#991b1b", "#fef2f2"),
            self._stat_card("Integrity Passed",  integrity_pass, "#065f46", "#f0fdf4"),
        ]))

        # Charts
        chart_frame = QtWidgets.QFrame()
        chart_frame.setObjectName("DashboardChartFrame")
        chart_frame.setStyleSheet(
            "background:white; border-radius:12px; border:1px solid #e2e8f0;"
        )
        chart_frame.setMinimumHeight(320)
        chart_frame.setMaximumHeight(360)
        chart_layout_h = QtWidgets.QHBoxLayout(chart_frame)
        chart_layout_h.setContentsMargins(16, 12, 16, 12)

        fig = plt.figure(figsize=(13, 3.2), facecolor='none', dpi=100)

        # Bar — transfers by method
        ax1 = fig.add_subplot(131)
        method_rows = self._db(
            "SELECT method, COUNT(*) FROM vault_transfers "
            "WHERE method IS NOT NULL GROUP BY method ORDER BY COUNT(*) DESC"
        )
        if method_rows:
            methods = [r[0] for r in method_rows]
            counts  = [r[1] for r in method_rows]
            bar_colors = ["#0369a1","#0891b2","#0284c7","#38bdf8","#7dd3fc"]
            ax1.bar(methods, counts, color=bar_colors[:len(methods)],
                    edgecolor='none', width=0.55)
            ax1.set_title("Transfers by Method", fontsize=9, fontweight='bold', pad=5)
            ax1.set_ylabel("Count", fontsize=8)
            ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            ax1.tick_params(axis='x', labelsize=7, rotation=15)
            ax1.tick_params(axis='y', labelsize=7)
            ax1.spines[['top','right']].set_visible(False)
        else:
            ax1.text(0.5, 0.5, "No transfers yet", ha='center', va='center',
                     transform=ax1.transAxes, fontsize=9, color='#64748b')
            ax1.set_title("Transfers by Method", fontsize=9, fontweight='bold')
            ax1.axis('off')

        # Pie — transfer status
        ax2 = fig.add_subplot(132)
        status_rows = self._db(
            "SELECT status, COUNT(*) FROM vault_transfers GROUP BY status"
        )
        if status_rows:
            pie_labels  = [r[0] for r in status_rows]
            pie_sizes   = [r[1] for r in status_rows]
            pie_colors  = {"PENDING":"#fbbf24","FETCHED":"#34d399","DECRYPTED":"#60a5fa"}
            pie_clrs    = [pie_colors.get(l, "#94a3b8") for l in pie_labels]
            wedges, _, autotexts = ax2.pie(
                pie_sizes, labels=pie_labels, colors=pie_clrs,
                autopct='%1.0f%%', startangle=90,
                wedgeprops=dict(edgecolor='white', linewidth=1.5),
                textprops=dict(fontsize=7)
            )
            for at in autotexts: at.set_fontsize(7)
            ax2.set_title("Transfer Status", fontsize=9, fontweight='bold', pad=5)
        else:
            ax2.text(0.5, 0.5, "No transfers yet", ha='center', va='center',
                     transform=ax2.transAxes, fontsize=9, color='#64748b')
            ax2.set_title("Transfer Status", fontsize=9, fontweight='bold')
            ax2.axis('off')

        # Bar — activity last 7 days
        ax3 = fig.add_subplot(133)
        day_rows = self._db(
            "SELECT DATE(timestamp), COUNT(*) FROM audit_logs "
            "WHERE timestamp >= DATE('now','-7 days') "
            "GROUP BY DATE(timestamp) ORDER BY DATE(timestamp)"
        )
        if day_rows:
            days   = [r[0][-5:] for r in day_rows]
            counts = [r[1] for r in day_rows]
            ax3.bar(days, counts, color="#8b5cf6", edgecolor='none', width=0.55)
            ax3.set_title("Activity — Last 7 Days", fontsize=9, fontweight='bold', pad=5)
            ax3.set_ylabel("Events", fontsize=8)
            ax3.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            ax3.tick_params(axis='x', labelsize=7, rotation=20)
            ax3.tick_params(axis='y', labelsize=7)
            ax3.spines[['top','right']].set_visible(False)
        else:
            ax3.text(0.5, 0.5, "No activity yet", ha='center', va='center',
                     transform=ax3.transAxes, fontsize=9, color='#64748b')
            ax3.set_title("Activity — Last 7 Days", fontsize=9, fontweight='bold')
            ax3.axis('off')

        fig.tight_layout(pad=2.0)
        canvas = FigureCanvas(fig)
        canvas.setFixedHeight(280)
        chart_layout_h.addWidget(canvas)
        self.content_layout.addWidget(chart_frame)

        # Recent activity
        recent_lbl = QtWidgets.QLabel("Recent Activity")
        recent_lbl.setStyleSheet("font-size:14px; font-weight:bold; color:#1e293b; margin-top:6px;")
        self.content_layout.addWidget(recent_lbl)

        tbl = self._make_table(
            ["User","Role","Action","Method","File","Details","Timestamp"],
            self.fetch_audit_logs()[:20]
        )
        tbl.setMinimumHeight(240)
        self.content_layout.addWidget(tbl)
        self.content_layout.addStretch()
        
        # Final cleanup
        self.content_layout.update()

    # ═══════════════════════════════════════════════════════════
    # PAGE 1 — CHAIN OF CUSTODY (filterable — replaces 4 old tabs)
    # ═══════════════════════════════════════════════════════════
    def show_chain_of_custody(self):
        self._set_active_nav(1)
        self._clear_content()

        self.content_layout.addWidget(self._page_title("Chain of Custody"))

        # Filter bar
        fb = QtWidgets.QHBoxLayout()
        fb.setSpacing(10)

        def combo(items, w=150):
            c = QtWidgets.QComboBox()
            c.addItems(items)
            c.setFixedWidth(w)
            c.setStyleSheet(
                "padding:6px; font-size:13px; border:1px solid #cbd5e1; "
                "border-radius:6px; background:white;"
            )
            return c

        self._coc_method = combo(
            ["All Methods","Email","LAN","USB","HDD","Google Drive","AES-256"]
        )
        self._coc_action = combo(
            ["All Actions","Encryption","Transfer","Vault Fetch",
             "Decryption","Integrity Check","Login","User Action"]
        )

        for lbl_text, widget in [("Method:", self._coc_method),
                                  ("Action:", self._coc_action)]:
            lbl = QtWidgets.QLabel(lbl_text)
            lbl.setStyleSheet("font-size:13px; color:#475569;")
            fb.addWidget(lbl)
            fb.addWidget(widget)

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setFixedSize(90, 34)
        apply_btn.setStyleSheet(
            "background:#0078d7; color:white; border-radius:6px; "
            "font-size:13px; font-weight:bold;"
        )
        apply_btn.clicked.connect(self._apply_coc_filter)
        fb.addWidget(apply_btn)

        reset_btn = QtWidgets.QPushButton("Reset")
        reset_btn.setFixedSize(80, 34)
        reset_btn.setStyleSheet(
            "background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; "
            "border-radius:6px; font-size:13px;"
        )
        def reset_coc():
            self._coc_method.setCurrentIndex(0)
            self._coc_action.setCurrentIndex(0)
            self._apply_coc_filter()
        reset_btn.clicked.connect(reset_coc)
        fb.addWidget(reset_btn)
        fb.addStretch()

        fw = QtWidgets.QWidget(); fw.setLayout(fb)
        self.content_layout.addWidget(fw)

        self._coc_table = self._make_table(
            ["User","Role","Action","Method","File","Details","Timestamp"],
            self.fetch_audit_logs()
        )
        self._coc_table.setMinimumHeight(500)
        self.content_layout.addWidget(self._coc_table, 1)

    def _coc_filter_sql(self):
        method_map = {
            "Email":        "method LIKE '%Email%' OR method LIKE '%Vault%'",
            "LAN":          "method LIKE '%LAN%'",
            "USB":          "method LIKE '%USB%'",
            "HDD":          "method LIKE '%HDD%'",
            "Google Drive": "method LIKE '%Drive%'",
            "AES-256":      "method LIKE '%AES%'",
        }
        action_map = {
            "Encryption":      "action LIKE '%ENCRYPT%'",
            "Transfer":        "action LIKE '%TRANSFER%'",
            "Vault Fetch":     "action LIKE '%FETCH%' OR action LIKE '%VAULT%'",
            "Decryption":      "action LIKE '%DECRYPT%'",
            "Integrity Check": "action LIKE '%INTEGRITY%' OR action LIKE '%HASH%'",
            "Login":           "action LIKE '%LOGIN%'",
            "User Action":     "action LIKE '%USER%' OR action LIKE '%ACCOUNT%'",
        }
        clauses = []
        m = self._coc_method.currentText()
        a = self._coc_action.currentText()
        if m != "All Methods" and m in method_map:
            clauses.append(f"({method_map[m]})")
        if a != "All Actions" and a in action_map:
            clauses.append(f"({action_map[a]})")
        return " AND ".join(clauses) if clauses else "1=1"

    def _apply_coc_filter(self):
        data = self.fetch_audit_logs(self._coc_filter_sql())
        self._coc_table.setRowCount(0)
        danger_kw = ["FAIL","MISMATCH","UNAUTHORIZED","DENIED","SUSPICIOUS","BLOCKED"]
        for ri, row_data in enumerate(data):
            self._coc_table.insertRow(ri)
            is_danger = any(any(k in str(v).upper() for k in danger_kw) for v in row_data)
            for ci, value in enumerate(row_data):
                item = QtWidgets.QTableWidgetItem(str(value) if value else "—")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if is_danger:
                    item.setForeground(QtGui.QColor("#c0392b"))
                self._coc_table.setItem(ri, ci, item)

    # ═══════════════════════════════════════════════════════════
    # PAGE 2 — EVIDENCE VAULT
    # ═══════════════════════════════════════════════════════════
    def show_evidence_vault(self):
        self._set_active_nav(2)
        self._clear_content()

        self.content_layout.addWidget(self._page_title("Evidence Vault"))

        # Filter
        fb = QtWidgets.QHBoxLayout(); fb.setSpacing(10)
        lbl = QtWidgets.QLabel("Status:"); lbl.setStyleSheet("font-size:13px; color:#475569;")
        fb.addWidget(lbl)
        self._vault_status = QtWidgets.QComboBox()
        self._vault_status.addItems(["All","PENDING","FETCHED","DECRYPTED"])
        self._vault_status.setFixedWidth(130)
        self._vault_status.setStyleSheet(
            "padding:6px; font-size:13px; border:1px solid #cbd5e1; "
            "border-radius:6px; background:white;"
        )
        fb.addWidget(self._vault_status)
        apply_btn = QtWidgets.QPushButton("Filter")
        apply_btn.setFixedSize(80, 34)
        apply_btn.setStyleSheet(
            "background:#0078d7; color:white; border-radius:6px; font-size:13px;"
        )
        apply_btn.clicked.connect(self._apply_vault_filter)
        fb.addWidget(apply_btn); fb.addStretch()
        fw = QtWidgets.QWidget(); fw.setLayout(fb)
        self.content_layout.addWidget(fw)

        rows = self._db(
            "SELECT sender_name,receiver_email,file_name,method,"
            "status,case_id,investigator,created_at,fetched_at "
            "FROM vault_transfers ORDER BY id DESC"
        )
        self._vault_table = self._make_table(
            ["Sender","Receiver","File","Method","Status",
             "Case ID","Investigator","Sent At","Fetched At"],
            rows, danger_kw=[]
        )
        self._color_vault_status()
        self._vault_table.setMinimumHeight(500)
        self.content_layout.addWidget(self._vault_table, 1)

    def _color_vault_status(self):
        sc = {"PENDING":"#92400e","FETCHED":"#065f46","DECRYPTED":"#1e40af"}
        for r in range(self._vault_table.rowCount()):
            item = self._vault_table.item(r, 4)
            if item:
                item.setForeground(QtGui.QColor(sc.get(item.text(), "#334155")))
                item.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))

    def _apply_vault_filter(self):
        status = self._vault_status.currentText()
        sql = (
            "SELECT sender_name,receiver_email,file_name,method,"
            "status,case_id,investigator,created_at,fetched_at "
            "FROM vault_transfers " +
            ("WHERE status=? " if status != "All" else "") +
            "ORDER BY id DESC"
        )
        rows = self._db(sql, (status,) if status != "All" else ())
        self._vault_table.setRowCount(0)
        for ri, row in enumerate(rows):
            self._vault_table.insertRow(ri)
            for ci, val in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(val) if val else "—")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if ci == 4:
                    sc = {"PENDING":"#92400e","FETCHED":"#065f46","DECRYPTED":"#1e40af"}
                    item.setForeground(QtGui.QColor(sc.get(str(val), "#334155")))
                    item.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))
                self._vault_table.setItem(ri, ci, item)

    # ═══════════════════════════════════════════════════════════
    # PAGE 3 — INTEGRITY AUDIT (sender + receiver, both sides)
    # ═══════════════════════════════════════════════════════════
    def show_integrity_audit(self):
        self._set_active_nav(3)
        self._clear_content()

        self.content_layout.addWidget(self._page_title("Integrity Audit"))

        passed         = len(self.fetch_audit_logs("action='INTEGRITY_PASSED'"))
        failed         = len(self.fetch_audit_logs("action='INTEGRITY_FAILED'"))
        sender_hashes  = len(self.fetch_audit_logs("action='FILE_ENCRYPTED'"))
        total          = passed + failed
        rate           = f"{int(passed/total*100)}%" if total else "N/A"

        self.content_layout.addWidget(self._cards_row([
            self._stat_card("Sender Hashes Generated", sender_hashes, "#0369a1", "#eff6ff"),
            self._stat_card("Integrity Passed",  passed,  "#065f46", "#f0fdf4"),
            self._stat_card("Integrity Failed",  failed,  "#991b1b", "#fef2f2"),
            self._stat_card("Pass Rate",          rate,    "#6d28d9", "#f5f3ff"),
        ]))

        # Sender records
        s_lbl = QtWidgets.QLabel("Sender — SHA-256 Hash Generation")
        s_lbl.setStyleSheet(
            "font-size:14px; font-weight:bold; color:#0369a1; margin-top:8px;"
        )
        self.content_layout.addWidget(s_lbl)

        sender_rows = self.fetch_audit_logs("action='FILE_ENCRYPTED'")
        sender_fmt  = []
        for row in sender_rows:
            details  = str(row[5])
            hash_val = "—"
            if "SHA-256:" in details:
                hash_val = details.split("SHA-256:")[-1].split("|")[0].strip()
                if len(hash_val) > 28: hash_val = hash_val[:28] + "..."
            sender_fmt.append([row[0], row[4], hash_val, "Generated", row[6]])

        s_tbl = self._make_table(
            ["Sender","File","SHA-256 (partial)","Status","Timestamp"],
            sender_fmt, danger_kw=[]
        )
        s_tbl.setMinimumHeight(200)
        for r in range(s_tbl.rowCount()):
            item = s_tbl.item(r, 3)
            if item: item.setForeground(QtGui.QColor("#0369a1"))
        self.content_layout.addWidget(s_tbl)

        # Receiver records
        r_lbl = QtWidgets.QLabel("Receiver — Integrity Verification Results")
        r_lbl.setStyleSheet(
            "font-size:14px; font-weight:bold; color:#065f46; margin-top:8px;"
        )
        self.content_layout.addWidget(r_lbl)

        recv_rows = self.fetch_audit_logs(
            "action IN ('INTEGRITY_PASSED','INTEGRITY_FAILED')"
        )
        recv_fmt = []
        for row in recv_rows:
            result = "MATCH" if "PASSED" in str(row[2]).upper() else "MISMATCH"
            recv_fmt.append([row[0], row[4], result, str(row[5])[:40], row[6]])

        r_tbl = self._make_table(
            ["Receiver","File","Result","Details","Timestamp"], recv_fmt
        )
        r_tbl.setMinimumHeight(200)
        for r in range(r_tbl.rowCount()):
            item = r_tbl.item(r, 2)
            if item:
                c = "#065f46" if item.text() == "MATCH" else "#991b1b"
                item.setForeground(QtGui.QColor(c))
                item.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))
        self.content_layout.addWidget(r_tbl)
        self.content_layout.addStretch()

    # ═══════════════════════════════════════════════════════════
    # PAGE 4 — SECURITY ALERTS
    # ═══════════════════════════════════════════════════════════
    def show_alerts(self):
        self._set_active_nav(4)
        self._clear_content()

        self.content_layout.addWidget(self._page_title("Security Alerts", "#991b1b"))

        rows    = self.fetch_audit_logs(
            "action LIKE '%FAIL%' OR action LIKE '%SUSPICIOUS%' "
            "OR action LIKE '%UNAUTHORIZED%' OR action LIKE '%DENIED%' "
            "OR action LIKE '%BLOCKED%'"
        )
        unauth  = len([r for r in rows if "UNAUTHORIZED" in str(r[2]).upper()])
        blocked = len([r for r in rows if "BLOCKED"      in str(r[2]).upper()])
        failed  = len([r for r in rows if "FAIL"         in str(r[2]).upper()])

        self.content_layout.addWidget(self._cards_row([
            self._stat_card("Total Alerts",          len(rows), "#991b1b", "#fef2f2"),
            self._stat_card("Unauthorized Access",   unauth,    "#7c2d12", "#fff7ed"),
            self._stat_card("Transfers Blocked",     blocked,   "#92400e", "#fffbeb"),
            self._stat_card("Failed Operations",     failed,    "#991b1b", "#fef2f2"),
        ]))

        tbl = self._make_table(
            ["User","Role","Alert Type","Method","Details","Timestamp"], rows
        )
        tbl.setMinimumHeight(460)
        self.content_layout.addWidget(tbl, 1)

    # ═══════════════════════════════════════════════════════════
    # PAGE 5 — USER MANAGEMENT
    # ═══════════════════════════════════════════════════════════
    def show_user_management(self):
        self._set_active_nav(5)
        self._clear_content()

        self.content_layout.addWidget(self._page_title("User Management"))

        scope_lbl = QtWidgets.QLabel(
            "Managing: All roles (Sender, Receiver, Admin)" if self.is_super
            else "Managing: Senders and Receivers only"
        )
        scope_lbl.setStyleSheet(
            "font-size:13px; color:#64748b; background:#f1f5f9; "
            "padding:6px 14px; border-radius:6px;"
        )
        self.content_layout.addWidget(scope_lbl)

        pending = self.fetch_users("pending")
        active  = self.fetch_users("active")
        revoked = self.fetch_users("revoked")

        self.content_layout.addWidget(self._cards_row([
            self._stat_card(f"Pending Approval",  len(pending), "#92400e", "#fffbeb"),
            self._stat_card(f"Active Users",       len(active),  "#065f46", "#f0fdf4"),
            self._stat_card(f"Revoked Accounts",   len(revoked), "#991b1b", "#fef2f2"),
        ]))

        tabs = QtWidgets.QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab {
                background:#e2e8f0; color:#475569; padding:14px 28px;
                border-radius:6px 6px 0 0; font-size:13px; font-weight:bold;
                min-width:160px;
            }
            QTabBar::tab:selected { background:#0078d7; color:white; }
            QTabWidget::pane { border:1px solid #e2e8f0; border-radius:0 8px 8px 8px; }
        """)
        tabs.addTab(self._build_user_tab(pending, "pending"),
                    f"Pending ({len(pending)})")
        tabs.addTab(self._build_user_tab(active,  "active"),
                    f"Active ({len(active)})")
        tabs.addTab(self._build_user_tab(revoked, "revoked"),
                    f"Revoked ({len(revoked)})")
        tabs.setCurrentIndex(0 if pending else 1)
        self.content_layout.addWidget(tabs, 1)

    def _build_user_tab(self, users, tab_type):
        w  = QtWidgets.QWidget()
        vl = QtWidgets.QVBoxLayout(w)
        vl.setContentsMargins(12, 12, 12, 12)

        if not users:
            empty = QtWidgets.QLabel(
                "No pending approvals — all caught up." if tab_type == "pending"
                else "No users in this category."
            )
            empty.setAlignment(QtCore.Qt.AlignCenter)
            empty.setStyleSheet("color:#64748b; font-size:14px; padding:40px;")
            vl.addWidget(empty)
            return w

        tbl = QtWidgets.QTableWidget(0, 6)
        tbl.setHorizontalHeaderLabels(
            ["Name","Email","Role","Registered","Status","Actions"]
        )
        tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Fixed)
        tbl.setColumnWidth(5, 230)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().setDefaultSectionSize(52)
        tbl.verticalHeader().hide()
        tbl.setStyleSheet(
            "QTableWidget::item{padding:8px;}"
            "QTableWidget::item:alternate{background:#f8fafc;}"
        )

        role_colors = {
            "Sender":"#1d4ed8","Receiver":"#065f46",
            "Admin":"#7c3aed","SuperAdmin":"#9a3412"
        }

        def btn_style(color):
            return (
                f"QPushButton{{background:{color};color:white;border-radius:5px;"
                f"font-size:12px;font-weight:bold;padding:4px 10px;}}"
            )

        for row in users:
            uid, name, email, role, is_approved, is_revoked, created_at = row
            r = tbl.rowCount(); tbl.insertRow(r)

            tbl.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            tbl.setItem(r, 1, QtWidgets.QTableWidgetItem(email))

            ri_item = QtWidgets.QTableWidgetItem(role)
            ri_item.setForeground(QtGui.QColor(role_colors.get(role, "#334155")))
            ri_item.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))
            tbl.setItem(r, 2, ri_item)

            tbl.setItem(r, 3, QtWidgets.QTableWidgetItem(
                str(created_at)[:16] if created_at else "—"
            ))

            st_text  = "Revoked" if is_revoked else ("Active" if is_approved else "Pending")
            st_color = {"Revoked":"#991b1b","Active":"#065f46","Pending":"#92400e"}[st_text]
            si = QtWidgets.QTableWidgetItem(st_text)
            si.setForeground(QtGui.QColor(st_color))
            si.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))
            tbl.setItem(r, 4, si)

            bw = QtWidgets.QWidget()
            bl = QtWidgets.QHBoxLayout(bw)
            bl.setContentsMargins(4, 4, 4, 4); bl.setSpacing(6)

            if tab_type == "pending":
                a = QtWidgets.QPushButton("Approve")
                a.setStyleSheet(btn_style("#16a34a"))
                a.clicked.connect(
                    lambda _, u=uid,n=name,ro=role: self.approve_user(u,n,ro))
                d = QtWidgets.QPushButton("Delete")
                d.setStyleSheet(btn_style("#dc2626"))
                d.clicked.connect(
                    lambda _, u=uid,n=name,ro=role: self.delete_user(u,n,ro))
                bl.addWidget(a); bl.addWidget(d)

            elif tab_type == "active":
                rv = QtWidgets.QPushButton("Revoke")
                rv.setStyleSheet(btn_style("#dc2626"))
                rv.clicked.connect(
                    lambda _, u=uid,n=name,ro=role: self.revoke_user(u,n,ro))
                d = QtWidgets.QPushButton("Delete")
                d.setStyleSheet(btn_style("#7f1d1d"))
                d.clicked.connect(
                    lambda _, u=uid,n=name,ro=role: self.delete_user(u,n,ro))
                bl.addWidget(rv); bl.addWidget(d)

            elif tab_type == "revoked":
                ri2 = QtWidgets.QPushButton("Reinstate")
                ri2.setStyleSheet(btn_style("#0369a1"))
                ri2.clicked.connect(
                    lambda _, u=uid,n=name,ro=role: self.reinstate_user(u,n,ro))
                d = QtWidgets.QPushButton("Delete")
                d.setStyleSheet(btn_style("#7f1d1d"))
                d.clicked.connect(
                    lambda _, u=uid,n=name,ro=role: self.delete_user(u,n,ro))
                bl.addWidget(ri2); bl.addWidget(d)

            tbl.setCellWidget(r, 5, bw)

        vl.addWidget(tbl)
        return w

    # ═══════════════════════════════════════════════════════════
    # PAGE 6 — SETTINGS
    # ═══════════════════════════════════════════════════════════
    def show_settings(self):
        self._set_active_nav(6)
        self._clear_content()

        self.content_layout.addWidget(self._page_title("Admin Settings"))

        inp_style = (
            "padding:10px; font-size:14px; border:1px solid #cbd5e1; "
            "border-radius:8px; background:#f8fafc; min-height:40px;"
        )
        btn_primary = (
            "background:#0078d7; color:white; font-size:14px; font-weight:bold; "
            "border-radius:8px; padding:10px 24px;"
        )

        # ── CHANGE PASSWORD ───────────────────────────────────────
        pw_box = QtWidgets.QGroupBox("Change My Password")
        pw_l   = QtWidgets.QVBoxLayout(pw_box)
        pw_l.setSpacing(12)

        old_pw  = QtWidgets.QLineEdit()
        new_pw  = QtWidgets.QLineEdit()
        conf_pw = QtWidgets.QLineEdit()
        for f, ph in [(old_pw,"Current password"),
                      (new_pw,"New password (min 8 chars, letter+digit+symbol)"),
                      (conf_pw,"Confirm new password")]:
            f.setEchoMode(QtWidgets.QLineEdit.Password)
            f.setPlaceholderText(ph)
            f.setStyleSheet(inp_style)

        pw_msg = QtWidgets.QLabel("")
        pw_msg.setStyleSheet("font-size:13px;")
        pw_btn = QtWidgets.QPushButton("Update Password")
        pw_btn.setStyleSheet(btn_primary)

        def do_change_pw():
            from app import verify_password, hash_password, check_password_strength
            old = old_pw.text(); new = new_pw.text(); conf = conf_pw.text()
            if not all([old, new, conf]):
                pw_msg.setText("All fields are required.")
                pw_msg.setStyleSheet("font-size:13px; color:#dc2626;"); return
            rows = self._db("SELECT password FROM users WHERE name=?", (self.user_name,))
            if not rows or not verify_password(old, rows[0][0]):
                pw_msg.setText("Current password is incorrect.")
                pw_msg.setStyleSheet("font-size:13px; color:#dc2626;"); return
            if new != conf:
                pw_msg.setText("New passwords do not match.")
                pw_msg.setStyleSheet("font-size:13px; color:#dc2626;"); return
            _, _, strong = check_password_strength(new)
            if not strong:
                pw_msg.setText("Password too weak — need letters, digits and a symbol.")
                pw_msg.setStyleSheet("font-size:13px; color:#dc2626;"); return
            if self._db_write(
                "UPDATE users SET password=? WHERE name=?",
                (hash_password(new), self.user_name)
            ):
                write_audit_log(self.user_name, self.user_role,
                                "PASSWORD_CHANGED", "Settings")
                pw_msg.setText("Password updated successfully.")
                pw_msg.setStyleSheet("font-size:13px; color:#16a34a;")
                old_pw.clear(); new_pw.clear(); conf_pw.clear()

        pw_btn.clicked.connect(do_change_pw)
        for widget in [old_pw, new_pw, conf_pw, pw_msg, pw_btn]:
            pw_l.addWidget(widget)
        self.content_layout.addWidget(pw_box)

        # ── SMTP CONFIG (SuperAdmin only) ─────────────────────────
        if self.is_super:
            smtp_box = QtWidgets.QGroupBox("OTP Email Configuration (SuperAdmin only)")
            smtp_l   = QtWidgets.QVBoxLayout(smtp_box)
            smtp_l.setSpacing(12)

            note = QtWidgets.QLabel(
                "These values update the running session only.\n"
                "To persist permanently, update your .env file."
            )
            note.setStyleSheet("font-size:12px; color:#64748b;")
            note.setWordWrap(True)
            smtp_l.addWidget(note)

            import os as _os
            smtp_email = QtWidgets.QLineEdit()
            smtp_email.setPlaceholderText("OTP sender Gmail address")
            smtp_email.setText(_os.getenv("OTP_SENDER_EMAIL", ""))
            smtp_email.setStyleSheet(inp_style)

            smtp_pass = QtWidgets.QLineEdit()
            smtp_pass.setEchoMode(QtWidgets.QLineEdit.Password)
            smtp_pass.setPlaceholderText("Gmail App Password (16 characters)")
            smtp_pass.setText(_os.getenv("OTP_SENDER_PASSWORD", ""))
            smtp_pass.setStyleSheet(inp_style)

            smtp_msg = QtWidgets.QLabel("")
            smtp_msg.setStyleSheet("font-size:13px;")

            smtp_btn = QtWidgets.QPushButton("Test Connection & Save to Session")
            smtp_btn.setStyleSheet(btn_primary)

            def do_smtp_test():
                import smtplib, ssl as _ssl
                em = smtp_email.text().strip()
                pw = smtp_pass.text().strip()
                if not em or not pw:
                    smtp_msg.setText("Both fields are required.")
                    smtp_msg.setStyleSheet("font-size:13px; color:#dc2626;"); return
                smtp_msg.setText("Testing connection...")
                smtp_msg.setStyleSheet("font-size:13px; color:#0369a1;")
                QtWidgets.QApplication.processEvents()
                try:
                    ctx = _ssl.create_default_context()
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=10) as s:
                        s.login(em, pw)
                    import app as _app
                    _app.OTP_SENDER_EMAIL    = em
                    _app.OTP_SENDER_PASSWORD = pw
                    write_audit_log(self.user_name, self.user_role,
                                    "SMTP_CONFIG_UPDATED", "Settings",
                                    details=f"Email: {em}")
                    smtp_msg.setText("Connection successful. Session updated.")
                    smtp_msg.setStyleSheet("font-size:13px; color:#16a34a;")
                except Exception as e:
                    smtp_msg.setText(f"Failed: {e}")
                    smtp_msg.setStyleSheet("font-size:13px; color:#dc2626;")

            smtp_btn.clicked.connect(do_smtp_test)
            for widget in [smtp_email, smtp_pass, smtp_msg, smtp_btn]:
                smtp_l.addWidget(widget)
            self.content_layout.addWidget(smtp_box)

        # ── DATABASE STATISTICS ───────────────────────────────────
        db_box = QtWidgets.QGroupBox("Database Statistics")
        db_l   = QtWidgets.QVBoxLayout(db_box)
        db_l.setSpacing(10)

        def db_row(label, count):
            h    = QtWidgets.QHBoxLayout()
            lbl  = QtWidgets.QLabel(label)
            lbl.setStyleSheet("font-size:13px; color:#475569;")
            val  = QtWidgets.QLabel(str(count))
            val.setStyleSheet("font-size:13px; font-weight:bold; color:#1e293b;")
            h.addWidget(lbl); h.addWidget(val); h.addStretch()
            w = QtWidgets.QWidget(); w.setLayout(h)
            return w

        audit_count  = (self._db("SELECT COUNT(*) FROM audit_logs") or [(0,)])[0][0]
        tx_count     = (self._db("SELECT COUNT(*) FROM vault_transfers") or [(0,)])[0][0]
        user_count   = (self._db("SELECT COUNT(*) FROM users") or [(0,)])[0][0]
        notif_count  = (self._db("SELECT COUNT(*) FROM shared_notifications") or [(0,)])[0][0]
        db_size      = f"{os.path.getsize(DB_PATH) // 1024} KB" if os.path.exists(DB_PATH) else "N/A"

        for label, val in [
            ("Audit log entries:", audit_count),
            ("Vault transfers:",   tx_count),
            ("Registered users:",  user_count),
            ("Shared notifications:", notif_count),
            ("Database file size:", db_size),
        ]:
            db_l.addWidget(db_row(label, val))

        if self.is_super:
            clear_btn = QtWidgets.QPushButton("Clear Audit Logs Older Than 90 Days")
            clear_btn.setStyleSheet(
                "background:#fef2f2; color:#dc2626; border:1px solid #fca5a5; "
                "border-radius:8px; font-size:13px; padding:8px 16px; margin-top:8px;"
            )
            def do_clear():
                if QtWidgets.QMessageBox.question(
                    self, "Confirm Clear",
                    "Delete all audit logs older than 90 days?\nThis cannot be undone.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                ) == QtWidgets.QMessageBox.Yes:
                    self._db_write(
                        "DELETE FROM audit_logs WHERE timestamp < DATE('now','-90 days')"
                    )
                    write_audit_log(self.user_name, self.user_role,
                                    "AUDIT_LOGS_CLEARED", "Settings",
                                    details="Logs older than 90 days removed")
                    QtWidgets.QMessageBox.information(self, "Done", "Old logs cleared.")
                    self.show_settings()
            clear_btn.clicked.connect(do_clear)
            db_l.addWidget(clear_btn)

        self.content_layout.addWidget(db_box)
        self.content_layout.addStretch()


    # ═══════════════════════════════════════════════════════════
    # PAGE 7 — SYSTEM MONITORING (Fixed & Complete)
    # ═══════════════════════════════════════════════════════════
        # ═══════════════════════════════════════════════════════════
    # PAGE 7 — SYSTEM MONITORING
    # ═══════════════════════════════════════════════════════════
    def show_system_monitoring(self):
        """System Monitoring Page - With Popup Confirmations"""
        self._set_active_nav(7)
        self._clear_content()
        
        QtCore.QCoreApplication.processEvents()
        
        self._forensic_db = r"C:\ProgramData\SecureForensic\forensic.db"

        # ── HEADER ──────────────────────────────────────────────
        hdr = QtWidgets.QHBoxLayout()
        title_lbl = QtWidgets.QLabel("🛡️ System Monitoring — Threat Detection")
        title_lbl.setStyleSheet("font-size:22px; font-weight:bold; color:#1e293b;")
        hdr.addWidget(title_lbl)

        # Refresh Button - WITH POPUP
        btn_refresh = QtWidgets.QPushButton("🔄  Refresh")
        btn_refresh.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn_refresh.setStyleSheet(
            "QPushButton{background:#2563eb;color:white;border-radius:6px;"
            "padding:8px 18px;font-weight:bold;font-size:13px;border:none;}"
            "QPushButton:hover{background:#1d4ed8;}"
        )
        
        def refresh_with_popup():
            reply = QtWidgets.QMessageBox.question(
                self, "Confirm Refresh",
                "Are you sure you want to refresh the System Monitoring data?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.show_system_monitoring()
        
        btn_refresh.clicked.connect(refresh_with_popup)
        hdr.addWidget(btn_refresh, 0, QtCore.Qt.AlignRight)
        self.content_layout.addLayout(hdr)

        # ── LOAD DATA ────────────────────────────────────────────
        external_rows = []
        if os.path.exists(self._forensic_db):
            try:
                conn = sqlite3.connect(self._forensic_db)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username, action, method, file_name, file_path, time "
                    "FROM logs ORDER BY id DESC LIMIT 500"
                )
                external_rows = cur.fetchall()
                conn.close()
            except Exception as e:
                print(f"Forensic DB error: {e}")

        internal_rows = []
        if os.path.exists(DB_PATH):
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username, action, method, file_name, details, timestamp "
                    "FROM audit_logs ORDER BY id DESC LIMIT 500"
                )
                internal_rows = cur.fetchall()
                conn.close()
            except Exception as e:
                print(f"Audit DB error: {e}")

        external_count = len(external_rows)
        internal_count = len(internal_rows)

        # ── STAT CARDS ───────────────────────────────────────────
        stat_row = QtWidgets.QHBoxLayout()
        stat_row.setSpacing(12)

        def stat_card(label, value, bg, fg, icon=""):
            f = QtWidgets.QFrame()
            f.setStyleSheet(f"background:{bg};border-radius:10px;border:1px solid {fg}33;")
            h = QtWidgets.QHBoxLayout(f)
            h.setContentsMargins(16, 10, 16, 10)
            
            if icon:
                ic = QtWidgets.QLabel(icon)
                ic.setStyleSheet(f"font-size:24px;border:none;background:transparent;")
                h.addWidget(ic)
            
            v = QtWidgets.QLabel(str(value))
            v.setStyleSheet(f"font-size:28px;font-weight:bold;color:{fg};border:none;")
            l = QtWidgets.QLabel(label)
            l.setStyleSheet(f"font-size:12px;color:{fg};font-weight:bold;border:none;")
            l.setWordWrap(True)
            h.addWidget(v)
            h.addWidget(l)
            h.addStretch()
            return f

        stat_row.addWidget(stat_card("External Threats", external_count, "#fef2f2", "#dc2626", "🚨"))
        stat_row.addWidget(stat_card("Authorized Ops", internal_count, "#f0fdf4", "#16a34a", "✅"))
        stat_row.addWidget(stat_card("Total Activities", external_count + internal_count, "#eff6ff", "#2563eb", "📊"))
        self.content_layout.addLayout(stat_row)

        # ── ACTION BUTTONS ROW ──────────────────────────────────
        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(10)

        # Generate Report Button - WITH POPUP
        btn_report = QtWidgets.QPushButton("📄 Generate Report")
        btn_report.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn_report.setStyleSheet(
            "QPushButton{background:#7c3aed;color:white;border-radius:6px;"
            "padding:8px 18px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#6d28d9;}"
        )
        
        def generate_report_with_popup():
            reply = QtWidgets.QMessageBox.question(
                self, "Generate Report",
                "Are you sure you want to generate a new security report?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self._generate_full_report()
        
        btn_report.clicked.connect(generate_report_with_popup)
        action_row.addWidget(btn_report)

        # Open Reports Button
        btn_open_reports = QtWidgets.QPushButton("📂 Open Reports")
        btn_open_reports.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn_open_reports.setStyleSheet(
            "QPushButton{background:#475569;color:white;border-radius:6px;"
            "padding:8px 18px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#334155;}"
        )
        btn_open_reports.clicked.connect(self._open_reports_folder)
        action_row.addWidget(btn_open_reports)

        # Clear All Logs Button - WITH POPUP
        btn_clear_all = QtWidgets.QPushButton("🗑 Clear All Logs")
        btn_clear_all.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn_clear_all.setStyleSheet(
            "QPushButton{background:#dc2626;color:white;border-radius:6px;"
            "padding:8px 18px;font-weight:bold;font-size:12px;border:none;}"
            "QPushButton:hover{background:#b91c1c;}"
        )
        btn_clear_all.clicked.connect(lambda: self._action_flush_db(self._forensic_db))
        action_row.addWidget(btn_clear_all)

        action_row.addStretch()
        self.content_layout.addLayout(action_row)

        # ── EXTERNAL THREATS TABLE ──────────────────────────────
        ext_hdr = QtWidgets.QHBoxLayout()
        ext_title = QtWidgets.QLabel(f"🔴  Unauthorized Activity Log — forensic.db  ({external_count} records)")
        ext_title.setStyleSheet("font-size:13px;font-weight:bold;color:#dc2626;")
        ext_hdr.addWidget(ext_title)
        self.content_layout.addLayout(ext_hdr)

        # Simple column headers - No "Control" column
        col_headers = ["ID", "User", "Action", "Method", "File Name", "Time"]
        tbl_ext = QtWidgets.QTableWidget(0, len(col_headers))
        tbl_ext.setHorizontalHeaderLabels(col_headers)
        tbl_ext.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        tbl_ext.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl_ext.setAlternatingRowColors(True)
        tbl_ext.verticalHeader().hide()
        tbl_ext.setMinimumHeight(220)
        tbl_ext.setStyleSheet(
            "QTableWidget{border:1px solid #fca5a5;border-radius:6px;background:white;}"
            "QTableWidget::item{color:#1e293b;padding:5px;}"
            "QTableWidget::item:alternate{background:#fff5f5;}"
            "QHeaderView::section{background:#dc2626;color:white;padding:8px;font-weight:bold;}"
        )

        if external_rows:
            for ri, row in enumerate(external_rows):
                tbl_ext.insertRow(ri)

                # ID
                item = QtWidgets.QTableWidgetItem(str(row[0]))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                tbl_ext.setItem(ri, 0, item)

                # Username
                item = QtWidgets.QTableWidgetItem(str(row[1]) if row[1] else "System")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                tbl_ext.setItem(ri, 1, item)

                # Action
                action_text = str(row[2]) if row[2] else "Unknown"
                item = QtWidgets.QTableWidgetItem(action_text)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if "UNAUTHORIZED" in action_text.upper() or "BLOCKED" in action_text.upper():
                    item.setForeground(QtGui.QColor("#dc2626"))
                    item.setFont(QtGui.QFont("Segoe UI", weight=QtGui.QFont.Bold))
                tbl_ext.setItem(ri, 2, item)

                # Method
                item = QtWidgets.QTableWidgetItem(str(row[3]) if row[3] else "—")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                tbl_ext.setItem(ri, 3, item)

                # File Name - row[4] is file_name from forensic.db
                file_name_display = str(row[4]) if row[4] else "—"
                item = QtWidgets.QTableWidgetItem(file_name_display)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                tbl_ext.setItem(ri, 4, item)

                # Time
                item = QtWidgets.QTableWidgetItem(str(row[6]) if row[6] else "—")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                tbl_ext.setItem(ri, 5, item)
        else:
            tbl_ext.insertRow(0)
            ph = QtWidgets.QTableWidgetItem("✅  No unauthorized activity detected — system is clean")
            ph.setTextAlignment(QtCore.Qt.AlignCenter)
            ph.setForeground(QtGui.QColor("#16a34a"))
            tbl_ext.setItem(0, 0, ph)
            tbl_ext.setSpan(0, 0, 1, len(col_headers))

        self.content_layout.addWidget(tbl_ext)

        # ── INTERNAL LOGS TABLE ──────────────────────────────────
        int_title = QtWidgets.QLabel(f"🟢  Authorized App Operations — users.db  ({internal_count} records)")
        int_title.setStyleSheet("font-size:13px;font-weight:bold;color:#16a34a;margin-top:12px;")
        self.content_layout.addWidget(int_title)

        int_headers = ["ID", "User", "Action", "Method", "File", "Details", "Time"]
        tbl_int = QtWidgets.QTableWidget(0, len(int_headers))
        tbl_int.setHorizontalHeaderLabels(int_headers)
        tbl_int.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        tbl_int.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl_int.setAlternatingRowColors(True)
        tbl_int.verticalHeader().hide()
        tbl_int.setMinimumHeight(150)
        tbl_int.setStyleSheet(
            "QTableWidget{border:1px solid #86efac;border-radius:6px;background:white;}"
            "QTableWidget::item{color:#1e293b;padding:5px;}"
            "QTableWidget::item:alternate{background:#f0fdf4;}"
            "QHeaderView::section{background:#16a34a;color:white;padding:8px;font-weight:bold;}"
        )

        if internal_rows:
            for ri, row in enumerate(internal_rows):
                tbl_int.insertRow(ri)
                for ci, val in enumerate(row):
                    item = QtWidgets.QTableWidgetItem(str(val) if val else "—")
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    if ci == 2:
                        if "AUTHORIZED" in str(val).upper() or "SUCCESS" in str(val).upper():
                            item.setForeground(QtGui.QColor("#16a34a"))
                    tbl_int.setItem(ri, ci, item)
        else:
            tbl_int.insertRow(0)
            ph = QtWidgets.QTableWidgetItem("📝  No authorized operations recorded yet")
            ph.setTextAlignment(QtCore.Qt.AlignCenter)
            ph.setForeground(QtGui.QColor("#64748b"))
            tbl_int.setItem(0, 0, ph)
            tbl_int.setSpan(0, 0, 1, len(int_headers))

        self.content_layout.addWidget(tbl_int)

        # ── CHART ─────────────────────────────────────────────────
        chart_frame = QtWidgets.QFrame()
        chart_frame.setStyleSheet("background:#1e293b;border-radius:10px;margin-top:14px;")
        chart_hl = QtWidgets.QHBoxLayout(chart_frame)
        chart_hl.setContentsMargins(18, 12, 18, 12)

        sv = QtWidgets.QVBoxLayout()
        ttl = QtWidgets.QLabel("📊 System Security Overview")
        ttl.setStyleSheet("color:#f8fafc;font-size:14px;font-weight:bold;border:none;")
        sv.addWidget(ttl)
        
        el = QtWidgets.QLabel(f"🔴  External Threats:         {external_count}")
        el.setStyleSheet("color:#ef4444;font-size:13px;border:none;")
        sv.addWidget(el)
        
        il = QtWidgets.QLabel(f"🟢  Authorized Operations:   {internal_count}")
        il.setStyleSheet("color:#22c55e;font-size:13px;border:none;")
        sv.addWidget(il)
        
        sv.addStretch()
        chart_hl.addLayout(sv, 2)

        fig, ax = plt.subplots(figsize=(4, 1.8), facecolor='#1e293b')
        cats = ['External Risk', 'App Secure']
        vals = [external_count, internal_count]
        clrs = ['#dc2626', '#16a34a']
        
        if not any(vals):
            vals = [1, 1]
            cats = ['No Risks', 'Ready']
            clrs = ['#64748b', '#2563eb']
        
        bars = ax.barh(cats, vals, color=clrs, height=0.55)
        ax.set_facecolor('#1e293b')
        ax.tick_params(colors='#f8fafc', labelsize=10)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.grid(axis='x', color='#334155', linestyle='--', alpha=0.5)
        
        for bar in bars:
            w = bar.get_width()
            if w > 0:
                ax.text(w + 0.1, bar.get_y() + bar.get_height() / 2,
                        str(int(w)), va='center', ha='left', 
                        color='#f8fafc', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet("background:transparent;border:none;")
        chart_hl.addWidget(canvas, 3)
        self.content_layout.addWidget(chart_frame)
        
        # ── STATUS BAR ────────────────────────────────────────────
        status_frame = QtWidgets.QFrame()
        status_frame.setStyleSheet("background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;margin-top:10px;")
        status_layout = QtWidgets.QHBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 8, 16, 8)
        
        status_icon = QtWidgets.QLabel("🟢")
        status_icon.setStyleSheet("font-size:16px;border:none;background:transparent;")
        status_layout.addWidget(status_icon)
        
        status_text = QtWidgets.QLabel(f"System Monitoring Active | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {external_count} threats detected")
        status_text.setStyleSheet("font-size:12px;color:#475569;border:none;background:transparent;")
        status_layout.addWidget(status_text)
        status_layout.addStretch()
        
        self.content_layout.addWidget(status_frame)
        self.content_layout.addStretch()
        self.content_layout.update()

    # ═══════════════════════════════════════════════════════════
    # BLOCKED THREAT TRACKING (per forensic.db row, persisted locally)
    # ═══════════════════════════════════════════════════════════
    def _load_blocked_map(self):
        """Returns dict: { row_id(str): {type, mode, blocked_at, blocked_by} }"""
        if os.path.exists(self.BLOCKED_STORAGE):
            try:
                with open(self.BLOCKED_STORAGE, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_blocked_map(self, data):
        try:
            with open(self.BLOCKED_STORAGE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to save blocked map: {e}")

    def _mark_row_blocked(self, row_id, threat_type, mode):
        """mode = 'Temporary' or 'Permanent'"""
        data = self._load_blocked_map()
        data[str(row_id)] = {
            "type": threat_type,
            "mode": mode,
            "blocked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "blocked_by": self.user_name,
        }
        self._save_blocked_map(data)

    def _unmark_row_blocked(self, row_id):
        data = self._load_blocked_map()
        data.pop(str(row_id), None)
        self._save_blocked_map(data)

    def _get_blocked_files(self):
        """Get list of quarantined/blocked files"""
        blocked = []
        quarantine_dir = r"C:\Quarantine"
        if os.path.exists(quarantine_dir):
            try:
                import json
                for file in os.listdir(quarantine_dir):
                    if file.endswith('.json'):
                        continue
                    meta_file = file + '.json'
                    if os.path.exists(os.path.join(quarantine_dir, meta_file)):
                        try:
                            with open(os.path.join(quarantine_dir, meta_file), 'r') as f:
                                data = json.load(f)
                                blocked.append(data)
                        except:
                            blocked.append({
                                "original_name": file,
                                "original_path": os.path.join(quarantine_dir, file),
                                "reason": "Unknown",
                                "timestamp": datetime.now().isoformat()
                            })
                    else:
                        blocked.append({
                            "original_name": file,
                            "original_path": os.path.join(quarantine_dir, file),
                            "reason": "Unknown",
                            "timestamp": datetime.now().isoformat()
                        })
            except Exception as e:
                print(f"Error reading quarantine: {e}")
        return blocked

    def _open_reports_folder(self):
        """Open reports folder"""
        report_dir = r"C:\SecureForensic\Reports"
        if not os.path.exists(report_dir):
            try:
                os.makedirs(report_dir)
            except:
                pass
        if os.path.exists(report_dir):
            os.startfile(report_dir)
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Reports folder not found!")

    def _generate_full_report(self):
        """Generate complete security report with success popup"""
        import json
        from datetime import datetime

        try:
            # Create reports directory
            report_dir = r"C:\SecureForensic\Reports"
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f"security_report_{timestamp}.html")

            # Collect data
            external_logs = self._get_forensic_logs()
            internal_logs = self._get_audit_logs()
            blocked_files = self._get_blocked_files()

            # Generate HTML
            html = self._build_report_html(external_logs, internal_logs, blocked_files, timestamp)

            # Save report
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html)

            # Log action
            write_audit_log(
                self.user_name, self.user_role,
                "REPORT_GENERATED",
                "Admin Dashboard",
                details=f"Security report generated: {report_path}"
            )

            # ✅ SUCCESS POPUP
            QtWidgets.QMessageBox.information(
                self, "✅ Report Generated Successfully!",
                f"Report saved at:\n{report_path}\n\n"
                "You can open it using the 'Open Reports' button."
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to generate report:\n{str(e)}")
    def _get_forensic_logs(self):
        """Get logs from forensic.db (external/unauthorized activity)"""
        logs = []
        forensic_db = r"C:\ProgramData\SecureForensic\forensic.db"
        if os.path.exists(forensic_db):
            try:
                conn = sqlite3.connect(forensic_db)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username, action, method, file_name, file_path, time "
                    "FROM logs ORDER BY id DESC LIMIT 500"
                )
                logs = cur.fetchall()
                conn.close()
            except Exception as e:
                print(f"Forensic DB error: {e}")
        return logs

    def _get_audit_logs(self):
        """Get logs from users.db (internal/authorized)"""
        logs = []
        if os.path.exists(DB_PATH):
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, username, action, method, file_name, details, timestamp "
                    "FROM audit_logs ORDER BY id DESC LIMIT 500"
                )
                logs = cur.fetchall()
                conn.close()
            except Exception as e:
                print(f"Audit DB error: {e}")
        return logs
    
    def _build_report_html(self, external_logs, internal_logs, blocked_files, timestamp):
        """Build HTML report"""
        external_count = len(external_logs)
        internal_count = len(internal_logs)
        blocked_files_count = len(blocked_files)
        blocked_map = self._load_blocked_map()
        threats_blocked_count = len(blocked_map)
        threats_active_count = max(external_count - threats_blocked_count, 0)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Security Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f1f5f9; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                          color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 8px 0 0 0; opacity: 0.8; font-size: 14px; }}
                .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 10px; 
                             box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
                .stat-number {{ font-size: 32px; font-weight: bold; }}
                .stat-label {{ font-size: 13px; color: #64748b; margin-top: 4px; }}
                .stat-card.danger .stat-number {{ color: #dc2626; }}
                .stat-card.success .stat-number {{ color: #16a34a; }}
                .stat-card.warning .stat-number {{ color: #d97706; }}
                .stat-card.info .stat-number {{ color: #2563eb; }}
                .section {{ background: white; border-radius: 10px; padding: 20px; 
                           box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .section h2 {{ margin: 0 0 15px 0; font-size: 18px; color: #1e293b; 
                               border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
                th {{ background: #f1f5f9; padding: 10px; text-align: left; }}
                td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
                .danger {{ color: #dc2626; font-weight: bold; }}
                .success {{ color: #16a34a; font-weight: bold; }}
                .warning {{ color: #d97706; font-weight: bold; }}
                .footer {{ margin-top: 20px; text-align: center; color: #94a3b8; font-size: 12px; }}
                .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; 
                         font-size: 11px; font-weight: bold; }}
                .badge-danger {{ background: #fef2f2; color: #dc2626; }}
                .badge-success {{ background: #f0fdf4; color: #16a34a; }}
                .badge-warning {{ background: #fffbeb; color: #d97706; }}
                .quarantine-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); 
                                   gap: 10px; }}
                .quarantine-item {{ background: #f8fafc; padding: 12px; border-radius: 8px; 
                                   border-left: 3px solid #dc2626; }}
                .quarantine-item .file {{ font-weight: bold; }}
                .quarantine-item .reason {{ color: #dc2626; font-size: 12px; }}
                .quarantine-item .time {{ color: #94a3b8; font-size: 11px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🛡️ Secure Forensic Security Report</h1>
                    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>User: {self.user_name} | Role: {self.user_role}</p>
                </div>

                <div class="stats">
                    <div class="stat-card danger">
                        <div class="stat-number">{external_count}</div>
                        <div class="stat-label">🚨 External Threats Detected</div>
                    </div>
                    <div class="stat-card warning">
                        <div class="stat-number">{threats_blocked_count}</div>
                        <div class="stat-label">🔒 Threats Blocked</div>
                    </div>
                    <div class="stat-card danger">
                        <div class="stat-number">{threats_active_count}</div>
                        <div class="stat-label">⚠️ Threats Still Active</div>
                    </div>
                    <div class="stat-card success">
                        <div class="stat-number">{internal_count}</div>
                        <div class="stat-label">✅ Authorized Operations</div>
                    </div>
                    <div class="stat-card info">
                        <div class="stat-number">{external_count + internal_count}</div>
                        <div class="stat-label">📊 Total Activities</div>
                    </div>
                </div>

                <div class="section">
                    <h2>🔴 External Threats Detected</h2>
                    <table>
                        <thead>
                            <tr><th>ID</th><th>User</th><th>Action</th><th>Method</th><th>File</th><th>Time</th><th>Status</th></tr>
                        </thead>
                        <tbody>
        """

        for log in external_logs[:100]:
            row_id_str = str(log[0])
            block_info = blocked_map.get(row_id_str)
            if block_info:
                status_html = f'<span class="badge badge-success">🔒 {block_info.get("mode", "Blocked")}</span>'
            else:
                status_html = '<span class="badge badge-danger">⚠️ Active</span>'
            html += f"""
                            <tr>
                                <td>{log[0]}</td>
                                <td>{log[1]}</td>
                                <td><span class="badge badge-danger">{log[2]}</span></td>
                                <td>{log[3]}</td>
                                <td>{log[4]}</td>
                                <td>{log[6]}</td>
                                <td>{status_html}</td>
                            </tr>
            """


        if not external_logs:
            html += '<tr><td colspan="7" style="text-align:center;color:#94a3b8;">No external threats detected</td></tr>'

        html += """
                        </tbody>
                    </table>
                </div>

                <div class="section">
                    <h2>🟢 Authorized Operations</h2>
                    <table>
                        <thead>
                            <tr><th>ID</th><th>User</th><th>Action</th><th>Method</th><th>File</th><th>Time</th></tr>
                        </thead>
                        <tbody>
        """

        for log in internal_logs[:100]:
            html += f"""
                            <tr>
                                <td>{log[0]}</td>
                                <td>{log[1]}</td>
                                <td><span class="badge badge-success">{log[2]}</span></td>
                                <td>{log[3]}</td>
                                <td>{log[4]}</td>
                                <td>{log[6]}</td>
                            </tr>
            """

        if not internal_logs:
            html += '<tr><td colspan="6" style="text-align:center;color:#94a3b8;">No authorized operations recorded</td></tr>'

        html += """
                        </tbody>
                    </table>
                </div>

                <div class="section">
                    <h2>📦 Blocked / Quarantined Files</h2>
                    <div class="quarantine-list">
        """

        for file in blocked_files:
            html += f"""
                        <div class="quarantine-item">
                            <div class="file">📄 {file.get('original_name', 'Unknown')}</div>
                            <div class="reason">🚫 {file.get('reason', 'Unknown')}</div>
                            <div class="time">🕐 {file.get('timestamp', 'N/A')}</div>
                        </div>
            """

        if not blocked_files:
            html += '<p style="color:#94a3b8;grid-column:1/-1;text-align:center;">No files have been quarantined</p>'

        html += f"""
                    </div>
                </div>

                <div class="footer">
                    <p>🔒 Secure Forensic System | Report: {timestamp}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html
    # ═══════════════════════════════════════════════════════════
    # SMART BLOCK — detects threat type and takes correct action
    # ═══════════════════════════════════════════════════════════
    def _smart_block(self, method, action, row_id, username, file_path=""):
        """
        SIMPLE BLOCK — Sirf file ko quarantine mein move karo.
        USB, LAN, Email, Cloud, Browser KAHIN BHI BLOCK NAHI HOGE.
        Sirf suspicious file quarantine mein chali jaye gi.
        """
        import shutil
        import os

        result_msg = ""
        quarantine_dir = r"C:\Quarantine"

        # ── Quarantine folder create karo ──
        if not os.path.exists(quarantine_dir):
            try:
                os.makedirs(quarantine_dir)
            except Exception:
                pass

        # ── Sirf file quarantine karo ──
        quarantined_file = ""
        if file_path and os.path.exists(file_path):
            try:
                file_name = os.path.basename(file_path)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_name = f"{timestamp}_{file_name}"
                dest_path = os.path.join(quarantine_dir, dest_name)
                shutil.move(file_path, dest_path)
                quarantined_file = f"\n\n📦 File moved to quarantine:\n  {dest_path}"
                result_msg = f"✅ File Quarantined Successfully!\n\nFile: {file_name}\nMoved to: {dest_path}"
            except Exception as e:
                quarantined_file = f"\n\n⚠️ Could not quarantine file: {e}"
                result_msg = f"❌ Failed to quarantine file: {e}"
        else:
            result_msg = "⚠️ File no longer exists on system."

        # ── Mark THIS row as blocked ──
        self._mark_row_blocked(row_id, "FILE_QUARANTINE", "Simple")

        # ── Log & notify ───────────────────────────────────────
        write_audit_log(
            self.user_name, self.user_role, "FILE_QUARANTINED",
            "System Monitoring",
            details=f"Simple block: File quarantined from log ID={row_id} user={username} method={method} action={action}"
        )
        self.add_notification(
            f"File quarantined — {username} activity blocked",
            "Alert"
        )

        QtWidgets.QMessageBox.information(
            self, "✅ File Quarantined",
            f"{result_msg}\n\n"
            "USB, LAN, Email, Cloud, Browser ALL still working.\n"
            "Only the suspicious file has been isolated."
        )
        self.show_system_monitoring()

    def _quarantine_file(self, file_path, quarantine_dir):
        """Moves the offending file into quarantine if it still exists. Returns a status string."""
        import shutil
        if file_path and os.path.exists(file_path):
            try:
                file_name = os.path.basename(file_path)
                fts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = os.path.join(quarantine_dir, f"{fts}_{file_name}")
                shutil.move(file_path, dest_path)
                return f"\n\n📦 File moved to quarantine:\n  {dest_path}"
            except Exception as e:
                return f"\n\n⚠️ Could not quarantine file: {e}"
        return ""

    def _unblock_threat(self, row_id, threat_type):
        """
        Reverses a previously applied block for this specific log entry only.
        Re-enables the relevant channel (USB / LAN / nothing for browser, since
        browsers can simply be reopened) and removes the row's Blocked status.
        """
        import subprocess

        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Unblock",
            f"Reverse the block for this {threat_type} threat entry (ID {row_id})?\n\n"
            "This will re-enable the corresponding channel on this system.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            if threat_type == "USB":
                subprocess.run(
                    ['reg', 'add',
                     r'HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR',
                     '/v', 'Start', '/t', 'REG_DWORD', '/d', '3', '/f'],
                    capture_output=True, check=True
                )
                msg = "USB Mass Storage RE-ENABLED (registry restored to Start=3)."
            elif threat_type == "LAN":
                res = subprocess.run(
                    ['netsh', 'interface', 'show', 'interface'],
                    capture_output=True, text=True
                )
                enabled = []
                for line in res.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 4 and parts[0] == 'Disabled':
                        name = ' '.join(parts[3:])
                        if any(k in name for k in ['Ethernet', 'LAN', 'Local Area', 'Wi-Fi']):
                            subprocess.run(
                                ['netsh', 'interface', 'set', 'interface', name, 'admin=enabled'],
                                capture_output=True
                            )
                            enabled.append(name)
                msg = (f"LAN Network RE-ENABLED: {', '.join(enabled)}" if enabled
                       else "No disabled LAN adapters found to re-enable.")
            elif threat_type == "EMAIL":
                msg = "Email channel unblocked — Outlook/webmail can be reopened normally."
            elif threat_type == "CLOUD":
                msg = "Cloud channel unblocked — OneDrive/Dropbox/browser cloud access can resume."
            else:
                msg = "Browser channel unblocked — browsers can be reopened normally."
        except subprocess.CalledProcessError as e:
            QtWidgets.QMessageBox.critical(self, "Permission Required",
                f"Run as Administrator to unblock {threat_type}.\n\nError: {str(e)}")
            return
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "Error", "Required system command not found.")
            return

        self._unmark_row_blocked(row_id)
        write_audit_log(
            self.user_name, self.user_role, "THREAT_UNBLOCKED",
            "System Monitoring",
            details=f"Unblocked threat log ID={row_id} type={threat_type}"
        )
        self.add_notification(f"{threat_type} threat (ID {row_id}) unblocked by admin", "Info")
        QtWidgets.QMessageBox.information(self, "Unblocked", msg)
        self.show_system_monitoring()


    def _action_flush_db(self, db_path):
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Clear All Logs",
            "Permanently delete ALL forensic threat log records?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            if not os.path.exists(db_path):
                QtWidgets.QMessageBox.warning(self, "Not Found",
                    f"forensic.db not found at:\n{db_path}")
                return
            try:
                conn = sqlite3.connect(db_path)
                conn.execute("DELETE FROM logs")
                conn.commit()
                conn.close()
                write_audit_log(self.user_name, self.user_role, "FORENSIC_LOGS_CLEARED",
                                "System Monitoring", details="All records deleted")
                self.add_notification("Forensic log history cleared by admin", "Info")

                # Also clear quarantine folder
                quarantine_dir = r"C:\Quarantine"
                if os.path.exists(quarantine_dir):
                    try:
                        import shutil
                        shutil.rmtree(quarantine_dir)
                        os.makedirs(quarantine_dir)
                    except:
                        pass

                # Reset blocked-status tracking so old row IDs don't
                # incorrectly mark future, unrelated log entries as blocked
                self._save_blocked_map({})

                QtWidgets.QMessageBox.information(self, "Logs Cleared",
                    "All forensic threat records deleted successfully.\nQuarantine folder and block-status tracking also reset.")
                self.show_system_monitoring()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Database Error", f"Failed:\n{str(e)}")
    

    def _poll_shared_notifications(self):
        rows = poll_notifications(self.user_role, self.user_name, self.last_notif_id)
        if rows:
            self.last_notif_id = rows[-1][0]
            for _, message, category in rows:
                self.add_notification(message, category)

    def add_notification(self, message, status="Info"):
        ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {"text": message, "status": status, "time": ts}
        data  = []
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f:
                    data = json.load(f)
            except:
                pass
        data.insert(0, entry)
        with open(self.NOTIF_STORAGE, 'w') as f:
            json.dump(data[:50], f, indent=4)
        self.notif_count += 1
        self.notif_btn.setCounter(self.notif_count)
        if self.notif_panel.isVisible():
            self.notif_panel.populate(data)
            self.notif_count = 0
            self.notif_btn.setCounter(0)

    def _toggle_notif_panel(self):
        if self.notif_panel.isVisible():
            self.notif_panel.hide()
            return
        data = []
        if os.path.exists(self.NOTIF_STORAGE):
            try:
                with open(self.NOTIF_STORAGE, 'r') as f:
                    data = json.load(f)
            except:
                pass
        self.notif_panel.populate(data)
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

    # ═══════════════════════════════════════════════════════════
    # LOGOUT
    # ═══════════════════════════════════════════════════════════
    def do_logout(self):
        self._poll_timer.stop()
        write_audit_log(self.user_name, self.user_role,
                        "ADMIN_LOGOUT", details="Session ended")
        self.close()
        try:
            from app import MainAppWindow
            self.landing = MainAppWindow()
            self.landing.showMaximized()
        except Exception as e:
            print(f"Logout error: {e}")


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT — blocked for direct run
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    from PyQt5.QtWidgets import QMessageBox
    msg = QMessageBox()
    msg.setWindowTitle("Access Denied")
    msg.setIcon(QMessageBox.Critical)
    msg.setText(
        "This module cannot be run directly.\n\n"
        "Launch the application through:\n"
        "    python app.py"
    )
    msg.exec_()
    sys.exit(1)