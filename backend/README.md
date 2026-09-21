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
│   │   ├── game.controller.js  # Game catalog handlers
│   │   ├── health.controller.js # Health check endpoint handler (with DB status)
│   │   ├── memory.controller.js # Gaming Second Brain memory handlers
│   │   └── session.controller.js # Gaming session lifecycle handlers
│   ├── routes/                 # API route definitions
│   │   ├── auth.routes.js      # Authentication endpoints (/api/auth)
│   │   ├── game.routes.js      # Game endpoints (/api/games)
│   │   ├── health.routes.js    # Health check route
│   │   ├── index.js            # Central route aggregator (/api)
│   │   ├── memory.routes.js    # Gaming memory endpoints (/api/memories)
│   │   └── session.routes.js   # Gaming session endpoints (/api/sessions)
│   ├── middleware/             # Express middlewares
│   │   ├── auth.middleware.js  # JWT Bearer token authentication middleware
│   │   └── error.middleware.js # Centralized error & 404 handlers
│   ├── services/               # Business logic & data operations
│   │   ├── auth.service.js     # User registration, password hashing, verification
│   │   ├── game.service.js     # Game creation and catalog queries
│   │   ├── memory.service.js   # Memory creation, JSONB metadata, session joins, ownership
│   │   └── session.service.js  # Session creation, duration calculation, ownership enforcement
│   ├── utils/                  # Reusable utility functions
│   │   ├── jwt.utils.js        # JWT signing & verification helpers
│   │   └── validation.utils.js # Email, UUID, game, session, memory, and pagination validation
│   ├── db/                     # PostgreSQL database layer
│   │   ├── migrations/         # Plain SQL migration files
│   │   │   └── 001_initial_schema.sql
│   │   ├── check-connection.js # CLI DB connection test utility
│   │   ├── index.js            # pg.Pool connection module & helpers
│   │   ├── migrate.js          # Migration runner (tracks applied in schema_migrations)
│   │   └── verify-schema.js    # Schema inspection utility
│   ├── tests/                  # Automated test suites
│   │   ├── auth.test.js        # Authentication & health test suite (15 tests)
│   │   ├── memory.test.js      # Gaming memory test suite (22 tests)
│   │   └── session.test.js     # Gaming session & games test suite (20 tests)
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
- **`npm test`**: Runs the full automated test suite (57 assertions across auth, session, and memory suites).
- **`npm run db:check`**: Tests connectivity to the PostgreSQL database.
- **`npm run db:migrate`**: Executes pending SQL migrations in `src/db/migrations/` sequentially.

## 🗄️ Database Schema & Tables

- **`users`**: User accounts (`id` [UUID PK], `name`, `email` [unique], `password_hash`, timestamps).
- **`games`**: Games library catalog (`id` [UUID PK], `name`, `platform`, `created_at`).
- **`gaming_sessions`**: Game sessions (`id` [UUID PK], `user_id` [FK users], `game_id` [FK games], `started_at`, `ended_at`, `duration`, `score`, `performance`, `notes`, timestamps).
- **`gaming_memories`**: Long-term Second Brain memories (`id` [UUID PK], `user_id` [FK users], `session_id` [FK gaming_sessions, nullable], `title`, `summary`, `memory_type`, `metadata` [JSONB], timestamps).
- **`tasks`**: Post-session transition tasks (`id` [UUID PK], `user_id` [FK users], `title`, `description`, `priority`, `due_date`, `estimated_minutes`, `completed`, timestamps).
- **`schema_migrations`**: Tracks applied migrations idempotently (`id`, `name`, `applied_at`).

---

## 📡 API Endpoints

### 1. Authentication (`/api/auth`)

#### Register User
- **Method / Path**: `POST /api/auth/signup`
- **Auth Required**: No
- **Request Body**:
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
- **Method / Path**: `POST /api/auth/login`
- **Auth Required**: No
- **Request Body**:
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
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "f4af628d-4fd5-4bf8-8ca9-48611bb77cfa",
      "name": "Lokesh",
      "email": "lokesh@example.com"
    }
  }
  ```

#### Current User Profile
- **Method / Path**: `GET /api/auth/me`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
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

---

### 2. Games Catalog (`/api/games`)

#### Create Game
- **Method / Path**: `POST /api/games`
- **Auth Required**: No
- **Request Body**:
  ```json
  {
    "name": "Valorant",
    "platform": "PC"
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "success": true,
    "message": "Game created successfully",
    "game": {
      "id": "3d05f33f-d632-4acd-8671-9beb611549ab",
      "name": "Valorant",
      "platform": "PC",
      "createdAt": "2026-09-20T17:22:50.838Z"
    }
  }
  ```

#### Get All Games
- **Method / Path**: `GET /api/games`
- **Auth Required**: No
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "games": [
      {
        "id": "3d05f33f-d632-4acd-8671-9beb611549ab",
        "name": "Valorant",
        "platform": "PC",
        "createdAt": "2026-09-20T17:22:50.838Z"
      }
    ]
  }
  ```

---

### 3. Gaming Sessions (`/api/sessions`)

> 🔒 **Security Notice**: All session endpoints require a valid JWT via the header `Authorization: Bearer <token>`. Session ownership is strictly enforced: users can only view, update, end, or delete their own sessions. Accessing another user's session returns `404 Not Found`.

#### Start Gaming Session
- **Method / Path**: `POST /api/sessions`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Request Body**:
  ```json
  {
    "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
    "score": 1200,
    "performance": "Good",
    "notes": "Strong first half"
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "success": true,
    "message": "Gaming session started successfully",
    "session": {
      "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
      "gameName": "Valorant",
      "platform": "PC",
      "startedAt": "2026-09-20T17:22:50.857Z",
      "endedAt": null,
      "duration": null,
      "score": 1200,
      "performance": "Good",
      "notes": "Strong first half",
      "createdAt": "2026-09-20T17:22:50.857Z",
      "updatedAt": "2026-09-20T17:22:50.857Z"
    }
  }
  ```
- **Status Codes**:
  - `201 Created`: Session started successfully.
  - `400 Bad Request`: Invalid `gameId` UUID format or input validation error.
  - `404 Not Found`: Referenced `gameId` does not exist in the database.
  - `409 Conflict`: User already has an active session (`"An active gaming session already exists"`).

#### Get Active Session
- **Method / Path**: `GET /api/sessions/active`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK - Active Session Found)**:
  ```json
  {
    "success": true,
    "session": {
      "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
      "gameName": "Valorant",
      "platform": "PC",
      "startedAt": "2026-09-20T17:22:50.857Z",
      "endedAt": null,
      "duration": null,
      "score": 1200,
      "performance": "Good",
      "notes": "Strong first half",
      "createdAt": "2026-09-20T17:22:50.857Z",
      "updatedAt": "2026-09-20T17:22:50.857Z"
    }
  }
  ```
- **Response (200 OK - No Active Session)**:
  ```json
  {
    "success": true,
    "session": null
  }
  ```

#### Get User Sessions (Paginated)
- **Method / Path**: `GET /api/sessions?page=1&limit=20`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "sessions": [
      {
        "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
        "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
        "gameName": "Valorant",
        "platform": "PC",
        "startedAt": "2026-09-20T17:22:50.857Z",
        "endedAt": "2026-09-20T17:22:51.897Z",
        "duration": 1,
        "score": 1550,
        "performance": "Excellent",
        "notes": "Clutched round 24",
        "createdAt": "2026-09-20T17:22:50.857Z",
        "updatedAt": "2026-09-20T17:22:51.897Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 1,
      "totalPages": 1
    }
  }
  ```

#### Get Single Session
- **Method / Path**: `GET /api/sessions/:id`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "session": {
      "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
      "gameName": "Valorant",
      "platform": "PC",
      "startedAt": "2026-09-20T17:22:50.857Z",
      "endedAt": null,
      "duration": null,
      "score": 1200,
      "performance": "Good",
      "notes": "Strong first half"
    }
  }
  ```
- **Status Codes**:
  - `200 OK`: Found and returned.
  - `400 Bad Request`: Invalid UUID format.
  - `404 Not Found`: Session does not exist or belongs to another user.

#### Update Session
- **Method / Path**: `PATCH /api/sessions/:id`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Request Body** *(at least one field)*:
  ```json
  {
    "score": 1550,
    "performance": "Excellent",
    "notes": "Clutched round 24"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Gaming session updated successfully",
    "session": {
      "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "score": 1550,
      "performance": "Excellent",
      "notes": "Clutched round 24",
      "updatedAt": "2026-09-20T17:22:50.871Z"
    }
  }
  ```
- **Status Codes**:
  - `200 OK`: Updated successfully.
  - `400 Bad Request`: Invalid UUID or attempting to modify restricted fields (`userId`, `gameId`, etc.).
  - `404 Not Found`: Session does not exist or belongs to another user.

#### End Gaming Session
- **Method / Path**: `POST /api/sessions/:id/end`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Gaming session ended successfully",
    "session": {
      "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "startedAt": "2026-09-20T17:22:50.857Z",
      "endedAt": "2026-09-20T17:22:51.897Z",
      "duration": 1,
      "score": 1550,
      "performance": "Excellent",
      "notes": "Clutched round 24"
    }
  }
  ```
- **Status Codes**:
  - `200 OK`: Ended successfully with PostgreSQL-calculated duration in seconds.
  - `400 Bad Request`: Invalid UUID format.
  - `404 Not Found`: Session does not exist or belongs to another user.
  - `409 Conflict`: Session has already been ended.

#### Delete Gaming Session
- **Method / Path**: `DELETE /api/sessions/:id`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Gaming session deleted successfully"
  }
  ```
- **Status Codes**:
  - `200 OK`: Deleted successfully.
  - `400 Bad Request`: Invalid UUID format.
  - `404 Not Found`: Session does not exist or belongs to another user.

---

### 4. Gaming Second Brain Memories (`/api/memories`)

> 🧠 **Overview**: Gaming memories represent meaningful insights, tactics, highlights, and lessons from a player's gaming journey. These will be indexed and queried by the AI layer.
>
> 🔒 **Security Notice**: All memory endpoints require authentication via `Authorization: Bearer <token>`. Strict ownership is enforced:
> - Users can only view, update, or delete their own memories.
> - If `sessionId` is provided, the backend verifies that the session belongs to `req.user.id`. Attaching a memory to another user's session is blocked with `404 Not Found`.
> - Accessing another user's memory returns `404 Not Found`.

#### Create Gaming Memory
- **Method / Path**: `POST /api/memories`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Request Body**:
  ```json
  {
    "title": "Best Valorant session",
    "summary": "My strongest performance after a 20 minute warm-up.",
    "memoryType": "performance",
    "sessionId": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
    "metadata": {
      "map": "Haven",
      "kills": 28,
      "deaths": 14
    }
  }
  ```
- **Validation**:
  - `title`: Required, non-empty string, max 255 chars.
  - `memoryType`: Required, non-empty string, max 100 chars (e.g., `performance`, `tactics`, `highlight`, `note`).
  - `summary`: Optional string, max 5000 chars.
  - `sessionId`: Optional UUID. If supplied, session must exist and belong to `req.user.id` (404 if not found or not owned).
  - `metadata`: Optional plain JSON object. Arrays, primitives, or `null` are rejected with 400.
- **Response (201 Created)**:
  ```json
  {
    "success": true,
    "message": "Gaming memory created successfully",
    "memory": {
      "id": "121e10cb-82af-4b7b-8bf1-f6c461a307a1",
      "title": "Best Valorant session",
      "summary": "My strongest performance after a 20 minute warm-up.",
      "memoryType": "performance",
      "sessionId": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "metadata": {
        "map": "Haven",
        "kills": 28,
        "deaths": 14
      },
      "session": {
        "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
        "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
        "gameName": "Valorant",
        "platform": "PC",
        "startedAt": "2026-09-20T17:22:50.857Z",
        "endedAt": "2026-09-20T17:22:51.897Z",
        "duration": 1
      },
      "createdAt": "2026-09-21T04:34:25.694Z",
      "updatedAt": "2026-09-21T04:34:25.694Z"
    }
  }
  ```
- **Status Codes**:
  - `201 Created`: Memory created successfully.
  - `400 Bad Request`: Missing title/memoryType, invalid UUID format, or non-object metadata.
  - `401 Unauthorized`: Missing or invalid token.
  - `404 Not Found`: Referenced `sessionId` does not exist or belongs to another user.

#### Get Gaming Memories (Paginated & Filterable)
- **Method / Path**: `GET /api/memories`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Query Parameters**:
  - `page` (default: `1`, min: `1`)
  - `limit` (default: `20`, max: `100`)
  - `memoryType` (optional, e.g. `?memoryType=highlight`)
  - `sessionId` (optional UUID, e.g. `?sessionId=38a58273-3e28-4b9f-82d2-7a67515bf72d`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "memories": [
      {
        "id": "121e10cb-82af-4b7b-8bf1-f6c461a307a1",
        "title": "Best Valorant session",
        "summary": "My strongest performance after a 20 minute warm-up.",
        "memoryType": "performance",
        "sessionId": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
        "metadata": {
          "map": "Haven",
          "kills": 28,
          "deaths": 14
        },
        "session": {
          "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
          "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
          "gameName": "Valorant",
          "platform": "PC",
          "startedAt": "2026-09-20T17:22:50.857Z",
          "endedAt": "2026-09-20T17:22:51.897Z",
          "duration": 1
        },
        "createdAt": "2026-09-21T04:34:25.694Z",
        "updatedAt": "2026-09-21T04:34:25.694Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 1,
      "totalPages": 1
    }
  }
  ```
- **Status Codes**:
  - `200 OK`: Retrieved successfully.
  - `400 Bad Request`: Invalid pagination values or invalid `sessionId` UUID.
  - `401 Unauthorized`: Missing or invalid token.

#### Get Single Gaming Memory
- **Method / Path**: `GET /api/memories/:id`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "memory": {
      "id": "121e10cb-82af-4b7b-8bf1-f6c461a307a1",
      "title": "Best Valorant session",
      "summary": "My strongest performance after a 20 minute warm-up.",
      "memoryType": "performance",
      "sessionId": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "metadata": {
        "map": "Haven",
        "kills": 28,
        "deaths": 14
      },
      "session": {
        "id": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
        "gameId": "3d05f33f-d632-4acd-8671-9beb611549ab",
        "gameName": "Valorant",
        "platform": "PC",
        "startedAt": "2026-09-20T17:22:50.857Z",
        "endedAt": "2026-09-20T17:22:51.897Z",
        "duration": 1
      },
      "createdAt": "2026-09-21T04:34:25.694Z",
      "updatedAt": "2026-09-21T04:34:25.694Z"
    }
  }
  ```
- **Status Codes**:
  - `200 OK`: Found and returned.
  - `400 Bad Request`: Invalid UUID format.
  - `401 Unauthorized`: Missing or invalid token.
  - `404 Not Found`: Memory does not exist or belongs to another user.

#### Update Gaming Memory
- **Method / Path**: `PATCH /api/memories/:id`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Request Body** *(at least one field)*:
  ```json
  {
    "title": "Updated Valorant Session Strategy",
    "metadata": {
      "map": "Haven",
      "kills": 30,
      "deaths": 14,
      "ace": true
    }
  }
  ```
- **Allowed Fields**: `title`, `summary`, `memoryType`, `metadata`. Disallowed fields (`id`, `userId`, `sessionId`, `createdAt`) are rejected.
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Gaming memory updated successfully",
    "memory": {
      "id": "121e10cb-82af-4b7b-8bf1-f6c461a307a1",
      "title": "Updated Valorant Session Strategy",
      "summary": "My strongest performance after a 20 minute warm-up.",
      "memoryType": "performance",
      "sessionId": "38a58273-3e28-4b9f-82d2-7a67515bf72d",
      "metadata": {
        "map": "Haven",
        "kills": 30,
        "deaths": 14,
        "ace": true
      },
      "session": { ... },
      "createdAt": "2026-09-21T04:34:25.694Z",
      "updatedAt": "2026-09-21T04:34:25.789Z"
    }
  }
  ```
- **Status Codes**:
  - `200 OK`: Updated successfully.
  - `400 Bad Request`: Invalid UUID, non-object metadata, or disallowed fields.
  - `401 Unauthorized`: Missing or invalid token.
  - `404 Not Found`: Memory does not exist or belongs to another user.

#### Delete Gaming Memory
- **Method / Path**: `DELETE /api/memories/:id`
- **Auth Required**: Yes (`Authorization: Bearer <token>`)
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Gaming memory deleted successfully"
  }
  ```
- **Status Codes**:
  - `200 OK`: Deleted successfully.
  - `400 Bad Request`: Invalid UUID format.
  - `401 Unauthorized`: Missing or invalid token.
  - `404 Not Found`: Memory does not exist or belongs to another user.

---

### 5. System Health (`/api/health`)

- **Method / Path**: `GET /api/health`
- **Auth Required**: No
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "AI Gaming Copilot API is running",
    "database": "connected"
  }
  ```
