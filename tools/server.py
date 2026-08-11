import socket
import threading
import json

# Configuration
HOST = '0.0.0.0'
PORT = 55555

connected_clients = []

def server_client_handler(conn, addr):
    global connected_clients
    try:
        rfile = conn.makefile('r')
        while True:
            line = rfile.readline()
            if not line:
                break
            
            raw_data = line.strip()
            
            # Drop any self-hit or self-damage packets instantly
            try:
                packet = json.loads(raw_data)
                if packet.get('type') == 'hit':
                    if packet.get('id') == packet.get('target_id'):
                        continue
            except Exception:
                pass
            
            # Relay the packet to all OTHER connected clients
            for client in connected_clients:
                if client != conn:
                    try:
                        client.sendall((raw_data + '\n').encode())
                    except Exception as e:
                        print(f"[!] Failed to send packet to a client: {e}")
                        
    except ConnectionResetError:
        print(f"[-] Connection dropped by {addr}")
    except Exception as e:
        print(f"[-] Server handler error for {addr}: {e}")
    finally:
        if conn in connected_clients:
            connected_clients.remove(conn)
        try:
            conn.close()
        except:
            pass
        print(f"[-] Client disconnected: {addr} | Active users: {len(connected_clients)}")

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print(f"[+] Dedicated Relay Server Hosting on {HOST}:{PORT}...")
    except Exception as e:
        print(f"[!] Failed to bind server: {e}")
        return

    while True:
        try:
            conn, addr = server_socket.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connected_clients.append(conn)
            print(f"[+] New client connected from {addr} | Active users: {len(connected_clients)}")
            
            threading.Thread(target=server_client_handler, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[!] Server shutting down.")
            break
        except Exception as e:
            print(f"[-] Acceptance loop error: {e}")
            break

if __name__ == "__main__":
    start_server()