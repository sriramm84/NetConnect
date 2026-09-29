# NetConnect

## Real-Time Network Communication and Chat System

NetConnect is a real-time network communication and chat application built using **Python, Flask, and Flask-SocketIO**.

The application provides a client-server based communication environment where users can register, log in, join chat rooms, exchange real-time messages, share files, and interact with other connected users.

The system also includes **role-based access control** with separate privileges for **Administrators** and **Students**. Administrators can manage users and chat rooms, while students can communicate through authorized rooms and submit access requests or appeals.

---

## Table of Contents

* [Project Overview](#project-overview)
* [Objectives](#objectives)
* [Key Features](#key-features)
* [User Roles](#user-roles)
* [Chat Room System](#chat-room-system)
* [Real-Time Communication](#real-time-communication)
* [File Sharing](#file-sharing)
* [Moderation System](#moderation-system)
* [Appeal System](#appeal-system)
* [Technology Stack](#technology-stack)
* [Project Architecture](#project-architecture)
* [Project Structure](#project-structure)
* [Prerequisites](#prerequisites)
* [Installation](#installation)
* [Running the Application](#running-the-application)
* [Running with Ngrok](#running-with-ngrok)
* [Available Commands](#available-commands)
* [How the System Works](#how-the-system-works)
* [Data Storage](#data-storage)
* [Security Considerations](#security-considerations)
* [Troubleshooting](#troubleshooting)
* [Future Enhancements](#future-enhancements)
* [Learning Outcomes](#learning-outcomes)
* [License](#license)

---

# Project Overview

NetConnect is designed as a **real-time client-server communication system**.

The backend is implemented using Flask and Flask-SocketIO. HTTP routes are used for authentication, pages, data access, and appeal operations, while Socket.IO provides real-time communication between connected clients.

The application maintains users, rooms, messages, uploaded files, and appeal information using local JSON/text-based storage.

The server listens on:

```text
http://localhost:5002
```

The application is configured to listen on all network interfaces:

```text
0.0.0.0:5002
```

The server configuration is defined in `app.py`.

---

# Objectives

The main objectives of NetConnect are:

1. Build a real-time client-server communication system.
2. Demonstrate real-time communication using WebSockets/Socket.IO.
3. Implement user authentication.
4. Implement role-based access control.
5. Provide multiple chat rooms.
6. Allow users to communicate in real time.
7. Implement administrative moderation features.
8. Allow file sharing between users in a room.
9. Implement controlled access to locked rooms.
10. Provide an appeal mechanism for banned or kicked users.
11. Demonstrate practical Computer Networks concepts through a working application.

---

# Key Features

## 1. User Registration

New users can register using:

* Username
* Password
* Role

The application supports student and administrator roles.

Passwords are stored using **bcrypt hashing** rather than storing plain-text passwords.

The registration endpoint validates the username and password before creating the account.

---

## 2. User Login

Registered users can log in using their username and password.

The application:

1. Checks whether the user exists.
2. Verifies the password using bcrypt.
3. Checks whether the user is banned.
4. Creates a session for the authenticated user.
5. Stores the username and role in the session.

The application provides separate routes for administrator and student chat access.

---

## 3. Role-Based Access Control

NetConnect has two primary roles:

### Administrator

Administrators can:

* Create rooms
* Delete rooms
* Lock rooms
* Unlock rooms
* Mute users
* Unmute users
* Ban users
* Unban users
* Kick users
* Approve room requests
* Deny room requests
* View online users
* Manage appeals

### Student

Students can:

* Join available rooms
* Send messages
* Receive real-time messages
* Request access to locked rooms
* Leave rooms
* View online users
* Submit appeals
* Communicate with administrators through the appeal chat

---

# Chat Room System

NetConnect uses Socket.IO rooms for real-time communication.

A default `general` room is created when the application initializes its data if no rooms file exists.

Administrators can create additional rooms.

Each room maintains information such as:

```text
Room Name
Locked / Unlocked Status
Members
```

Students are restricted to one active room at a time.

When a student joins a different room, their previous room membership is removed from the persisted room data.

---

# Real-Time Communication

The main networking functionality is implemented using **Flask-SocketIO**.

When a user sends a message:

```text
Client
   |
   | Socket.IO message
   ↓
Flask-SocketIO Server
   |
   | Validate user
   |
   | Validate room
   |
   | Process message
   ↓
Socket.IO Room
   |
   ↓
Connected Clients
```

Messages are broadcast to users who have joined the corresponding Socket.IO room.

The server also maintains information about connected users and their active sessions.

---

# Online User Tracking

The server maintains mappings for connected clients.

Conceptually:

```text
Socket ID → Username
Username → Socket IDs
```

This allows the application to determine which users are currently connected.

The online user list is updated when clients connect or disconnect.

Users can use:

```text
/who
```

to view currently online users.

---

# File Sharing

NetConnect supports file sharing inside chat rooms.

The client sends file information to the server using the Socket.IO `file_upload` event.

The server:

1. Validates the user and room.
2. Receives the file data.
3. Decodes the Base64 data.
4. Generates a safer stored filename.
5. Saves the file inside the `uploads/` directory.
6. Generates a URL for the uploaded file.
7. Notifies users in the room.

Files are therefore shared through the same real-time communication system used for chat.

---

# Moderation System

Administrators have additional moderation capabilities.

## Mute

An administrator can mute a user:

```text
/mute username
```

A muted user cannot send chat messages.

## Unmute

```text
/unmute username
```

This removes the mute status.

## Ban

```text
/ban username
```

A banned user is prevented from chatting and is disconnected from active sessions.

## Unban

```text
/unban username
```

This removes the user's banned status.

## Kick

```text
/kick username
```

This disconnects the selected user.

Unlike a permanent ban, kicking is intended as a session-level administrative action.

---

# Room Management

Administrators can manage rooms using commands.

## Create a Room

```text
/create room_name
```

Example:

```text
/create networking
```

## Delete a Room

```text
/delete room_name
```

## Lock a Room

```text
/lock room_name
```

A locked room requires authorization before a student can join.

## Unlock a Room

```text
/unlock room_name
```

This removes the room restriction.

---

# Locked Room Access

Students can request access to a locked room.

For example:

```text
/request networking
```

The request is sent to the server and added to the pending request queue.

An administrator can then approve or deny the request.

### Approve

```text
/approve username room_name
```

### Deny

```text
/deny username room_name
```

This demonstrates an access-control workflow between clients and the server.

---

# Appeal System

NetConnect contains an appeal mechanism for users who have been banned or kicked.

A user can access:

```text
/appeal
```

and submit a reason for their appeal.

The appeal is stored by the application and connected administrators are notified in real time.

Administrators can view submitted appeals and communicate with users through an appeal chat.

The system supports communication between:

```text
Student ←→ Administrator
```

for the appeal process.

---

# Available Commands

## Student Commands

| Command           | Description                 |
| ----------------- | --------------------------- |
| `/help`           | Displays available commands |
| `/who`            | Displays online users       |
| `/leave`          | Leaves the current room     |
| `/request <room>` | Requests access to a room   |

Example:

```text
/request networking
```

---

## Administrator Commands

| Command                  | Description                     |
| ------------------------ | ------------------------------- |
| `/help`                  | Displays administrator commands |
| `/who`                   | Displays online users           |
| `/create <room>`         | Creates a new room              |
| `/delete <room>`         | Deletes a room                  |
| `/lock <room>`           | Locks a room                    |
| `/unlock <room>`         | Unlocks a room                  |
| `/mute <user>`           | Mutes a user                    |
| `/unmute <user>`         | Unmutes a user                  |
| `/ban <user>`            | Bans a user                     |
| `/unban <user>`          | Unbans a user                   |
| `/kick <user>`           | Kicks a user                    |
| `/approve <user> <room>` | Approves room access            |
| `/deny <user> <room>`    | Denies room access              |

Example:

```text
/ban user1
```

---

# Technology Stack

## Backend

* Python
* Flask
* Flask-SocketIO
* Eventlet
* Bcrypt

The project's current `requirements.txt` specifies:

```text
Flask>=2.0
flask-socketio>=5.3.2
eventlet>=0.33.0
bcrypt>=4.0.1
```

---

## Frontend

The Flask application uses:

* HTML
* CSS
* JavaScript
* Socket.IO client-side communication

The Flask application is configured to use:

```text
templates/
static/
```

for the web interface.

---

## Networking

The project demonstrates:

* Client-server communication
* HTTP
* Real-time socket communication
* Socket.IO rooms
* Broadcasting
* Connected-client tracking
* Network-accessible server deployment
* Ngrok tunneling

---

## Storage

The application uses local file-based storage.

The backend maintains:

```text
data/
├── users.json
├── rooms.json
├── appeals.json
├── messages/
└── appeal_chats/

uploads/
```

The application automatically creates required data directories when necessary.

---

# Project Architecture

The overall architecture can be represented as:

```text
                 ┌─────────────────────┐
                 │      Web Client     │
                 │ HTML/CSS/JavaScript │
                 └──────────┬──────────┘
                            │
                    HTTP / Socket.IO
                            │
                            ▼
                 ┌─────────────────────┐
                 │   Flask Server      │
                 │                     │
                 │ Authentication      │
                 │ Sessions            │
                 │ REST Routes         │
                 │ Socket.IO           │
                 │ Access Control      │
                 └──────────┬──────────┘
                            │
                ┌───────────┼────────────┐
                │           │            │
                ▼           ▼            ▼
           ┌────────┐  ┌─────────┐  ┌──────────┐
           │ Users  │  │  Rooms  │  │ Messages │
           │ JSON   │  │  JSON   │  │  Files   │
           └────────┘  └─────────┘  └──────────┘
```

---

# Project Structure

A typical project structure is:

```text
NetConnect/
│
├── app.py
├── requirements.txt
├── start_chat.sh
│
├── templates/
│   ├── login.html
│   ├── chat.html
│   ├── appeal.html
│   ├── appeal_chat.html
│   └── appeal_table.html
│
├── static/
│   ├── css/
│   ├── js/
│   └── ...
│
├── data/
│   ├── users.json
│   ├── rooms.json
│   ├── appeals.json
│   ├── messages/
│   └── appeal_chats/
│
├── uploads/
│
└── README.md
```

> The exact frontend files may vary depending on the version of the project.

---

# Prerequisites

Before running the project, install the following:

### Required

* Python 3.x
* pip
* Git

### Optional

* Ngrok

Ngrok is required only if you want to make the local server accessible through a public URL.

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/sriramm84/NetConnect.git
```

Move into the project:

```bash
cd NetConnect
```

---

# 2. Create a Virtual Environment

### Windows

```powershell
python -m venv venv
```

Activate it:

```powershell
venv\Scripts\activate
```

If PowerShell blocks script execution, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again:

```powershell
venv\Scripts\activate
```

---

### Linux / macOS

```bash
python3 -m venv venv
```

Activate:

```bash
source venv/bin/activate
```

---

# 3. Install Dependencies

Run:

```bash
pip install -r requirements.txt
```

The dependencies include Flask, Flask-SocketIO, Eventlet, and Bcrypt.

---

# Running the Application

After installing the dependencies, run:

```bash
python app.py
```

The application starts on:

```text
http://localhost:5002
```

Open your browser and visit:

```text
http://localhost:5002
```

---

# Running on Your Local Network

The Flask-SocketIO server is configured to listen on:

```text
0.0.0.0
```

and port:

```text
5002
```

Therefore, if your computer and another device are connected to the same network, you can use your computer's local IP address:

```text
http://YOUR_LOCAL_IP:5002
```

For example:

```text
http://192.168.1.10:5002
```

The exact IP address depends on your local network configuration.

---

# Running with Ngrok

The project contains a script:

```text
start_chat.sh
```

The script:

1. Stops existing Flask and Ngrok processes.
2. Starts `app.py`.
3. Starts an Ngrok tunnel.
4. Creates a tunnel to port `5002`.
5. Retrieves the public Ngrok URL.
6. Displays the URL in the terminal.

The relevant configuration is:

```text
ngrok http 5002
```

---

## Linux / macOS / WSL / Git Bash

Make the script executable:

```bash
chmod +x start_chat.sh
```

Then run:

```bash
./start_chat.sh
```

The script will attempt to display a public URL such as:

```text
https://xxxxx.ngrok-free.dev
```

You can share this URL with other users so they can access the application.

---

# Running Ngrok Manually

If you don't want to use the startup script, first start Flask:

```bash
python app.py
```

Then open another terminal and run:

```bash
ngrok http 5002
```

Ngrok will provide a public forwarding URL.

---

# Windows Note

`start_chat.sh` is a Bash shell script.

If you are using Windows PowerShell, the simplest method is:

### Terminal 1

```powershell
python app.py
```

### Terminal 2

```powershell
ngrok http 5002
```

Alternatively, run `start_chat.sh` through **Git Bash**, WSL, or another Bash-compatible environment.

---

# First Run

When the application starts, it creates required directories and default data files if they do not already exist.

The application initializes a default `general` room.

User data is stored in:

```text
data/users.json
```

Room information is stored in:

```text
data/rooms.json
```

Appeal information is stored in:

```text
data/appeals.json
```

Room message logs are stored under:

```text
data/messages/
```

Appeal chat history is stored under:

```text
data/appeal_chats/
```

Uploaded files are stored under:

```text
uploads/
```

---

# Authentication Flow

The authentication flow works as follows:

```text
                 ┌──────────────┐
                 │     User     │
                 └──────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │    Sign Up    │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Password Hash │
                │    Bcrypt     │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │  users.json   │
                └───────────────┘


                        OR


                ┌───────────────┐
                │     Login     │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Verify User   │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Check Password│
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Check Status  │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │ Create Session│
                └───────────────┘
```

---

# Message Flow

A normal chat message follows this process:

```text
User enters message
        │
        ▼
Socket.IO Client
        │
        ▼
Flask-SocketIO Server
        │
        ├── Check login
        ├── Check ban status
        ├── Check mute status
        ├── Check room
        │
        ▼
Save message
        │
        ▼
Broadcast to Socket.IO room
        │
        ▼
All connected room members
```

---

# Data Persistence

NetConnect uses local files rather than an external database.

### Users

```text
data/users.json
```

Stores user-related information such as:

* Username
* Hashed password
* Role
* Ban status
* Mute status
* Approved rooms

### Rooms

```text
data/rooms.json
```

Stores:

* Room names
* Locked status
* Room members

### Messages

```text
data/messages/
```

Stores room-specific message logs.

### Appeals

```text
data/appeals.json
```

Stores submitted appeal information.

### Appeal Chat

```text
data/appeal_chats/
```

Stores administrator/student appeal conversations.

### Uploaded Files

```text
uploads/
```

Stores files shared through the chat system.

---

# Security Considerations

This project is intended primarily as an educational Computer Networks project.

Before deploying it publicly, several security improvements should be made.

## 1. Change the Flask Secret Key

The current source contains a development secret key.

For production use, replace it with a strong random secret and preferably load it from an environment variable.

Example:

```text
FLASK_SECRET_KEY=<your-secure-secret>
```

Do not commit production secrets to GitHub.

---

## 2. Do Not Commit Sensitive Data

Do not upload:

```text
.env
passwords
API keys
Ngrok authentication tokens
private keys
production credentials
```

Use `.gitignore` where appropriate.

---

## 3. Change Default Credentials

The application source initializes a default administrator account when the user database does not exist.

Before using the project outside a controlled development environment, replace the default administrative credential mechanism with a secure configuration and change any default credentials.

---

## 4. File Upload Security

For production deployment, file uploads should additionally implement:

* File type validation
* Maximum file size
* Malware scanning
* Content validation
* Stronger filename validation
* Access control
* Secure storage

---

## 5. Production Deployment

The development configuration should not be considered production-ready.

For production deployment, consider:

* HTTPS
* Secure cookies
* Environment variables
* Production WSGI configuration
* Reverse proxy
* Database-backed persistence
* Rate limiting
* Strong authentication
* Input validation

---

# Troubleshooting

## Flask command not found

Instead of:

```bash
flask run
```

use:

```bash
python app.py
```

The project directly starts the Socket.IO server from `app.py`.

---

## Port 5002 already in use

The application uses:

```text
5002
```

If another process is using this port, stop that process or change the port configuration in `app.py`.

---

## ModuleNotFoundError

For example:

```text
ModuleNotFoundError: No module named 'flask_socketio'
```

Run:

```bash
pip install -r requirements.txt
```

Make sure your virtual environment is activated.

---

## Ngrok does not start

Check whether Ngrok is installed:

```bash
ngrok version
```

If it is not installed, install Ngrok and configure your account as required.

Then run:

```bash
ngrok http 5002
```

---

## `start_chat.sh` does not work on Windows

The script uses Bash commands such as:

```text
pkill
sleep
curl
```

Therefore, run it through:

* Git Bash
* WSL
* Linux
* macOS

On Windows PowerShell, use:

```powershell
python app.py
```

and in another terminal:

```powershell
ngrok http 5002
```

---

# Future Enhancements

Possible future improvements include:

* PostgreSQL/MySQL database integration
* Redis for scalable Socket.IO messaging
* End-to-end encryption
* HTTPS deployment
* JWT-based authentication
* Password reset functionality
* Email verification
* User profile management
* Message search
* Message deletion/editing
* Typing indicators
* Read receipts
* Private messaging
* Group management
* Advanced administrator dashboard
* Improved file management
* File type and size restrictions
* Docker deployment
* Cloud deployment
* Horizontal scaling
* Comprehensive logging
* Automated testing

---

# Learning Outcomes

This project demonstrates practical concepts from **Computer Networks and distributed communication systems**, including:

* Client-server architecture
* Network communication
* HTTP request/response
* Real-time communication
* Socket-based communication
* Broadcasting
* Multi-client communication
* Session management
* Access control
* Network-accessible services
* Public tunneling using Ngrok
* Concurrent client connections

It also provides practical experience with Python web development and real-time event-driven communication.

---

# Contributing

Contributions are welcome.

To contribute:

1. Fork the repository.
2. Create a new branch.

```bash
git checkout -b feature/your-feature
```

3. Make your changes.
4. Commit your changes.

```bash
git add .
git commit -m "Add new feature"
```

5. Push your branch.

```bash
git push origin feature/your-feature
```

6. Create a Pull Request.

---

# License

This project is intended for educational and academic purposes.

If you plan to distribute or deploy the project commercially, add an appropriate open-source license to the repository.

---

# Author

**Sri Ram**

GitHub:

```text
https://github.com/sriramm84
```

Project:

```text
https://github.com/sriramm84/NetConnect
```

---

# Quick Start

For experienced users, the complete setup is:

```bash
git clone https://github.com/sriramm84/NetConnect.git
cd NetConnect

python -m venv venv
```

### Windows

```powershell
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Linux / macOS

```bash
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://localhost:5002
```

For public access:

```bash
ngrok http 5002
```

---

## Project Summary

**NetConnect** is a real-time network communication system that combines Flask's web server capabilities with Flask-SocketIO's event-driven communication model.

It provides authentication, role-based access control, real-time chat rooms, online-user tracking, file sharing, administrative moderation, locked-room access management, and an appeal communication system.

The project demonstrates how networking concepts can be applied to build a functional multi-user real-time communication platform.
