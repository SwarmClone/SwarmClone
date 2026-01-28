from flask import Flask

app = Flask("SwarmCloneBackend")


@app.route('/')
def hello():
    return 'Hello from SwarmCloneBackend!'


if __name__ == '__main__':
    app.run(host="127.0.0.1", port=8192)
