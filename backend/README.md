# AI Gaming Copilot - Backend & Database

Core backend service for the AI Gaming Copilot + Gaming Second Brain hackathon project.

## 🛠 Tech Stack

- **Runtime**: Node.js
- **Framework**: Express.js
- **Database**: PostgreSQL (via `pg` connection pool)
- **Utilities**: `dotenv`, `cors`
- **Development**: `nodemon`

## 📁 Directory Structure

```
backend/
├── src/
│   ├── controllers/            # Request handlers and response formatting
│   │   └── health.controller.js # Health check endpoint handler (with DB status)
│   ├── routes/                 # API route definitions
│   │   ├── health.routes.js    # Health check route
│   │   └── index.js            # Central route aggregator (/api)
│   ├── middleware/             # Express middlewares
│   │   └── error.middleware.js # Centralized error & 404 handlers
│   ├── services/               # Business logic & external services (sessions, AI, tasks)
│   │   └── .gitkeep
│   ├── db/                     # PostgreSQL database layer
│   │   ├── migrations/         # Plain SQL migration files
│   │   │   └── 001_initial_schema.sql
│   │   ├── check-connection.js # CLI DB connection test utility
│   │   ├── index.js            # pg.Pool connection module & helpers
│   │   ├── migrate.js          # Migration runner (tracks applied in schema_migrations)
│   │   └── verify-schema.js    # Schema inspection utility
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
| `DATABASE_URL` | `postgresql://username:password@localhost:5432/ai_gaming_copilot` | PostgreSQL connection string |

## 🚀 Scripts

- **`npm run dev`**: Starts the development server with hot reload via `nodemon`.
- **`npm start`**: Runs the server in production mode using standard `node`.
- **`npm run db:check`**: Tests connectivity to the PostgreSQL database.
- **`npm run db:migrate`**: Executes pending SQL migrations in `src/db/migrations/` sequentially.

## 🗄️ Database Schema & Tables

- **`users`**: User accounts (`id`, `name`, `email` [unique], `password_hash`, timestamps).
- **`games`**: Games library catalog (`id`, `name`, `platform`, `created_at`).
- **`gaming_sessions`**: Game sessions (`id`, `user_id` [FK users], `game_id` [FK games], `started_at`, `ended_at`, `duration`, `score`, `performance`, `notes`, timestamps).
- **`gaming_memories`**: Long-term Second Brain memories (`id`, `user_id` [FK users], `session_id` [FK gaming_sessions, nullable], `title`, `summary`, `memory_type`, `metadata` [JSONB], timestamps).
- **`tasks`**: Post-session transition tasks (`id`, `user_id` [FK users], `title`, `description`, `priority`, `due_date`, `estimated_minutes`, `completed`, timestamps).
- **`schema_migrations`**: Tracks applied migrations idempotently (`id`, `name`, `applied_at`).

## 📡 API Endpoints

### Health Check

- **Endpoint**: `GET /api/health`
- **Description**: Verifies backend availability and PostgreSQL database connectivity.
- **Sample Response**:

```json
{
  "success": true,
  "message": "AI Gaming Copilot API is running",
  "database": "connected"
}
```
