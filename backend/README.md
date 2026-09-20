# AI Gaming Copilot - Backend & Database

Core backend service for the AI Gaming Copilot + Gaming Second Brain hackathon project.

## 🛠 Tech Stack

- **Runtime**: Node.js
- **Framework**: Express.js
- **Database**: PostgreSQL (via `pg` connection pool)
- **Authentication**: JWT (`jsonwebtoken`) & `bcryptjs`
- **Utilities**: `dotenv`, `cors`
- **Development**: `nodemon`

## 📁 Directory Structure

```
backend/
├── src/
│   ├── controllers/            # Request handlers and response formatting
│   │   ├── auth.controller.js  # Signup, login, and profile handlers
│   │   └── health.controller.js # Health check endpoint handler (with DB status)
│   ├── routes/                 # API route definitions
│   │   ├── auth.routes.js      # Authentication endpoints (/api/auth)
│   │   ├── health.routes.js    # Health check route
│   │   └── index.js            # Central route aggregator (/api)
│   ├── middleware/             # Express middlewares
│   │   ├── auth.middleware.js  # JWT Bearer token authentication middleware
│   │   └── error.middleware.js # Centralized error & 404 handlers
│   ├── services/               # Business logic & data operations
│   │   └── auth.service.js     # User registration, password hashing, verification
│   ├── utils/                  # Reusable utility functions
│   │   ├── jwt.utils.js        # JWT signing & verification helpers
│   │   └── validation.utils.js # Email & password validation utilities
│   ├── db/                     # PostgreSQL database layer
│   │   ├── migrations/         # Plain SQL migration files
│   │   │   └── 001_initial_schema.sql
│   │   ├── check-connection.js # CLI DB connection test utility
│   │   ├── index.js            # pg.Pool connection module & helpers
│   │   ├── migrate.js          # Migration runner (tracks applied in schema_migrations)
│   │   └── verify-schema.js    # Schema inspection utility
│   ├── tests/                  # Automated test suites
│   │   └── auth.test.js        # Full authentication & health test suite (15 tests)
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
| `JWT_SECRET` | `replace_with_a_secure_secret` | Secret key for signing and verifying JWTs |
| `JWT_EXPIRES_IN` | `7d` | Token validity duration |

## 🚀 Scripts

- **`npm run dev`**: Starts the development server with hot reload via `nodemon`.
- **`npm start`**: Runs the server in production mode using standard `node`.
- **`npm test`**: Runs the automated authentication test suite (15 assertions).
- **`npm run db:check`**: Tests connectivity to the PostgreSQL database.
- **`npm run db:migrate`**: Executes pending SQL migrations in `src/db/migrations/` sequentially.

## 🗄️ Database Schema & Tables

- **`users`**: User accounts (`id` [UUID PK], `name`, `email` [unique], `password_hash`, timestamps).
- **`games`**: Games library catalog (`id` [UUID PK], `name`, `platform`, `created_at`).
- **`gaming_sessions`**: Game sessions (`id` [UUID PK], `user_id` [FK users], `game_id` [FK games], `started_at`, `ended_at`, `duration`, `score`, `performance`, `notes`, timestamps).
- **`gaming_memories`**: Long-term Second Brain memories (`id` [UUID PK], `user_id` [FK users], `session_id` [FK gaming_sessions, nullable], `title`, `summary`, `memory_type`, `metadata` [JSONB], timestamps).
- **`tasks`**: Post-session transition tasks (`id` [UUID PK], `user_id` [FK users], `title`, `description`, `priority`, `due_date`, `estimated_minutes`, `completed`, timestamps).
- **`schema_migrations`**: Tracks applied migrations idempotently (`id`, `name`, `applied_at`).

## 📡 API Endpoints

### Authentication

#### Register User
- **Endpoint**: `POST /api/auth/signup`
- **Body**:
  ```json
  {
    "name": "Lokesh",
    "email": "lokesh@example.com",
    "password": "example-password"
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "success": true,
    "message": "User registered successfully",
    "user": {
      "id": "f4af628d-4fd5-4bf8-8ca9-48611bb77cfa",
      "name": "Lokesh",
      "email": "lokesh@example.com"
    }
  }
  ```

#### Login
- **Endpoint**: `POST /api/auth/login`
- **Body**:
  ```json
  {
    "email": "lokesh@example.com",
    "password": "example-password"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Login successful",
    "token": "eyJhbGciOi...",
    "user": {
      "id": "f4af628d-4fd5-4bf8-8ca9-48611bb77cfa",
      "name": "Lokesh",
      "email": "lokesh@example.com"
    }
  }
  ```

#### Current User Profile (Protected)
- **Endpoint**: `GET /api/auth/me`
- **Header**: `Authorization: Bearer <token>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "user": {
      "id": "f4af628d-4fd5-4bf8-8ca9-48611bb77cfa",
      "name": "Lokesh",
      "email": "lokesh@example.com"
    }
  }
  ```

### System Health

- **Endpoint**: `GET /api/health`
- **Description**: Verifies backend availability and PostgreSQL database connectivity.
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "AI Gaming Copilot API is running",
    "database": "connected"
  }
  ```
