import socket
import json

# Configuration
HOST = '0.0.0.0'
PORT = 55555

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        server_socket.bind((HOST, PORT))
        print(f"[+] Dedicated UDP Relay Server Hosting on {HOST}:{PORT}...")
    except Exception as e:
        print(f"[!] Failed to bind server: {e}")
        return

    known_clients = set()

    while True:
        try:
            data, addr = server_socket.recvfrom(4096)
            if addr not in known_clients:
                known_clients.add(addr)
                print(f"[+] New client address tracked: {addr} | Active tracked users: {len(known_clients)}")

            raw_data = data.decode('utf-8').strip()

            # Optional self-hit filtration check
            try:
                packet = json.loads(raw_data)
                if packet.get('type') == 'hit':
                    if packet.get('id') == packet.get('target_id'):
                        continue
            except Exception:
                pass

            # Broadcast packet to all other registered client addresses
            for client_addr in list(known_clients):
                if client_addr != addr:
                    try:
                        server_socket.sendto((raw_data + '\n').encode('utf-8'), client_addr)
                    except Exception as e:
                        print(f"[!] Failed to relay packet to {client_addr}: {e}")
                        known_clients.discard(client_addr)

        except KeyboardInterrupt:
            print("\n[!] Server shutting down.")
            break
        except Exception as e:
            print(f"[-] UDP Server loop error: {e}")
            break

if __name__ == "__main__":
    start_server()
