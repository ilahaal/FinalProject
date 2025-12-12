# ☕ BrewHaven Café — Cloud-Native Coffee Shop

**BrewHaven Café** is a cloud-native coffee shop application that demonstrates a modern containerized web architecture using Microsoft Azure.

The application allows customers to browse a café menu, filter by category, search items, manage a basket, and place orders — all backed by a managed NoSQL database.

---

## 🚀 Technology Stack

- **FastAPI (Python)** — Backend API + frontend HTML/JS
- **Azure Cosmos DB (NoSQL)** — Products, cart, and orders
- **Docker** — Containerized application runtime
- **Azure Container Instances (ACI)** — Cloud deployment
- **Docker Hub** — Container image registry
- **GitHub** — Source control

The application follows a **single-container architecture**, where FastAPI serves both the backend API and the frontend UI.

---

## ✨ Features

### ☕ Coffee Shop Menu
- Coffees, specialty drinks, pastries, and desserts
- Category filtering
- Search by item name or category

### 🧺 Basket & Orders
- Add, update, and remove items from basket
- Automatic total calculation
- Place orders stored in Cosmos DB

### 🔐 Authentication
- Lightweight JWT-based login
- Protected cart and order endpoints

### ☁️ Cloud-Native Design
- Stateless container
- Configuration via environment variables
- Automatic database seeding on first startup

---

## 🏗 Architecture Overview

Browser
↓
Azure Container Instance
↓
FastAPI Application
↓
Azure Cosmos DB (NoSQL)

yaml
Copy code

### Components
- **Frontend + Backend**: Served from FastAPI
- **Database**: Azure Cosmos DB (SQL API)
- **Hosting**: Azure Container Instance (Linux)
- **Container Registry**: Docker Hub

---

## 📁 Project Structure

brewhaven-cafe/
├── main.py
├── Dockerfile
├── requirements.txt
├── README.md

yaml
Copy code

---

## 🧪 Local Development (without Azure)

### 1. Install dependencies
```bash
pip install -r requirements.txt
2. Run locally
bash
Copy code
uvicorn main:app --reload
Open in browser:

cpp
Copy code
http://127.0.0.1:8000/
Note: Without Cosmos DB environment variables, database-backed features will be disabled.

🐳 Docker Usage
Build image locally
bash
Copy code
docker build -t brewhaven-api:local .
Run container locally
bash
Copy code
docker run --rm -p 8080:80 brewhaven-api:local
Open:

arduino
Copy code
http://localhost:8080/
☁️ Azure Deployment
The application is deployed using Azure Container Instances and connects to Azure Cosmos DB.

Required environment variables:
COSMOS_ENDPOINT

COSMOS_KEY

JWT_SECRET_KEY

On first startup, the application automatically seeds the café menu into Cosmos DB.

🔍 API Endpoints
Method	Endpoint	Description
GET	/	Frontend UI
GET	/health	Health & build info
POST	/auth/login	Login (JWT)
GET	/api/v1/products	List menu items
GET	/api/v1/categories	List categories
GET	/api/v1/cart	Get basket
POST	/api/v1/cart/items	Add/update basket item
DELETE	/api/v1/cart/items/{id}	Remove basket item
POST	/api/v1/orders	Place order
GET	/api/v1/orders	List orders

👤 Author
Ilaha Alakbarova
CSP451 Final Project
