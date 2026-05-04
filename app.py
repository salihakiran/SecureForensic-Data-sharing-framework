import sys
import sqlite3
import re # Regular expressions for validation
from PyQt5 import QtWidgets, QtCore, QtGui
import os

from utils.userUtils import send_verification_token, hash_text

# =======================================================
# CREATE DATABASE TABLES (11 TABLES) - Preserved
# =======================================================

def create_users_db():
    # Database connection create karna (agar file nahi hai to ban jayegi)
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Foreign Key support enable karna (SQLite mein lazmi hai)
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. users table [cite: 2, 3, 4]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        role TEXT, 
        verification_token TEXT,
        is_verified INTEGER DEFAULT 0,
        status INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 2. forensic_files table [cite: 5, 6, 7]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forensic_files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        original_hash TEXT NOT NULL,
        file_size TEXT,
        sender_name TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 3. manifest_details table [cite: 8, 9, 10]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS manifest_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        case_id TEXT,
        aes_key TEXT,
        investigator_name TEXT,
        creation_date DATETIME,
        FOREIGN KEY (file_id) REFERENCES forensic_files(file_id)
    )''')

    # 4. transfers table [cite: 11, 12, 13]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfers (
        transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        method TEXT, 
        sender_id INTEGER,
        receiver_id INTEGER,
        status TEXT,
        FOREIGN KEY (file_id) REFERENCES forensic_files(file_id)
    )''')

    # 5. receiver_logs table [cite: 14, 15, 16, 17]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS receiver_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        receiver_name TEXT,
        received_time DATETIME,
        decryption_status TEXT,
        FOREIGN KEY (file_id) REFERENCES forensic_files(file_id)
    )''')

    # 6. integrity_audit table [cite: 18, 19, 20]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS integrity_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        sender_hash TEXT,
        receiver_hash TEXT,
        integrity_status TEXT,
        audit_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (file_id) REFERENCES forensic_files(file_id)
    )''')

    # 7. chain_of_custody table [cite: 21, 22, 23]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chain_of_custody (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT,
        action TEXT, 
        performed_by TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        location_device TEXT
    )''')

    # 8. anomaly_alerts table [cite: 24, 25, 26]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS anomaly_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        description TEXT,
        severity TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 9. system_monitor_logs table [cite: 27, 28, 29]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_monitor_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_source TEXT,
        event_type TEXT,
        details TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 10. forensic_receipts table [cite: 30, 31, 32]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forensic_receipts (
        receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER,
        generated_by TEXT,
        hash_confirmed TEXT,
        receipt_path TEXT,
        FOREIGN KEY (file_id) REFERENCES forensic_files(file_id)
    )''')

    # 11. login_history table [cite: 33, 34]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS login_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        login_time DATETIME,
        logout_time DATETIME,
        status TEXT
    )''')

    conn.commit()
    conn.close()
    print("Database aur saare 11 tables kamyabi se ban gaye hain!")

if __name__ == "__main__":
    create_users_db()
# =======================================================
# VALIDATION HELPER FUNCTIONS (Preserved)
# =======================================================

def is_valid_name(name):
    """Allows only letters (uppercase/lowercase) and spaces, minimum 3 chars."""
    if re.fullmatch(r"^[a-zA-Z\s]{3,}$", name.strip()):
        return True
    return False

def is_valid_email(email):
    """Basic email format check, allows digits and letters in username (e.g., example123@gmail.com)."""
    if re.fullmatch(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return True
    return False

def check_password_strength(password):
    """Checks password complexity and returns strength status, color, and validity based on user's request."""
    score = 0
    
    # 1. Length (Minimum 8 characters)
    is_long_enough = len(password) >= 8
    if is_long_enough: score += 1
    
    # 2. Letters (Uppercase or Lowercase)
    has_letters = re.search(r"[a-zA-Z]", password)
    if has_letters: score += 1
    
    # 3. Digits
    has_digits = re.search(r"\d", password)
    if has_digits: score += 1
    
    # 4. Symbols
    has_symbols = re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    if has_symbols: score += 1

    # Check for Strong Password (Must meet all 4 criteria)
    if score == 4 and is_long_enough:
        return "Strong Password", "green", True
    else:
        return "Weak password (letters, digits, symbols)", "red", False

# =======================================================
# STYLING AND HELPER FUNCTIONS
# =======================================================

# --- THEME COLORS ---
BLUE_PRIMARY = "#0284c7"   # medium sky blue (not too light)
BLUE_DARK = "#0369a1"      # hover / dark shade
BLUE_LIGHT_BG = "#eff6ff" # Very light blue/white background (Used for Welcome/Signup/Signin BG)
NAV_BAR_COLOR = "#0284c7"

# --- COMMON STYLES ---
INPUT_STYLE = """
    QLineEdit, QComboBox {
        background-color: #f3f4f6;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        font-size: 16px; 
        padding: 10px;
        min-height: 45px; 
        max-height: 45px;
        color: #1f2937;
    }
    
    QLineEdit:focus, QComboBox:focus {
        border: 2px solid #60a5fa;
        background-color: white;
    }

    /* --- Dropdown Box Setup --- */
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 35px; 
        border: none;
    }

    /* Arrow ko bilkul center aur dark karne ke liye */
    QComboBox::down-arrow {
        image: none; 
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-top: 8px solid #000000; /* Ekdum Dark Black Arrow */
        
        /* Yeh do lines arrow ko kone se nikal kar sahi jagah layengi */
        position: relative;
        right: 10px; 
        top: 0px;
    }

    /* Hover effect */
    QComboBox::down-arrow:hover {
        border-top: 8px solid #3b82f6; /* Blue color on hover */
    }

    /* Dropdown list (Menu) ki styling */
    QComboBox QAbstractItemView {
        border: 1px solid #d1d5db;
        selection-background-color: #3b82f6;
        selection-color: white;
        background-color: white;
        outline: none;
        padding: 5px;
    }
"""
BUTTON_PRIMARY_STYLE = f"""
    QPushButton {{
        background-color: {BLUE_PRIMARY};
        color: white;
        font-size: 20px; 
        padding: 15px;
        border-radius: 12px;
        margin-top: 20px; 
        min-height: 50px; 
    }}
    QPushButton:hover {{
        background-color: {BLUE_DARK};
    }}
"""

LINK_STYLE = "font-size: 16px; color: black; text-decoration: none;" 
ERROR_LABEL_STYLE = "color: #ef4444; font-size: 16px; font-weight: bold; min-height: 25px;" 

# --- POPUP (Retained) ---
class CustomPopup(QtWidgets.QDialog):
    def __init__(self, message, title="Notification"):
        # The parent is passed as None to make it a standalone window
        super().__init__(None, QtCore.Qt.Window) 
        self.setWindowTitle(title)
        self.setFixedSize(300, 150)
        self.setStyleSheet(f"""
            background-color: {BLUE_LIGHT_BG};
            border: 2px solid {BLUE_PRIMARY}; 
            border-radius: 10px;
        """)

        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(message)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {BLUE_PRIMARY}; font-size: 14px; font-weight: bold;")
        layout.addWidget(label)

        btn = QtWidgets.QPushButton("OK")
        btn.setFixedSize(100, 30)
        btn.setStyleSheet(BUTTON_PRIMARY_STYLE.replace("font-size: 20px", "font-size: 14px").replace("min-height: 50px", "min-height: 30px").replace("margin-top: 20px", "margin-top: 5px"))
        layout.addWidget(btn, alignment=QtCore.Qt.AlignCenter)
        btn.clicked.connect(self.accept)

        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

def show_popup(msg):
    CustomPopup(msg).exec_()


# --- UI Helper for Form Fields ---
def create_field_layout(label_text, widget):
    h_layout = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(label_text)
    label.setStyleSheet("color: black; font-size: 16px; min-width: 100px;") 
    h_layout.addWidget(label)
    h_layout.addWidget(widget) 
    return h_layout

# =======================================================
# WELCOME PAGE (Landing Page) - MODIFIED FOR STACK
# =======================================================
class WelcomePage(QtWidgets.QWidget):
    switch_page = QtCore.pyqtSignal(int)
    theme_changed = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark_mode = False 
        
        # Main Layout
        self.main_container = QtWidgets.QVBoxLayout(self)
        self.main_container.setSpacing(0)
        self.main_container.setContentsMargins(0, 0, 0, 0)

        # ================= 1. NAVIGATION BAR =================
        self.navBar = QtWidgets.QFrame()
        self.navBar.setMinimumHeight(70) 
        self.navBar.setStyleSheet(f"background-color: {NAV_BAR_COLOR};")
        self.navLayout = QtWidgets.QHBoxLayout(self.navBar)
        self.navLayout.setContentsMargins(25, 0, 25, 0)

        self.titleLabel = QtWidgets.QLabel("SDTF")
        self.titleLabel.setStyleSheet("color: white; font-weight: bold; font-size: 28px; margin-right: 20px;")
        self.navLayout.addWidget(self.titleLabel)

        self.btn_home = self.create_nav_btn("Home")
        self.btn_sec = self.create_nav_btn("Security Architecture")
        self.btn_for = self.create_nav_btn("Forensic Audit")
        self.btn_how = self.create_nav_btn("How It Works")
        self.btn_sup = self.create_nav_btn("Support & Report")

        for btn in [self.btn_home, self.btn_sec, self.btn_for, self.btn_how, self.btn_sup]:
            self.navLayout.addWidget(btn)

        self.navLayout.addStretch() 

        self.themeToggle = QtWidgets.QPushButton("🌙")
        self.themeToggle.setFixedSize(45, 42)
        self.themeToggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.themeToggle.setStyleSheet("QPushButton { background: rgba(255,255,255,0.1); border-radius: 6px; font-size: 18px; color: white; }")
        self.themeToggle.clicked.connect(self.toggle_theme)
        self.navLayout.addWidget(self.themeToggle)

        self.signinButton = QtWidgets.QPushButton("Sign in")
        self.signupButton = QtWidgets.QPushButton("Sign up")
        self.signinButton.setFixedSize(110, 42)
        self.signupButton.setFixedSize(110, 42)
        self.signinButton.setStyleSheet("background: white; color: #0284c7 ; border: 2px solid white; border-radius: 6px; font-weight: bold;font-size: 18px;")
        self.signupButton.setStyleSheet("background: white; color: #0284c7; border-radius: 6px; font-weight: bold;font-size: 18px;")
        
        self.navLayout.addWidget(self.signinButton)
        self.navLayout.addWidget(self.signupButton)
        self.main_container.addWidget(self.navBar)

        # ================= 2. STACKED CONTENT AREA =================
        self.content_stack = QtWidgets.QStackedWidget()
        
        # Home Page (Index 0)
        self.home_page = self.create_home_page()
        self.content_stack.addWidget(self.home_page)

        # Detail Page (Index 1)
        self.details_page = QtWidgets.QWidget()
        self.details_layout = QtWidgets.QHBoxLayout(self.details_page)
        self.details_layout.setContentsMargins(80, 40, 80, 40)
        self.details_layout.setSpacing(50)
        self.content_stack.addWidget(self.details_page)

        self.main_container.addWidget(self.content_stack)
        self.apply_theme_styles()

        # ================= 3. CONNECTIONS WITH DETAILED CONTENT =================
        self.btn_home.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))

        # 1. Security Architecture (FIXED)
        self.btn_sec.clicked.connect(lambda: self.update_details_page("Security Architecture", 
            "<h3>Core Framework Security</h3>"
            "<b>• End-to-End Encryption:</b> High-level local encryption ensures that data remains inaccessible to unauthorized users. All files are encrypted at the source before transmission.<br><br>"
            "<b>• Advanced Cryptographic Algorithms:</b> The system utilizes military-grade AES-256 and Fernet encryption standards to guarantee confidentiality and robust protection against brute-force attacks.<br><br>"
            "<b>• Data Integrity & Hashing:</b> Every data packet is validated using SHA-256 hash algorithms. This ensures that the file received is bit-for-bit identical to the original file sent.<br><br>"
            "<b>• Secure Key Exchange:</b> Keys are shared through secure channels, preventing 'Man-in-the-Middle' attacks during the decryption process.<br><br>"
            "<b>• Zero Knowledge Architecture:</b> The framework is designed so that even the service provider cannot access your raw data without the specific user-generated keys.", 
            "images/security.jpg"))

        # =======================================================
# 2. Forensic Audit Button Connection
# =======================================================
        self.btn_for.clicked.connect(lambda: self.update_details_page("Forensic Audit", 
    "<h3>Digital Forensic & Accountability</h3>"
    "<b>• Immutable Activity Logs:</b> Every action within the framework is recorded in tamper-proof logs. These logs cannot be modified or deleted, ensuring a 100% reliable audit trail.<br><br>"
    "<b>• Granular Tracking:</b> The system captures deep metadata including Unique User IDs, Machine MAC Addresses, precise Timestamps, and specific IP addresses used during the session.<br><br>"
    "<b>• Forensic Reporting Module:</b> Generates automated, comprehensive reports for administrators, highlighting any unusual patterns or unauthorized access attempts.<br><br>"
    "<b>• Non-Repudiation:</b> Due to the forensic nature of the logs, users cannot deny their actions, which is crucial for legal and corporate accountability.<br><br>"
    "<b>• Integrity Monitoring:</b> Constant background surveillance of system files to detect any post-transfer metadata manipulation.",
    "images/forensic.jpg"))
    
        # =======================================================
        # 3. How It Works Button Connection
        # =======================================================
        self.btn_how.clicked.connect(lambda: self.update_details_page("How It Works", 
    "<h3>Operational Workflow & Data Journey</h3>"
    "<b>Step 1: Secure Authentication:</b> Users must first authenticate through a multi-factor portal. The system verifies identity and assigns a secure session token.<br><br>"
    "<b>Step 2: Local Encryption & Hashing:</b> Before the file leaves your machine, the framework performs a high-speed AES-256 encryption and generates a SHA-256 integrity hash.<br><br>"
    "<b>Step 3: Transfer Mode Selection:</b> Depending on network availability, the user can choose <b>Online P2P</b> (via secure sockets) or <b>Offline Mode</b> (USB/LAN) for data sharing.<br><br>"
    "<b>Step 4: Secure Key Delivery:</b> The unique decryption key is shared only with the authorized receiver through an out-of-band secure channel.<br><br>"
    "<b>Step 5: Verification & Decryption:</b> The receiver's system validates the file hash. If the hash matches perfectly, the file is decrypted and restored to its original format.",
    "images/process.jpg"))
    
        # 4. Support & Report
        # =======================================================
# 4. Support & Report Button Connection
# =======================================================
        self.btn_sup.clicked.connect(lambda: self.update_details_page("Support & Report", 
    "<h3>AI Threat Detection & System Support</h3>"
    "<b>• AI-Driven Anomaly Detection:</b> The framework utilizes an integrated AI module that constantly monitors for suspicious activities, such as multiple failed login attempts or unusual data access patterns.<br><br>"
    "<b>• Real-time Incident Alerts:</b> In case of a detected breach or unauthorized file manipulation, instant notifications are dispatched to both the end-user and the system administrator for immediate action.<br><br>"
    "<b>• Administrative Control Panel:</b> A dedicated suite for system administrators to manage user permissions, oversee forensic logs, and handle system-wide security configurations efficiently.<br><br>"
    "<b>• Secure Incident Reporting:</b> A specialized module where users can report system bugs, security concerns, or suspicious file requests directly to our forensic technical team.<br><br>"
    "<b>• Automated Data Recovery:</b> Support for system-wide backups and recovery protocols to ensure that no data is lost during hardware failures or sudden system crashes.<br><br>"
    "<b>• 24/7 Technical Assistance:</b> Integrated support ticketing system that automatically prioritizes security-related queries for rapid forensic investigation.", 
    "images/support.jpg"))

        self.signupButton.clicked.connect(lambda: self.switch_page.emit(2))
        self.signinButton.clicked.connect(lambda: self.switch_page.emit(1))

    # create_home_page aur baqi functions (as it is raheinge pehle ki tarah)

    def update_details_page(self, title, info, image_path):
        # 1. Purane widgets clear karein
        while self.details_layout.count():
            child = self.details_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Layout margins (Screen ke charo taraf thori jagah)
        self.details_layout.setContentsMargins(50, 30, 50, 30)
        self.details_layout.setSpacing(40)

        text_color = "white" if self.is_dark_mode else BLUE_PRIMARY
        card_bg = "#1e293b" if self.is_dark_mode else "white"
        sub_text_color = "#94a3b8" if self.is_dark_mode else "#334155"

        # --- LEFT SIDE: Text Box (Fixed - No Scroll) ---
        left_container = QtWidgets.QWidget()
        left_v = QtWidgets.QVBoxLayout(left_container)
        left_v.setContentsMargins(0, 0, 0, 0)
        
        h_label = QtWidgets.QLabel(title)
        h_label.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {text_color}; margin-bottom: 5px;")
        
        info_card = QtWidgets.QLabel(info)
        info_card.setTextFormat(QtCore.Qt.RichText)
        info_card.setWordWrap(True)
        # Font size 17px rakha hai taake fit aaye, aur padding thori kam ki hai
        info_card.setStyleSheet(f"""
            font-size: 17px; 
            color: {sub_text_color}; 
            background: {card_bg}; 
            padding: 25px; 
            border-radius: 20px; 
            border: 2px solid #cbd5e1;
            line-height: 140%;
        """)
        
        left_v.addWidget(h_label)
        left_v.addWidget(info_card)
        left_v.addStretch() # Content ko upar push karega

        # --- RIGHT SIDE: Balanced Image ---
        right_img = QtWidgets.QLabel()
        pix = QtGui.QPixmap(image_path)
        
        if not pix.isNull():
            # Image size ko moderate rakha hai (Max height 550) taake neche se cut na ho
            scaled_pix = pix.scaled(500, 550, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            right_img.setPixmap(scaled_pix)
        else:
            right_img.setText("📷 Picture Space")
            right_img.setStyleSheet(f"background: {card_bg}; border-radius: 20px; border: 2px dashed #cbd5e1;")
            right_img.setFixedSize(400, 500)
        
        right_img.setAlignment(QtCore.Qt.AlignCenter)

        # Layout 55% Text aur 45% Image ka split hai
        self.details_layout.addWidget(left_container, 55)
        self.details_layout.addWidget(right_img, 45)
        
        self.content_stack.setCurrentIndex(1)
    def create_nav_btn(self, text):
        btn = QtWidgets.QPushButton(text)
        btn.setFixedHeight(45)
        btn.setStyleSheet("QPushButton { background-color: transparent; color: white; border: none; font-size: 15px; font-weight: bold; padding: 0 10px; } QPushButton:hover { color: #bae6fd; }")
        return btn

    def apply_theme_styles(self):
        bg = "#121212" if self.is_dark_mode else BLUE_LIGHT_BG
        self.setStyleSheet(f"background-color: {bg};")
        nav_bg = "#0f172a" if self.is_dark_mode else NAV_BAR_COLOR
        self.navBar.setStyleSheet(f"background-color: {nav_bg};")

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.theme_changed.emit(self.is_dark_mode)
        self.themeToggle.setText("☀️" if self.is_dark_mode else "🌙")
        self.apply_theme_styles()
        idx = self.content_stack.currentIndex()
        self.content_stack.removeWidget(self.home_page)
        self.home_page = self.create_home_page()
        self.content_stack.insertWidget(0, self.home_page)
        self.content_stack.setCurrentIndex(idx)

    def create_home_page(self):
        page = QtWidgets.QWidget()
        main_v = QtWidgets.QVBoxLayout(page)
        main_v.setContentsMargins(0, 0, 0, 0)
        
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        content_widget = QtWidgets.QWidget()
        content_widget.setStyleSheet("background: transparent;")
        scroll.setWidget(content_widget)
        scroll_layout = QtWidgets.QVBoxLayout(content_widget)

        # --- COLORS & STYLES ---
        text_color = "white" if self.is_dark_mode else "#1e293b" # BLUE_PRIMARY replaced with hex for safety
        sub_text = "#94a3b8" if self.is_dark_mode else "#4b5563"
        card_bg = "#1e293b" if self.is_dark_mode else "white"
        card_text = "white" if self.is_dark_mode else "#1e293b"

        # --- HERO SECTION (TOP PART) ---
        hero = QtWidgets.QFrame()
        h_lay = QtWidgets.QHBoxLayout(hero)
        h_lay.setContentsMargins(80, 60, 80, 60)
        
        t_box = QtWidgets.QVBoxLayout()
        
        # Main Title
        title = QtWidgets.QLabel("Secure Data Sharing\nFramework")
        title.setStyleSheet(f"font-size: 50px; font-weight: bold; color: #0284c7; line-height: 110%;")
        
        # Your 5-Line Symmetrical Intro
        fyp_text = (
            "A reliable and robust offline and online platform<br>"
            "designed specifically to facilitate secure data exchange<br>"
            "using high level military grade AES-256 encryption standards<br>"
            "ensuring sensitive information remains fully protected<br>"
            "integrated with automated forensic logs and AI-checks."
        )
        desc = QtWidgets.QLabel(fyp_text)
        desc.setTextFormat(QtCore.Qt.RichText)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 18px; color: {sub_text}; line-height: 170%; margin-top: 15px;")
        
        t_box.addWidget(title)
        t_box.addWidget(desc)
        t_box.addStretch()

        # Hero Image
        img = QtWidgets.QLabel()
        pix = QtGui.QPixmap("images/landing.jpg")
        if not pix.isNull():
            img.setPixmap(pix.scaled(500, 400, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            img.setText("📷") # Placeholder if image missing
            img.setStyleSheet("font-size: 100px;")
        
        h_lay.addLayout(t_box, 60)
        h_lay.addWidget(img, 40)
        scroll_layout.addWidget(hero)

        # --- FEATURES GRID (BOTTOM PART) ---
        grid_widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_widget)
        grid.setContentsMargins(80, 20, 80, 40)
        grid.setSpacing(30)
        
        # --- 6 Features: Technical & Detailed Content ---
        features = [
            ("End-to-End Encryption", "🔒", 
             "Implementing military-grade AES-256 standards to encrypt data at the source. This ensures that sensitive information remains completely confidential and inaccessible to any unauthorized third parties during transit."),
            
            ("Tamper-Proof Logs", "📝", 
             "Maintaining immutable forensic audit trails that record every system interaction. These logs are cryptographically sealed to prevent deletion, ensuring absolute accountability and transparency for security audits."),
            
            ("Uninterrupted Transfer", "🚀", 
             "Optimized for high-performance data exchange using multi-threaded protocols. Our system ensures seamless and reliable file delivery for large datasets, even across unstable or low-bandwidth network environments."),
            
            ("No Central Server", "🌐", 
             "Built on a decentralized Peer-to-Peer (P2P) architecture. By removing the central server, the framework eliminates single points of failure and prevents man-in-the-middle attacks, ensuring direct user-to-user security."),
            
            ("AI Threat Alerts", "🤖", 
             "Integrating advanced AI algorithms to monitor system behavior in real-time. The engine automatically detects login anomalies or suspicious data patterns and triggers instant alerts to mitigate potential security breaches."),
            
            ("File Integrity Check", "✔️", 
             "Utilizing SHA-256 cryptographic hashing to verify file consistency. The system performs a bit-by-bit comparison post-transfer to guarantee that the delivered data is an exact, uncorrupted match of the original file.")
        ]
        
        for i, (f_t, icon, f_d) in enumerate(features):
            card = QtWidgets.QFrame()
            card.setFixedSize(350, 190) # Balanced size for detailed text
            card.setStyleSheet(f"background: {card_bg}; border-radius: 15px; border: 1px solid #cbd5e1;")
            
            v = QtWidgets.QVBoxLayout(card)
            v.setContentsMargins(20, 20, 20, 20)
            
            h_t = QtWidgets.QHBoxLayout()
            il = QtWidgets.QLabel(icon); il.setStyleSheet("font-size: 28px; border:none;")
            tl = QtWidgets.QLabel(f"<b>{f_t}</b>"); tl.setStyleSheet(f"font-size: 16px; color: {card_text}; border:none;")
            h_t.addWidget(il); h_t.addWidget(tl); h_t.addStretch()
            
            dl = QtWidgets.QLabel(f_d)
            dl.setWordWrap(True)
            dl.setStyleSheet(f"font-size: 13px; color: {sub_text}; border:none; line-height: 140%;")
            
            v.addLayout(h_t)
            v.addSpacing(10)
            v.addWidget(dl)
            v.addStretch()
            grid.addWidget(card, i // 3, i % 3)
            
        scroll_layout.addWidget(grid_widget)
        main_v.addWidget(scroll)
        return page
# =======================================================
# SIGNUP PAGE — MODIFIED FOR STACK
# =======================================================
class SignupPage(QtWidgets.QWidget):
    switch_page = QtCore.pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Removed self.showMaximized() - handled by MainAppWindow

        main = QtWidgets.QHBoxLayout(self)
        main.addStretch()
        
        # --- White Card Container (Two-Column) ---
        whiteCard = QtWidgets.QFrame()
        whiteCard.setFixedSize(950, 650) 
        whiteCard.setStyleSheet("background-color: white; border-radius: 20px;")
        
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        whiteCard.setGraphicsEffect(shadow)
        
        cardHLayout = QtWidgets.QHBoxLayout(whiteCard)
        cardHLayout.setContentsMargins(20, 20, 20, 20) 
        cardHLayout.setSpacing(0)
        
        # --- LEFT SIDE (Blue/Welcome Area) ---
        blueSide = QtWidgets.QFrame()
        blueSide.setFixedWidth(350) 
        blueSide.setStyleSheet(f"background-color: {BLUE_PRIMARY}; border-radius: 15px;")
        
        blueVLayout = QtWidgets.QVBoxLayout(blueSide)
        blueVLayout.setContentsMargins(25, 50, 25, 50)
        
        welcomeLabel = QtWidgets.QLabel("WELCOME")
        welcomeLabel.setStyleSheet("color: white; font-size: 40px; font-weight: bold;")
        welcomeLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        headlineLabel = QtWidgets.QLabel("CREATE YOUR ACCOUNT")
        headlineLabel.setStyleSheet("color: white; font-size: 24px;")
        headlineLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        infoLabel = QtWidgets.QLabel("Create your secure account to encrypt, transfer, and manage data with confidence.")
        infoLabel.setStyleSheet("color: #bfdbfe; font-size: 14px;")
        infoLabel.setWordWrap(True)
        infoLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        blueVLayout.addWidget(welcomeLabel)
        blueVLayout.addSpacing(15)
        blueVLayout.addWidget(headlineLabel)
        blueVLayout.addSpacing(15)
        blueVLayout.addWidget(infoLabel)
        blueVLayout.addStretch()
        
        cardHLayout.addWidget(blueSide)
        
        # --- RIGHT SIDE (Form Area) ---
        formSide = QtWidgets.QFrame()
        formVLayout = QtWidgets.QVBoxLayout(formSide)
        formVLayout.setSpacing(15) 
        formVLayout.setAlignment(QtCore.Qt.AlignCenter)

        formTitle = QtWidgets.QLabel("Sign up")
        formTitle.setStyleSheet("color: black; font-size: 45px; font-weight: bold; margin-bottom: 10px;")
        formTitle.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(formTitle)

        # Fields (Name, Email, Password, Role)
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Name")
        self.name.setStyleSheet(INPUT_STYLE)
        self.name.textChanged.connect(self.validate_live) 

        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Email (e.g., example123@domain.com)")
        self.email.setStyleSheet(INPUT_STYLE)
        self.email.textChanged.connect(self.validate_live) 

        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setStyleSheet(INPUT_STYLE)
        self.password.textChanged.connect(self.validate_live) 
        
        # Password strength label 
        self.password_strength_label = QtWidgets.QLabel("")
        self.password_strength_label.setAlignment(QtCore.Qt.AlignLeft)
        self.password_strength_label.setFixedHeight(20) 
        
        self.role = QtWidgets.QComboBox()
        self.role.setStyleSheet(INPUT_STYLE) 
        
        # Items add karna aur placeholder set karna
        self.role.addItem("Select Your Role")
        self.role.addItems(["Sender", "Receiver", "Admin"])
        
        # Placeholder (Index 0) ko disable karna aur uska font sahi rakhna
        self.role.setItemData(0, 0, QtCore.Qt.UserRole - 1) 
        
        self.role.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.role.currentIndexChanged.connect(self.validate_live)
        # Adding fields
        formVLayout.addLayout(create_field_layout("Name:", self.name))
        formVLayout.addLayout(create_field_layout("Email:", self.email))
        
        formVLayout.addLayout(create_field_layout("Password:", self.password))
        
        self.password_strength_label.setStyleSheet(f"font-size: 15px; font-weight: bold; padding-left: 110px; margin-top: -5px;")
        formVLayout.addWidget(self.password_strength_label, alignment=QtCore.Qt.AlignLeft)
        
        formVLayout.addSpacing(-5) 
        
        formVLayout.addLayout(create_field_layout("Role:", self.role))
        
        formVLayout.addSpacing(10) 
        
        # RED FLAG SPACE (Error Label)
        self.errorLabel = QtWidgets.QLabel("")
        self.errorLabel.setStyleSheet(ERROR_LABEL_STYLE)
        self.errorLabel.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(self.errorLabel)
        
        formVLayout.addSpacing(-10) 
        
        self.create_btn = QtWidgets.QPushButton("Create Account")
        self.create_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        formVLayout.addWidget(self.create_btn)
        
        formVLayout.addSpacing(25) 

        # Signin Link (Connects to Signin Page - Index 1)
        loginLink = QtWidgets.QLabel("Already have an account? <a href=\"#\">Sign in</a>")
        loginLink.linkActivated.connect(lambda: self.switch_page.emit(1)) 
        loginLink.setAlignment(QtCore.Qt.AlignCenter)
        loginLink.setStyleSheet(LINK_STYLE)
        formVLayout.addWidget(loginLink)

        formVLayout.addStretch()
        
        cardHLayout.addWidget(formSide)
        
        main.addWidget(whiteCard)
        main.addStretch()

        self.create_btn.clicked.connect(self.create_account)
        
    def validate_live(self):
        """Performs live validation and updates error/strength labels."""
        self.errorLabel.setText("") 
        self.create_btn.setEnabled(True) 
        
        name = self.name.text().strip()
        email = self.email.text().strip()
        password = self.password.text()
        role = self.role.currentText()
        
        is_name_valid = is_valid_name(name)
        is_email_valid = is_valid_email(email)
        is_password_strong = False
        
        # 1. Name Validation
        if name and (not is_name_valid):
            self.errorLabel.setText("Invalid Name: Only letters and spaces allowed (min 3 chars).")
            self.create_btn.setEnabled(False)
            return

        # 2. Email Validation 
        if email and (not is_valid_email(email)):
            self.errorLabel.setText("Invalid Email Format. (e.g., example123@domain.com)")
            self.create_btn.setEnabled(False)
            return

        # 3. Password Validation (Strength Check)
        if password:
            strength_text, color, is_password_strong = check_password_strength(password)
            self.password_strength_label.setText(f"{strength_text}")
            self.password_strength_label.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold; padding-left: 110px; margin-top: -5px;")
            
            if not is_password_strong: 
                self.create_btn.setEnabled(False)
                return 
            
        else:
            self.password_strength_label.setText("") 
            
        
        # 4. Role Validation 
        all_key_fields_valid = is_name_valid and is_email_valid and is_password_strong

        if all_key_fields_valid and (role == "Select Your Role"):
            self.errorLabel.setText("Please select valid Role.") 
            self.create_btn.setEnabled(False)
            return 
        
        if is_name_valid and is_valid_email(email) and is_password_strong and role != "Select Your Role":
             self.create_btn.setEnabled(True)
        else:
             if name or email or password or role != "Select Your Role":
                 self.create_btn.setEnabled(False)


    def create_account(self):
        """Final validation and database insertion on button click."""
        name = self.name.text().strip()
        email = self.email.text().strip()
        password = hash_text(self.password.text())
        role = self.role.currentText()

        self.validate_live() 

        if not name or not email or not password or role == "Select Your Role":
            self.errorLabel.setText("Please fill all required fields correctly.")
            return

        if not self.create_btn.isEnabled():
            return
            
        conn = sqlite3.connect("users.db")
        c = conn.cursor()

        try:
            
            user = c.execute("SELECT email FROM users WHERE email = ? ", (email,)).fetchone()
            if user:
                show_popup("You can sign in or reset your password if this email is already in use.")
            else: 
                message, _ok = send_verification_token(email)
                
                if not _ok:
                    show_popup(message)
                
                else:
                    c.execute("INSERT INTO users (name, email, password, role,) VALUES (?, ?, ?, ?)",
                              (name, email, password, role))
                    conn.commit()
                    conn.close()
                    show_popup(message)
                    # Switch to Signin Page (Index 1)
                    self.switch_page.emit(1) 

        except sqlite3.IntegrityError:
            conn.close()
            self.errorLabel.setText("Error: Email already exists!")


    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        pixmap = QtGui.QPixmap("signup.jpg") 
        if not pixmap.isNull():
            painter.drawPixmap(self.rect(), pixmap)


# =======================================================
# SIGNIN PAGE — MODIFIED FOR STACK
# =======================================================
class SigninPage(QtWidgets.QWidget):
    switch_page = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;") 

        main = QtWidgets.QHBoxLayout(self)
        main.addStretch()
        
        whiteCard = QtWidgets.QFrame()
        whiteCard.setFixedSize(950, 650) 
        whiteCard.setStyleSheet("background-color: white; border-radius: 20px;")
        
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        whiteCard.setGraphicsEffect(shadow)
        
        cardHLayout = QtWidgets.QHBoxLayout(whiteCard)
        cardHLayout.setContentsMargins(20, 20, 20, 20) 
        cardHLayout.setSpacing(0)
        
        # --- LEFT SIDE (Blue Area) ---
        blueSide = QtWidgets.QFrame()
        blueSide.setFixedWidth(350) 
        blueSide.setStyleSheet(f"background-color: {BLUE_PRIMARY}; border-radius: 15px;")
        
        blueVLayout = QtWidgets.QVBoxLayout(blueSide)
        blueVLayout.setContentsMargins(25, 50, 25, 50)
        
        welcomeLabel = QtWidgets.QLabel("DATA SECURITY")
        welcomeLabel.setStyleSheet("color: white; font-size: 36px; font-weight: bold; background: transparent;") 
        welcomeLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        headlineLabel = QtWidgets.QLabel("ACCESS YOUR ACCOUNT")
        headlineLabel.setStyleSheet("color: white; font-size: 24px; background: transparent;")
        headlineLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        blueVLayout.addWidget(welcomeLabel)
        blueVLayout.addSpacing(15)
        blueVLayout.addWidget(headlineLabel)
        blueVLayout.addStretch()
        
        cardHLayout.addWidget(blueSide)
        
        # --- RIGHT SIDE (Form Area) ---
        formSide = QtWidgets.QFrame()
        formVLayout = QtWidgets.QVBoxLayout(formSide)
        formVLayout.setSpacing(15) 
        formVLayout.setAlignment(QtCore.Qt.AlignCenter)
        
        formTitle = QtWidgets.QLabel("Sign in")
        formTitle.setStyleSheet("color: black; font-size: 45px; font-weight: bold; margin-bottom: 20px; background: transparent;")
        formTitle.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(formTitle)

        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Email")
        self.email.setStyleSheet(INPUT_STYLE)
        self.email.textChanged.connect(self.validate_live) 

        # --- Password Field ---
        

        
        # --- Password Field Setup ---
        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        
        # Padding right barha dein taake icon ke liye jagah ban jaye
        self.password.setStyleSheet(INPUT_STYLE + "padding-right: 40px;") 

        # Eye icon logic
        self.toggle_action = self.password.addAction(
            QtGui.QIcon("eye_icon.png"), 
            QtWidgets.QLineEdit.TrailingPosition
        )
        
        # --- ICON BARA KARNE KA SAHI TAREEKA ---
        # Hum stylesheet ke zariye icon ki width aur height set karenge
        self.password.setStyleSheet(self.password.styleSheet() + """
            QLineEdit {
                qproperty-iconSize: 40x 40px;
            }
        """)
        
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.toggle_password_visibility)
        

        formVLayout.addSpacing(30) 
        formVLayout.addLayout(create_field_layout("Email:", self.email))
        formVLayout.addSpacing(10)
        formVLayout.addLayout(create_field_layout("Password:", self.password))
        
        formVLayout.addSpacing(10)
        self.errorLabel = QtWidgets.QLabel("")
        self.errorLabel.setStyleSheet(ERROR_LABEL_STYLE)
        self.errorLabel.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(self.errorLabel)
        
        self.login_btn = QtWidgets.QPushButton("Sign In")
        self.login_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        formVLayout.addWidget(self.login_btn)
        
        formVLayout.addSpacing(20) 
        
        signupLink = QtWidgets.QLabel("Don't have an account? <a href=\"#\">Sign up</a>")
        signupLink.linkActivated.connect(lambda: self.switch_page.emit(2)) 
        signupLink.setAlignment(QtCore.Qt.AlignCenter)
        signupLink.setStyleSheet(LINK_STYLE)
        formVLayout.addWidget(signupLink)

        formVLayout.addStretch()
        cardHLayout.addWidget(formSide)
        main.addWidget(whiteCard)
        main.addStretch()

        self.login_btn.clicked.connect(self.verify_login)

    # ======= BACKGROUND IMAGE LOGIC =======
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        pixmap = QtGui.QPixmap("signin.jpg") # Signin pic folder mein honi chahiye
        if not pixmap.isNull():
            painter.drawPixmap(self.rect(), pixmap)

    def validate_live(self):
        self.errorLabel.setText("") 
        self.login_btn.setEnabled(True)
        email = self.email.text().strip()
        if email and not is_valid_email(email):
            self.errorLabel.setText("Invalid Email Format.")
            self.login_btn.setEnabled(False)


    

    def verify_login(self):
        email = self.email.text().strip()
        password = hash_text(self.password.text())

        if not email or not password:
            self.errorLabel.setText("Please enter both Email and Password.")
            return

        conn = sqlite3.connect("users.db")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT role, name, is_verified,status FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        conn.close()

        if not user:
            self.errorLabel.setText("Invalid Email or Password")
        elif not user['is_verified']:
            
            message, _ok = send_verification_token(email)

            if not _ok:
                self.errorLabel.setText(message)
            else:
                self.errorLabel.setText("Account is not verified, check your email inbox")    
       elif not user["status"]:
           self.errorLabel.setText("Admin Hasn't Approved Yet")
       else:
            self.open_dashboard_by_role(user['role'], user['name'])
    def open_dashboard_by_role(self, role, name):
        global dashboard_window 
        if role == "Sender":
            from sender_dashboard import SenderDashboard
            dashboard_window = SenderDashboard(name)
        elif role == "Receiver":
            from receiver_dashboard import ReceiverDashboard
            dashboard_window = ReceiverDashboard(name)
        else:
            from admin_dashboard import AdminDashboard
            dashboard_window = AdminDashboard(name)
            
        dashboard_window.showMaximized()
        if self.window():
            self.window().hide()

    
    
    def toggle_password_visibility(self):
        if self.password.echoMode() == QtWidgets.QLineEdit.Password:
            self.password.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.password.setEchoMode(QtWidgets.QLineEdit.Password)
    

# =======================================================
# ROLE DASHBOARD CLASSES (RETAINED)
# =======================================================

# --- BASE DASHBOARD CLASS FOR ALL ROLES (RETAINED) ---
class BaseRoleDashboard(QtWidgets.QWidget):
    # Signal emitted when the user wants to go back to the role selection screen
    back_to_roles = QtCore.pyqtSignal()
    
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: white; border-radius: 10px;") 
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        
        role_title = QtWidgets.QLabel(title)
        role_title.setStyleSheet(f"font: bold 32pt 'Segoe UI'; color: {BLUE_PRIMARY}; margin-bottom: 20px;")
        layout.addWidget(role_title, alignment=QtCore.Qt.AlignCenter)

        for text in items:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedSize(350, 60) 
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #4da9ff; 
                    color: white; 
                    font: bold 14pt 'Segoe UI';
                    border-radius: 10px;
                    padding: 5px;
                    margin: 8px;
                }}
                QPushButton:hover {{
                    background-color: #1c83e8; 
                }}
            """)
            layout.addWidget(btn, alignment=QtCore.Qt.AlignCenter)

        layout.addStretch()

        back_btn = QtWidgets.QPushButton("Back to Roles")
        back_btn.setFixedSize(250, 50)
        back_btn.setStyleSheet(BUTTON_PRIMARY_STYLE.replace("font-size: 20px", "font-size: 16px").replace("min-height: 50px", "min-height: 50px")) 
        back_btn.clicked.connect(self.back_to_roles.emit)
        layout.addWidget(back_btn, alignment=QtCore.Qt.AlignCenter)
        layout.addSpacing(30)

# --- SENDER DASHBOARD (RETAINED) ---
class SenderDashboard(BaseRoleDashboard):
    def __init__(self, parent=None):
        items = [
            "Upload File",
            "Encrypt File",
            "Select Transfer Method",
            "Send File",
            "Sent Files History"
        ]
        super().__init__("Sender Dashboard", items, parent)

# --- RECEIVER DASHBOARD (RETAINED) ---
class ReceiverDashboard(BaseRoleDashboard):
    def __init__(self, parent=None):
        items = [
            "View Incoming Files",
            "Enter Decryption Key",
            "Decrypt File",
            "Verify File Integrity",
            "Received Files History"
        ]
        super().__init__("Receiver Dashboard", items, parent)

# --- ADMIN DASHBOARD (RETAINED) ---
class AdminDashboard(BaseRoleDashboard):
    def __init__(self, parent=None):
        items = [
            "Manage Users",
            "View Forensic Logs",
            "AI Monitoring Alerts",
            "System Settings",
            "Statistics Dashboard"
        ]
        super().__init__("Admin Dashboard", items, parent)

# =======================================================
# DASHBOARD INTERFACE - MODIFIED FOR STACK
# =======================================================
class DashboardInterface(QtWidgets.QWidget):
    """
    Manages the switching between Role Selection and Role Specific Dashboards
    within the MainAppWindow stack.
    """
    # Signal emitted when the user requests LOGOUT (to switch back to WelcomePage - Index 0)
    logout_requested = QtCore.pyqtSignal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BLUE_PRIMARY};") 
        # Removed self.showMaximized() - handled by MainAppWindow

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.main_stack = QtWidgets.QStackedWidget()
        self.main_stack.setStyleSheet("background-color: transparent;") 

        # --- 1. Role Selection Screen (Index 0 of Dashboard Stack) ---
        self.roles_page = self._create_roles_selection_page()
        self.main_stack.addWidget(self.roles_page) 

        # --- 2. Sender Dashboard (Index 1 of Dashboard Stack) ---
        self.sender_page = SenderDashboard()
        self.sender_page.back_to_roles.connect(self._show_roles_page)
        self.main_stack.addWidget(self.sender_page) 

        # --- 3. Receiver Dashboard (Index 2 of Dashboard Stack) ---
        self.receiver_page = ReceiverDashboard()
        self.receiver_page.back_to_roles.connect(self._show_roles_page)
        self.main_stack.addWidget(self.receiver_page) 
        
        # --- 4. Admin Dashboard (Index 3 of Dashboard Stack) ---
        self.admin_page = AdminDashboard()
        self.admin_page.back_to_roles.connect(self._show_roles_page)
        self.main_stack.addWidget(self.admin_page) 

        self.main_layout.addWidget(self.main_stack)


    def _create_roles_selection_page(self):
        """Creates the main screen with Sender/Receiver/Admin boxes."""
        roles_page = QtWidgets.QWidget()
        roles_page.setStyleSheet("background-color: transparent;")
        v_layout = QtWidgets.QVBoxLayout(roles_page)
        v_layout.setAlignment(QtCore.Qt.AlignCenter)
        v_layout.setSpacing(10)
        v_layout.setContentsMargins(50, 50, 50, 50)
        
        # 1. Main Title
        main_title = QtWidgets.QLabel("Secure Data Sharing Framework")
        main_title.setStyleSheet("font: bold 28pt 'Segoe UI'; color: white;") 
        main_title.setAlignment(QtCore.Qt.AlignCenter)
        v_layout.addWidget(main_title)

        # 2. Sub Title
        sub_title = QtWidgets.QLabel("Select Your Role")
        sub_title.setStyleSheet("font: bold 20pt 'Segoe UI'; color: #bfdbfe;") 
        sub_title.setAlignment(QtCore.Qt.AlignCenter)
        v_layout.addWidget(sub_title)
        
        v_layout.addSpacing(50)

        # 3. Roles Container (Horizontal Layout)
        roles_h_layout = QtWidgets.QHBoxLayout()
        roles_h_layout.setAlignment(QtCore.Qt.AlignCenter)
        
        # --- Helper for creating a Role Box ---
        def create_role_box(title, index_to_switch):
            box_frame = QtWidgets.QFrame()
            box_frame.setFixedSize(300, 250) 
            box_frame.setStyleSheet("""
                QFrame {
                    background-color: white; 
                    border: 3px solid #0074b8; 
                    border-radius: 15px;
                }
            """)
            
            v_layout_box = QtWidgets.QVBoxLayout(box_frame)
            v_layout_box.setAlignment(QtCore.Qt.AlignCenter)
            v_layout_box.setSpacing(25)

            title_label = QtWidgets.QLabel(title)
            title_label.setStyleSheet("font: bold 18pt 'Segoe UI'; color: #004a7c;")
            title_label.setAlignment(QtCore.Qt.AlignCenter)
            v_layout_box.addWidget(title_label)
            
            open_button = QtWidgets.QPushButton("Open")
            open_button.setFixedSize(150, 50)
            open_button.setStyleSheet("""
                QPushButton {
                    background-color: #4da9ff; 
                    color: white; 
                    font: bold 14pt 'Segoe UI';
                    border-radius: 8px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #1c83e8; 
                }
            """)
            open_button.clicked.connect(lambda: self.main_stack.setCurrentIndex(index_to_switch))
            v_layout_box.addWidget(open_button)

            return box_frame

        # 4. Adding Roles to Layout
        roles_h_layout.addWidget(create_role_box("Sender", 1)) 
        roles_h_layout.addSpacing(70) 
        roles_h_layout.addWidget(create_role_box("Receiver", 2)) 
        roles_h_layout.addSpacing(70) 
        roles_h_layout.addWidget(create_role_box("Admin", 3)) 
        
        v_layout.addLayout(roles_h_layout)
        
        v_layout.addStretch()

        # 5. Logout Button (Now signals the MainAppWindow to switch to Welcome)
        logout_btn = QtWidgets.QPushButton("LOGOUT")
        logout_btn.setFixedSize(250, 50)
        logout_btn.setStyleSheet(BUTTON_PRIMARY_STYLE.replace("font-size: 20px", "font-size: 16px").replace("min-height: 50px", "min-height: 50px")) 
        # Emit signal to the parent MainAppWindow
        logout_btn.clicked.connect(self.logout_requested.emit) 
        v_layout.addWidget(logout_btn, alignment=QtCore.Qt.AlignCenter)
        
        return roles_page

    def _show_roles_page(self):
        """Switches the QStackedWidget back to the role selection screen (Index 0)."""
        self.main_stack.setCurrentIndex(0)

# =======================================================
# MAIN APPLICATION WINDOW (Single Window Manager) - NEW
# =======================================================

class MainDashboardUI(QtWidgets.QWidget):

    logout_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # MAIN LAYOUT
        mainLayout = QtWidgets.QVBoxLayout(self)
        mainLayout.setContentsMargins(0,0,0,0)
        mainLayout.setSpacing(0)

        # ================= HEADER =================
        header = QtWidgets.QFrame()
        header.setFixedHeight(75)
        header.setStyleSheet("background:#1e88e5; color:white;")

        headerLayout = QtWidgets.QHBoxLayout(header)
        headerLayout.setContentsMargins(25,0,25,0)

        title = QtWidgets.QLabel("Secure Data Sharing Framework")
        title.setStyleSheet("font-size:22px; font-weight:bold; color:white;")
        headerLayout.addWidget(title)
        headerLayout.addStretch()

        self.generateBtn = QtWidgets.QPushButton("Generate Report")
        self.notifyBtn = QtWidgets.QPushButton("🔔")
        self.adminBtn = QtWidgets.QPushButton("Admin")

        for b in [self.generateBtn, self.notifyBtn, self.adminBtn]:
            b.setFixedHeight(35)
            b.setStyleSheet("""
                QPushButton{
                    background:white;
                    color:#1e88e5;
                    border-radius:6px;
                    padding:5px 12px;
                    font-weight:600;
                }
                QPushButton:hover{
                    background:#e3f2fd;
                }
            """)
            headerLayout.addWidget(b)

        mainLayout.addWidget(header)

        # ================= BODY =================
        bodyLayout = QtWidgets.QHBoxLayout()
        bodyLayout.setContentsMargins(0,0,0,0)

        # ================= SIDEBAR =================
        sidebar = QtWidgets.QFrame()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("background:white;")

        sideLayout = QtWidgets.QVBoxLayout(sidebar)
        sideLayout.setContentsMargins(15,20,15,20)
        sideLayout.setSpacing(15)

        self.homeBtn = QtWidgets.QPushButton("Home")
        self.uploadBtn = QtWidgets.QPushButton("Upload Data")
        self.filesBtn = QtWidgets.QPushButton("My Files")
        self.recordsBtn = QtWidgets.QPushButton("Files Record")
        self.auditBtn = QtWidgets.QPushButton("Audit Logs")
        self.usersBtn = QtWidgets.QPushButton("User Management")
        self.settingsBtn = QtWidgets.QPushButton("Settings")
        self.transferBtn = QtWidgets.QPushButton("Data Transfer")

        buttons = [
            self.homeBtn, self.uploadBtn, self.filesBtn,
            self.recordsBtn, self.auditBtn, self.usersBtn,
            self.settingsBtn, self.transferBtn
        ]

        for b in buttons:
            b.setFixedHeight(48)
            b.setStyleSheet("""
                QPushButton{
                    text-align:left;
                    padding-left:15px;
                    font-size:16px;
                    font-weight:600;
                    background:white;
                    border:2px solid #1e88e5;
                    border-radius:8px;
                    color:#1e88e5;
                }
                QPushButton:hover{
                    background:#1e88e5;
                    color:white;
                }
            """)
            sideLayout.addWidget(b)

        sideLayout.addSpacing(15)

        self.logoutBtn = QtWidgets.QPushButton("Logout")
        self.logoutBtn.setFixedHeight(45)
        self.logoutBtn.setStyleSheet("""
            QPushButton{
                background:#e53935;
                color:white;
                border-radius:8px;
                font-weight:bold;
                font-size:15px;
            }
            QPushButton:hover{
                background:#c62828;
            }
        """)
        sideLayout.addWidget(self.logoutBtn)

        # ================= CONTENT AREA =================
        self.contentStack = QtWidgets.QStackedWidget()
        self.contentStack.setStyleSheet("background:#f5f9ff;")

        # Create Pages
        self.pageHome = self.createPage("Dashboard Home",
                                        ["View System Overview",
                                         "Check Recent Activity",
                                         "Monitor Security Status"])

        self.pageUpload = self.createPage("Upload Data",
                                          ["Select File",
                                           "Encrypt Before Upload",
                                           "Upload Securely"])

        self.pageFiles = self.createPage("My Files",
                                         ["View Files",
                                          "Download File",
                                          "Delete File"])

        self.pageRecords = self.createPage("Files Record",
                                           ["Track File History",
                                            "Check Integrity",
                                            "View Access Logs"])

        self.pageAudit = self.createPage("Audit Logs",
                                         ["Monitor User Activity",
                                          "View Login Records",
                                          "Track Modifications"])

        self.pageUsers = self.createPage("User Management",
                                         ["Add User",
                                          "Assign Roles",
                                          "Manage Permissions"])

        self.pageSettings = self.createPage("Settings",
                                            ["Change Password",
                                             "Enable 2FA",
                                             "Update Profile"])

        self.pageTransfer = self.createPage("Data Transfer",
                                            ["Send Secure File",
                                             "Verify Receiver",
                                             "Track Transfer Status"])

        pages = [
            self.pageHome, self.pageUpload, self.pageFiles,
            self.pageRecords, self.pageAudit, self.pageUsers,
            self.pageSettings, self.pageTransfer
        ]

        for p in pages:
            self.contentStack.addWidget(p)

        bodyLayout.addWidget(sidebar)
        bodyLayout.addWidget(self.contentStack)

        mainLayout.addLayout(bodyLayout)

        # BUTTON CONNECTIONS
        self.homeBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(0))
        self.uploadBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(1))
        self.filesBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(2))
        self.recordsBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(3))
        self.auditBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(4))
        self.usersBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(5))
        self.settingsBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(6))
        self.transferBtn.clicked.connect(lambda: self.contentStack.setCurrentIndex(7))

        self.logoutBtn.clicked.connect(self.logout_requested.emit)


    # PAGE CREATOR
    def createPage(self, titleText, buttonTexts):

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        title = QtWidgets.QLabel(titleText)
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size:34px; font-weight:bold; color:#1e88e5;")
        layout.addWidget(title)

        layout.addSpacing(40)

        for text in buttonTexts:
            btn = QtWidgets.QPushButton(text)
            btn.setFixedWidth(300)
            btn.setFixedHeight(55)
            btn.setStyleSheet("""
                QPushButton{
                    font-size:17px;
                    font-weight:600;
                    background:white;
                    border:2px solid #1e88e5;
                    border-radius:10px;
                    color:#1e88e5;
                }
                QPushButton:hover{
                    background:#1e88e5;
                    color:white;
                }
            """)
            layout.addWidget(btn)
            layout.addSpacing(15)

        return page




class MainAppWindow(QtWidgets.QWidget):
    """
    Main application container that manages all pages (Welcome, Signin, Signup, Dashboard) 
    using a QStackedWidget, ensuring all pages run in a single, maximized window.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure Data Sharing Framework")
        self.setStyleSheet(f"background-color: {BLUE_LIGHT_BG};")
        self.showMaximized() # Ensures full-screen launch
        self.setMinimumSize(
            QtWidgets.QDesktopWidget().availableGeometry().size()
        )


        self.stack = QtWidgets.QStackedWidget()
        
        # Initialize Pages
        # Passing self as parent allows widgets to access the stack manager (via signals)
        self.welcome_page = WelcomePage(self)
        self.signin_page = SigninPage(self)
        self.signup_page = SignupPage(self)
        self.main_dashboard = MainDashboardUI(self)

        # Add pages to the stack (Indices defined below)
        self.stack.addWidget(self.welcome_page)   # Index 0: Welcome
        self.stack.addWidget(self.signin_page)    # Index 1: Signin
        self.stack.addWidget(self.signup_page)    # Index 2: Signup
        self.stack.addWidget(self.main_dashboard)  # Index 3

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.stack)

        # Connections to switch pages
        # All sub-pages emit signals which are caught by the MainAppWindow's navigate method
        self.welcome_page.switch_page.connect(self.navigate)
        self.signin_page.switch_page.connect(self.navigate)
        self.signup_page.switch_page.connect(self.navigate)
        
        self.main_dashboard.logout_requested.connect(
        lambda: self.stack.setCurrentIndex(0)
)
        
 

    def navigate(self, target_index):
        """Switches the view to the desired page index."""
        # target_index: 0=Welcome, 1=Signin, 2=Signup, 3=Dashboard
        self.stack.setCurrentIndex(target_index)


# --- app.py ke andar ---                

    # ... baqi code ...

    # =======================================================
    # FUNCTIONS TO OPEN DASHBOARDS (Updated to Hide Landing)
    # =======================================================
    def open_sender_dashboard(self, name):
        self.hide() # <--- LANDING PAGE CHUP JAYEGI
        from sender_dashboard import SenderDashboard
        self.dashboard = SenderDashboard(name)
        self.dashboard.showMaximized()

    def open_receiver_dashboard(self, name):
        self.hide() # <--- LANDING PAGE CHUP JAYEGI
        from receiver_dashboard import ReceiverDashboard
        self.dashboard = ReceiverDashboard(name)
        self.dashboard.showMaximized()

    def open_admin_dashboard(self, name):
        self.hide() # <--- LANDING PAGE CHUP JAYEGI
        from admin_dashboard import AdminDashboard
        self.dashboard = AdminDashboard(name)
        self.dashboard.showMaximized()

    # ... baqi code ...


# =======================================================
# MAIN
# =======================================================
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # App is now managed by the MainAppWindow class for single-window switching
    win = MainAppWindow() 
    win.show()
    sys.exit(app.exec_())
