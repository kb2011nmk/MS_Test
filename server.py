import socket
import threading
import json

HOST = '127.0.0.1'
PORT = 12345

# Database storing registered users: {phone: {"password": pwd, "name": name}}
user_db = {}
db_lock = threading.Lock()

# Online connected clients: {phone: socket_obj}
active_clients = {}
clients_lock = threading.Lock()

def handle_client(client_socket, client_address):
    print(f"[+] Connection attempt from {client_address}")
    user_phone = None

    try:
        while True:
            data = client_socket.recv(4096)
            if not data:
                break

            try:
                msg = json.loads(data.decode('utf-8'))
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            # ---------------------------------------------------------
            # 1. SIGN UP (AUTO-LOGS IN ON SUCCESS)
            # ---------------------------------------------------------
            if msg_type == "signup":
                phone = msg.get("phone")
                password = msg.get("password")
                name = msg.get("name")

                with db_lock:
                    if phone in user_db:
                        response = {
                            "type": "auth_response", 
                            "success": False, 
                            "message": "Phone number already registered."
                        }
                    else:
                        user_db[phone] = {"password": password, "name": name}
                        user_phone = phone
                        response = {
                            "type": "auth_response", 
                            "success": True, 
                            "message": "Account created successfully!",
                            "phone": phone,
                            "name": name
                        }

                if response["success"]:
                    with clients_lock:
                        active_clients[user_phone] = client_socket
                    print(f"[REGISTER & LOGIN] {name} ({phone}) registered and logged in.")

                client_socket.sendall(json.dumps(response).encode('utf-8'))
                continue

            # ---------------------------------------------------------
            # 2. LOGIN
            # ---------------------------------------------------------
            elif msg_type == "login":
                phone = msg.get("phone")
                password = msg.get("password")

                with db_lock:
                    user_data = user_db.get(phone)
                    if user_data and user_data["password"] == password:
                        user_phone = phone
                        display_name = user_data["name"]
                        success = True
                        message = "Login successful."
                    else:
                        success = False
                        display_name = ""
                        message = "Invalid phone number or password."

                if success:
                    with clients_lock:
                        active_clients[user_phone] = client_socket
                    print(f"[LOGIN] {display_name} ({user_phone}) logged in.")

                response = {
                    "type": "auth_response", 
                    "success": success, 
                    "message": message,
                    "phone": user_phone if success else None,
                    "name": display_name if success else None
                }
                client_socket.sendall(json.dumps(response).encode('utf-8'))
                continue

            # ---------------------------------------------------------
            # 3. FRIEND REQUEST BY PHONE
            # ---------------------------------------------------------
            elif msg_type == "friend_request":
                target_phone = msg.get("recipient_phone")
                sender_phone = msg.get("sender_phone")

                with db_lock:
                    target_user = user_db.get(target_phone)
                    sender_user = user_db.get(sender_phone)

                if not target_user:
                    err_payload = {"type": "system", "text": f"No account found for phone: {target_phone}"}
                    client_socket.sendall(json.dumps(err_payload).encode('utf-8'))
                    continue

                req_payload = {
                    "type": "friend_request",
                    "sender_phone": sender_phone,
                    "sender_name": sender_user["name"] if sender_user else sender_phone,
                    "recipient_phone": target_phone
                }

                with clients_lock:
                    target_socket = active_clients.get(target_phone)

                if target_socket:
                    target_socket.sendall(json.dumps(req_payload).encode('utf-8'))
                else:
                    err_payload = {"type": "system", "text": f"User ({target_user['name']}) is currently offline."}
                    client_socket.sendall(json.dumps(err_payload).encode('utf-8'))

            # ---------------------------------------------------------
            # 4. FRIEND RESPONSE
            # ---------------------------------------------------------
            elif msg_type == "friend_response":
                target_phone = msg.get("recipient_phone")
                with clients_lock:
                    target_socket = active_clients.get(target_phone)
                if target_socket:
                    target_socket.sendall(json.dumps(msg).encode('utf-8'))

            # ---------------------------------------------------------
            # 5. CHAT MESSAGES
            # ---------------------------------------------------------
            elif msg_type == "chat_msg":
                target_phone = msg.get("recipient_phone")
                with clients_lock:
                    target_socket = active_clients.get(target_phone)

                if target_socket:
                    target_socket.sendall(json.dumps(msg).encode('utf-8'))
                else:
                    err_payload = {"type": "system", "text": "Recipient is offline."}
                    client_socket.sendall(json.dumps(err_payload).encode('utf-8'))

    except ConnectionResetError:
        pass
    finally:
        if user_phone:
            with clients_lock:
                if user_phone in active_clients:
                    del active_clients[user_phone]
            print(f"[-] User ({user_phone}) disconnected.")
        client_socket.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)
    print(f"[*] Chat Server running on {HOST}:{PORT}")

    try:
        while True:
            client_socket, client_address = server.accept()
            thread = threading.Thread(
                target=handle_client, 
                args=(client_socket, client_address), 
                daemon=True
            )
            thread.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
    finally:
        server.close()

if __name__ == "__main__":
    main()