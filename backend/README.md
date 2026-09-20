# AI Gaming Copilot - Backend Foundation

Core backend service for the AI Gaming Copilot + Gaming Second Brain hackathon project.

## 🛠 Tech Stack

- **Runtime**: Node.js
- **Framework**: Express.js
- **Utilities**: `dotenv`, `cors`
- **Development**: `nodemon`

## 📁 Directory Structure

```
backend/
├── src/
│   ├── controllers/            # Request handlers and response formatting
│   │   └── health.controller.js # Health check endpoint handler
│   ├── routes/                 # API route definitions
│   │   ├── health.routes.js    # Health check route
│   │   └── index.js            # Central route aggregator (/api)
│   ├── middleware/             # Express middlewares
│   │   └── error.middleware.js # Centralized error & 404 handlers
│   ├── services/               # Business logic & external services (sessions, AI, tasks)
│   │   └── .gitkeep
│   ├── db/                     # Database connection pool & queries (PostgreSQL planned)
│   │   └── .gitkeep
│   └── server.js               # Express application entry point & server bootstrap
├── .env.example                # Template for environment variables
├── .gitignore                  # Backend-specific ignore rules
├── package.json                # Project dependencies & scripts
└── README.md                   # Backend documentation
```

## ⚙️ Environment Variables

Copy `.env.example` to `.env` before starting the server:

```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `5000` | Port on which the Express server listens |
| `NODE_ENV` | `development` | Environment mode (`development`, `production`, `test`) |

## 🚀 Scripts

- **`npm run dev`**: Starts the development server with hot reload via `nodemon`.
- **`npm start`**: Runs the server in production mode using standard `node`.

## 📡 API Endpoints

### Health Check

- **Endpoint**: `GET /api/health`
- **Description**: Verifies backend availability and service status.
- **Sample Response**:

```json
{
  "success": true,
  "message": "AI Gaming Copilot API is running"
}
```
