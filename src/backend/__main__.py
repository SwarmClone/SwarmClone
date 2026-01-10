from backend.api.server import Server

def main():
    server = Server(host="127.0.0.1", port=8000)
    server.run()

if __name__ == "__main__":
    main()