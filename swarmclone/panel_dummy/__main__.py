from . import config
import threading
import socket
import json
import subprocess

def to_llm(from_asr_conn: socket.socket, to_llm_conn: socket.socket, to_frontend_conn: socket.socket):
    while True:
        data = from_asr_conn.recv(4096)
        if not data:
            break
        to_llm_conn.sendall(data)
        to_frontend_conn.sendall(data)
        try:
            if json.loads(data.decode())['from'] == "stop":
                break
        except:
            pass

def from_llm(from_llm_conn: socket.socket, to_tts_conn: socket.socket, to_frontend_conn: socket.socket):
    while True:
        data = from_llm_conn.recv(4096)
        if not data:
            break
        to_tts_conn.sendall(data)
        to_frontend_conn.sendall(data)
        try:
            if json.loads(data.decode())['from'] == "stop":
                break
        except:
            pass

if __name__ == '__main__':
    with (  socket.socket(socket.AF_INET, socket.SOCK_STREAM) as from_asr_sock, 
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as to_llm_sock,
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as from_llm_sock,
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as to_tts_sock,
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as to_frontend_sock):
        from_asr_sock.bind((config.PANEL_HOST, config.PANEL_FROM_ASR))
        from_asr_sock.listen(1)
        to_llm_sock.bind((config.PANEL_HOST, config.PANEL_TO_LLM))
        to_llm_sock.listen(1)
        from_llm_sock.bind((config.PANEL_HOST, config.PANEL_FROM_LLM))
        from_llm_sock.listen(1)
        to_tts_sock.bind((config.PANEL_HOST, config.PANEL_TO_TTS))
        to_tts_sock.listen(1)
        to_frontend_sock.bind((config.PANEL_HOST, config.PANEL_TO_UNITY))
        to_frontend_sock.listen(1)

        from_asr_conn, from_asr_addr = from_asr_sock.accept()
        print(f"ASR connected from {from_asr_addr}")
        to_llm_conn, to_llm_addr = to_llm_sock.accept()
        print(f"LLM INPUT connected from {to_llm_addr}")
        from_llm_conn, from_llm_addr = from_llm_sock.accept()
        print(f"LLM OUTPUT connected from {from_llm_addr}")
        to_tts_conn, to_tts_addr = to_tts_sock.accept()
        print(f"TTS connected from {to_tts_addr}")
        to_frontend_conn, to_frontend_addr = to_frontend_sock.accept()
        print(f"UNITY connected from {to_frontend_addr}")

        try:
            to_llm_thread = threading.Thread(target=to_llm, args=(from_asr_conn, to_llm_conn, to_frontend_conn))
            to_llm_thread.start()
            from_llm_thread = threading.Thread(target=from_llm, args=(from_llm_conn, to_tts_conn, to_frontend_conn))
            from_llm_thread.start()
            to_llm_thread.join()
            from_llm_thread.join()
        except KeyboardInterrupt:
            pass
        finally:
            from_asr_conn.close()
            to_llm_conn.close()
            from_asr_sock.close()
            to_llm_sock.close()

