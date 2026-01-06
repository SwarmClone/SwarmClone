from backend.src.api.server import Server

if __name__ == "__main__":
    server = Server(host="127.0.0.1", port=8000)
    server.run()