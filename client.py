import sys
import json
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, 
    QHBoxLayout, QVBoxLayout, QPushButton, 
    QListWidget, QTextEdit, QLabel, QInputDialog,
    QLineEdit, QDialog, QMessageBox, QMenu, QStackedWidget,
    QCheckBox
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtNetwork import QTcpSocket, QAbstractSocket

SESSION_FILE = "session.json"


# =====================================================================
# SESSION PERSISTENCE HELPERS (AUTO-LOGIN)
# =====================================================================
def save_session(phone, password, auto_login=False):
    if auto_login:
        with open(SESSION_FILE, "w") as f:
            json.dump({"phone": phone, "password": password, "auto_login": True}, f)
    else:
        clear_session()

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                if data.get("auto_login"):
                    return data
        except Exception:
            pass
    return None


# =====================================================================
# LOGIN & SIGNUP DIALOG
# =====================================================================
class AuthDialog(QDialog):
    def __init__(self, socket, auto_credentials=None, parent=None):
        super().__init__(parent)
        self.socket = socket
        self.setWindowTitle("Authentication")
        self.setFixedSize(320, 420)

        self.user_data = None
        self.saved_credentials = None
        self.socket.readyRead.connect(self.handle_auth_response)

        layout = QVBoxLayout(self)
        self.stacked = QStackedWidget()

        # --- LOGIN PAGE ---
        login_widget = QWidget()
        l_layout = QVBoxLayout(login_widget)
        
        l_title = QLabel("<h2>Login</h2>")
        self.l_phone = QLineEdit()
        self.l_phone.setPlaceholderText("Phone Number")
        self.l_pwd = QLineEdit()
        self.l_pwd.setPlaceholderText("Password")
        self.l_pwd.setEchoMode(QLineEdit.Password)
        
        self.chk_auto_login = QCheckBox("Keep me logged in")
        self.chk_auto_login.setChecked(True)

        btn_login = QPushButton("Log In")
        btn_to_signup = QPushButton("Don't have an account? Sign Up")
        btn_to_signup.setFlat(True)

        l_layout.addWidget(l_title)
        l_layout.addWidget(self.l_phone)
        l_layout.addWidget(self.l_pwd)
        l_layout.addWidget(self.chk_auto_login)
        l_layout.addWidget(btn_login)
        l_layout.addWidget(btn_to_signup)
        l_layout.addStretch()

        # --- SIGNUP PAGE ---
        signup_widget = QWidget()
        s_layout = QVBoxLayout(signup_widget)
        
        s_title = QLabel("<h2>Sign Up</h2>")
        self.s_name = QLineEdit()
        self.s_name.setPlaceholderText("Full Name")
        self.s_phone = QLineEdit()
        self.s_phone.setPlaceholderText("Phone Number")
        self.s_pwd = QLineEdit()
        self.s_pwd.setPlaceholderText("Password")
        self.s_pwd.setEchoMode(QLineEdit.Password)
        
        self.chk_signup_auto_login = QCheckBox("Keep me logged in")
        self.chk_signup_auto_login.setChecked(True)

        btn_signup = QPushButton("Register Account")
        btn_to_login = QPushButton("Already have an account? Log In")
        btn_to_login.setFlat(True)

        s_layout.addWidget(s_title)
        s_layout.addWidget(self.s_name)
        s_layout.addWidget(self.s_phone)
        s_layout.addWidget(self.s_pwd)
        s_layout.addWidget(self.chk_signup_auto_login)
        s_layout.addWidget(btn_signup)
        s_layout.addWidget(btn_to_login)
        s_layout.addStretch()

        self.stacked.addWidget(login_widget)
        self.stacked.addWidget(signup_widget)
        layout.addWidget(self.stacked)

        btn_login.clicked.connect(self.send_login)
        btn_signup.clicked.connect(self.send_signup)
        btn_to_signup.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        btn_to_login.clicked.connect(lambda: self.stacked.setCurrentIndex(0))

        # Perform silent login if valid session exists
        if auto_credentials:
            self.l_phone.setText(auto_credentials["phone"])
            self.l_pwd.setText(auto_credentials["password"])
            self.send_login()

    def send_login(self):
        phone = self.l_phone.text().strip()
        pwd = self.l_pwd.text().strip()
        if phone and pwd:
            self.saved_credentials = (phone, pwd, self.chk_auto_login.isChecked())
            payload = {"type": "login", "phone": phone, "password": pwd}
            self.socket.write(json.dumps(payload).encode('utf-8'))

    def send_signup(self):
        name = self.s_name.text().strip()
        phone = self.s_phone.text().strip()
        pwd = self.s_pwd.text().strip()
        if name and phone and pwd:
            self.saved_credentials = (phone, pwd, self.chk_signup_auto_login.isChecked())
            payload = {"type": "signup", "name": name, "phone": phone, "password": pwd}
            self.socket.write(json.dumps(payload).encode('utf-8'))

    def handle_auth_response(self):
        raw_bytes = self.socket.readAll().data()
        try:
            res = json.loads(raw_bytes.decode('utf-8'))
            if res.get("type") == "auth_response":
                if res.get("success"):
                    self.user_data = res
                    # Save local session settings
                    if self.saved_credentials:
                        phone, pwd, auto_login = self.saved_credentials
                        save_session(phone, pwd, auto_login)
                    
                    self.socket.readyRead.disconnect(self.handle_auth_response)
                    self.accept()
                else:
                    QMessageBox.warning(self, "Authentication Error", res.get("message"))
        except Exception as e:
            print("Auth Error:", e)


# =====================================================================
# DYNAMIC AUTO-RESIZING TEXT INPUT
# =====================================================================
class AutoResizingTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        font_metrics = self.fontMetrics()
        line_height = font_metrics.lineSpacing()
        padding = 16 
        
        self.min_height = line_height + padding
        self.max_height = (line_height * 2) + padding
        
        self.setFixedHeight(self.min_height)
        self.textChanged.connect(self.adjust_height)

    def adjust_height(self):
        doc_height = int(self.document().size().height())
        new_height = max(self.min_height, min(doc_height + 10, self.max_height))
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                main_window = self.window()
                if hasattr(main_window, 'send_message'):
                    main_window.send_message()
                return
        else:
            super().keyPressEvent(event)


# =====================================================================
# MAIN WINDOW
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self, socket, user_data):
        super().__init__()
        self.socket = socket
        self.my_phone = user_data["phone"]
        self.my_name = user_data["name"]
        self.setWindowTitle(f"MS Chat App - {self.my_name} ({self.my_phone})")

        self.contacts = {}
        self.current_contact_phone = None

        self.socket.readyRead.connect(self.receive_server_data)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # COLUMN 1: Sidebar
        sidebar_layout = QVBoxLayout()
        btn_chat = QPushButton("💬")
        btn_add_contact = QPushButton("➕")
        btn_logout = QPushButton("🚪")
        
        btn_chat.setObjectName("iconButton")
        btn_add_contact.setObjectName("iconButton")
        btn_logout.setObjectName("iconButton")
        
        btn_add_contact.setToolTip("Add Contact by Phone")
        btn_logout.setToolTip("Log Out & Clear Saved Session")
        
        btn_add_contact.clicked.connect(self.send_friend_request_dialog)
        btn_logout.clicked.connect(self.logout)

        sidebar_layout.addWidget(btn_chat)
        sidebar_layout.addWidget(btn_add_contact)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(btn_logout)

        # COLUMN 2: Conversations List
        self.conversations_list = QListWidget()
        self.conversations_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.conversations_list.customContextMenuRequested.connect(self.show_context_menu)

        # COLUMN 3: Chat Interface
        chat_area_layout = QVBoxLayout()
        chat_area_layout.setSpacing(6)
        chat_area_layout.setContentsMargins(0, 0, 0, 0)

        self.chat_header = QLabel("No contact selected")
        self.chat_header.setObjectName("chatHeader")

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)

        input_layout = QHBoxLayout()
        input_layout.setAlignment(Qt.AlignBottom)

        self.message_input = AutoResizingTextEdit()
        self.message_input.setPlaceholderText("Select a contact to type a message...")
        self.message_input.setEnabled(False)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setEnabled(False)

        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)

        chat_area_layout.addWidget(self.chat_header)
        chat_area_layout.addWidget(self.chat_history, 1)
        chat_area_layout.addLayout(input_layout)

        main_layout.addLayout(sidebar_layout, 1)
        main_layout.addWidget(self.conversations_list, 14)
        main_layout.addLayout(chat_area_layout, 35)

        self.send_button.clicked.connect(self.send_message)
        self.conversations_list.currentRowChanged.connect(self.switch_contact_by_row)

        self.apply_theme()

    def logout(self):
        clear_session()
        QMessageBox.information(self, "Logged Out", "Session cleared. Restart app to log in again.")
        self.close()

    # -----------------------------------------------------------------
    # CONTACT & FRIEND REQUESTS BY PHONE
    # -----------------------------------------------------------------
    def send_friend_request_dialog(self):
        target_phone, ok = QInputDialog.getText(self, "Add Contact", "Enter Friend's Phone Number:")
        if ok and target_phone.strip():
            phone = target_phone.strip()
            if phone == self.my_phone:
                QMessageBox.warning(self, "Warning", "You cannot add your own phone number.")
                return
            if phone in self.contacts:
                QMessageBox.information(self, "Info", "This contact is already in your list.")
                return

            payload = {
                "type": "friend_request",
                "sender_phone": self.my_phone,
                "recipient_phone": phone
            }
            self.socket.write(json.dumps(payload).encode('utf-8'))
            QMessageBox.information(self, "Request Sent", f"Request sent to phone {phone}. Awaiting response...")

    def handle_incoming_request(self, sender_phone, sender_name):
        reply = QMessageBox.question(
            self, 
            "Contact Request", 
            f"User '{sender_name}' ({sender_phone}) wants to add you. Accept?",
            QMessageBox.Yes | QMessageBox.No
        )

        accepted = (reply == QMessageBox.Yes)
        
        response_payload = {
            "type": "friend_response",
            "sender_phone": self.my_phone,
            "sender_name": self.my_name,
            "recipient_phone": sender_phone,
            "accepted": accepted
        }
        self.socket.write(json.dumps(response_payload).encode('utf-8'))

        if accepted:
            self.add_new_contact(sender_phone, sender_name)

    def add_new_contact(self, phone, name):
        if phone not in self.contacts:
            self.contacts[phone] = {"name": name, "history": []}
            display_text = f"{name} ({phone})"
            self.conversations_list.addItem(display_text)

    def show_context_menu(self, position: QPoint):
        item = self.conversations_list.itemAt(position)
        if not item:
            return

        row = self.conversations_list.row(item)
        phone = list(self.contacts.keys())[row]

        menu = QMenu(self)
        delete_action = menu.addAction(f"Delete Contact")
        action = menu.exec_(self.conversations_list.mapToGlobal(position))

        if action == delete_action:
            self.delete_contact(phone, row)

    def delete_contact(self, phone, row):
        if phone in self.contacts:
            del self.contacts[phone]
        self.conversations_list.takeItem(row)

        if self.current_contact_phone == phone:
            self.current_contact_phone = None
            self.chat_header.setText("No contact selected")
            self.chat_history.clear()
            self.message_input.setEnabled(False)
            self.send_button.setEnabled(False)

    # -----------------------------------------------------------------
    # NETWORK DATA HANDLING
    # -----------------------------------------------------------------
    def send_message(self):
        if not self.current_contact_phone:
            return

        text = self.message_input.toPlainText().strip()
        
        if text != "":
            formatted_text = text.replace('\n', '<br>')
            formatted_msg = f"<b>You:</b> {formatted_text}"
            
            self.contacts[self.current_contact_phone]["history"].append(formatted_msg)
            self.chat_history.append(formatted_msg)
            self.message_input.clear()
            self.message_input.setFocus()

            payload = {
                "type": "chat_msg",
                "sender_phone": self.my_phone,
                "sender_name": self.my_name,
                "recipient_phone": self.current_contact_phone,
                "text": formatted_text
            }
            self.socket.write(json.dumps(payload).encode('utf-8'))

    def receive_server_data(self):
        raw_bytes = self.socket.readAll().data()
        try:
            payload = json.loads(raw_bytes.decode('utf-8'))
            msg_type = payload.get("type")

            if msg_type == "friend_request":
                self.handle_incoming_request(payload["sender_phone"], payload["sender_name"])

            elif msg_type == "friend_response":
                if payload.get("accepted"):
                    s_phone = payload["sender_phone"]
                    s_name = payload["sender_name"]
                    QMessageBox.information(self, "Accepted", f"'{s_name}' ({s_phone}) accepted your request!")
                    self.add_new_contact(s_phone, s_name)
                else:
                    QMessageBox.warning(self, "Declined", "Contact request was declined.")

            elif msg_type == "chat_msg":
                s_phone = payload.get("sender_phone")
                s_name = payload.get("sender_name")
                text = payload.get("text")

                if s_phone and text:
                    formatted_msg = f"<b>{s_name}:</b> {text}"
                    
                    if s_phone not in self.contacts:
                        self.add_new_contact(s_phone, s_name)

                    self.contacts[s_phone]["history"].append(formatted_msg)

                    if s_phone == self.current_contact_phone:
                        self.chat_history.append(formatted_msg)

            elif msg_type == "system":
                QMessageBox.warning(self, "System", payload.get("text", ""))

        except Exception as e:
            print("Error parsing data:", e)

    # -----------------------------------------------------------------
    # UI CONTROLS & STYLES
    # -----------------------------------------------------------------
    def switch_contact_by_row(self, row):
        if row >= 0 and row < len(self.contacts):
            phone = list(self.contacts.keys())[row]
            contact_info = self.contacts[phone]
            
            self.current_contact_phone = phone
            self.chat_header.setText(f"{contact_info['name']} ({phone})")
            
            self.message_input.setEnabled(True)
            self.send_button.setEnabled(True)
            self.message_input.setPlaceholderText("Type a message...")
            
            self.chat_history.clear()
            for line in contact_info["history"]:
                self.chat_history.append(line)
            self.message_input.setFocus()

    def apply_theme(self):
        style_sheet = """
            QMainWindow { background-color: #1e1e2e; }
            QLabel#chatHeader { color: #ffffff; font-size: 16px; font-weight: bold; padding: 6px 4px; }
            QPushButton#iconButton { background-color: #2b2b3d; color: #ffffff; border: none; border-radius: 8px; font-size: 18px; min-width: 42px; min-height: 42px; }
            QPushButton#iconButton:hover { background-color: #3b3b52; }
            QListWidget { background-color: #252536; color: #e0e0e0; border: 1px solid #313145; border-radius: 10px; padding: 5px; font-size: 14px; outline: none; }
            QListWidget::item { padding: 10px; border-radius: 6px; }
            QListWidget::item:hover { background-color: #2e2e44; }
            QListWidget::item:selected { background-color: #0078d4; color: #ffffff; }
            QTextEdit { background-color: #252536; color: #ffffff; border: 1px solid #313145; border-radius: 10px; padding: 12px; font-size: 14px; }
            AutoResizingTextEdit { background-color: #2b2b3d; color: #ffffff; border: 1px solid #3d3d56; border-radius: 8px; padding: 6px 10px; font-size: 14px; }
            AutoResizingTextEdit:focus { border: 1px solid #0078d4; }
            AutoResizingTextEdit:disabled { background-color: #1a1a26; color: #555566; }
            QPushButton#sendButton { background-color: #0078d4; color: #ffffff; border: none; border-radius: 8px; padding: 10px 18px; font-weight: bold; font-size: 14px; min-height: 22px; }
            QPushButton#sendButton:hover { background-color: #106ebe; }
            QPushButton#sendButton:disabled { background-color: #2b2b3d; color: #555566; }
            QMenu { background-color: #252536; color: #ffffff; border: 1px solid #313145; padding: 4px; border-radius: 6px; }
            QMenu::item:selected { background-color: #d9534f; color: #ffffff; border-radius: 4px; }
            QCheckBox { color: #ffffff; }
        """
        self.setStyleSheet(style_sheet)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    socket = QTcpSocket()
    socket.connectToHost("127.0.0.1", 12345)

    if not socket.waitForConnected(3000):
        QMessageBox.critical(None, "Connection Error", "Could not connect to server on 127.0.0.1:12345")
        sys.exit()

    saved_session = load_session()

    auth_dialog = AuthDialog(socket, auto_credentials=saved_session)
    if auth_dialog.exec() == QDialog.Accepted:
        window = MainWindow(socket, auth_dialog.user_data)
        window.showMaximized()
        sys.exit(app.exec())
    else:
        sys.exit()
