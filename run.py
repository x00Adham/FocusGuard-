from app import create_app, socketio

# Initialize the Flask application
app = create_app()

if __name__ == '__main__':
    print("Starting Focus Guard Server...")
    print("AI Engine initialized. WebSockets ready.")
    # Run the server with SocketIO
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)