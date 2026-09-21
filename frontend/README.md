# AI Gaming Copilot - Frontend Foundation

Modern, responsive React + Vite client for the AI Gaming Copilot + Gaming Second Brain hackathon project.

## 🎯 Purpose

The frontend is an intelligent productivity and gaming assistant dashboard. It allows gamers to:
- Securely register and authenticate accounts via JWT
- Track competitive and casual gaming sessions
- Maintain a Second Brain of gameplay highlights, strategies, and lessons
- Queue and prioritize real-world productivity tasks to smoothly transition from gaming sessions into focused work

## 🛠 Tech Stack

- **Framework**: React 18
- **Build Tool**: Vite 6
- **Language**: JavaScript (ESM)
- **Routing**: React Router DOM (v6)
- **HTTP Client**: Native Fetch API with centralized `ApiClient` wrapper
- **Styling**: Pure CSS design tokens with gaming-inspired dark SaaS theme

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/            # Reusable UI & structural components
│   │   ├── EmptyState.jsx     # Card/list placeholder component
│   │   ├── ErrorMessage.jsx   # Error banner with retry trigger
│   │   ├── HealthBadge.jsx    # Live backend/database health indicator
│   │   ├── LoadingSpinner.jsx # Centered spinner component
│   │   ├── ProtectedRoute.jsx # Guard for authenticated routes
│   │   └── PublicRoute.jsx    # Guard redirecting authed users to dashboard
│   ├── context/
│   │   └── AuthContext.jsx    # Authentication provider & startup session verification
│   ├── hooks/
│   │   └── useAuth.js         # Custom hook for accessing AuthContext
│   ├── layouts/
│   │   └── AppLayout.jsx      # Authenticated layout with sidebar & mobile menu
│   ├── pages/
│   │   ├── Dashboard.jsx      # Gaming Overview page
│   │   ├── Login.jsx          # User sign-in page
│   │   ├── Memories.jsx       # Gaming Second Brain page
│   │   ├── Sessions.jsx       # Gaming Sessions page
│   │   ├── Signup.jsx         # User registration page
│   │   └── Tasks.jsx          # Productivity Tasks page
│   ├── services/
│   │   └── api.js             # Centralized fetch client with automatic JWT headers
│   ├── tests/
│   │   └── frontend-integration.test.js # E2E test against live backend & PostgreSQL
│   ├── utils/
│   │   └── constants.js       # Global constants (token storage key, fallback API URL)
│   ├── App.jsx                # Application root with router configuration
│   ├── index.css              # Design system tokens & global styling
│   └── main.jsx               # React DOM entry point
├── .env.example               # Environment variables template
├── .gitignore                 # Ignore rules for node_modules, build, and local envs
├── index.html                 # HTML entry template
├── package.json               # Dependencies and scripts
├── vite.config.js             # Vite configuration
└── README.md                  # Frontend documentation
```

## ⚙️ Environment Variables

Create `.env` in the `frontend/` directory (or copy from `.env.example`):

```bash
VITE_API_BASE_URL=http://localhost:5000/api
```

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Base endpoint URL for the Express backend REST API | `http://localhost:5000/api` |

## 🚀 Getting Started

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
The application will launch on `http://localhost:5173`.

### 3. Production Build & Preview
```bash
npm run build
npm run preview
```

### 4. Run Integration Tests
```bash
npm test
```
Runs the automated end-to-end integration test suite verifying Vite dev serving, live backend communication, user signup, login, session restoration, and protected route access.

## 🛣 Route Structure

| Route | Access | Component | Purpose |
|---|---|---|---|
| `/` | Public | `RootRedirect` | Redirects to `/dashboard` if authenticated; otherwise `/login` |
| `/login` | Public (Unauthed) | `Login` | Sign in with email and password |
| `/signup` | Public (Unauthed) | `Signup` | Register display name, email, and password |
| `/dashboard` | Protected | `Dashboard` | Gaming Overview metrics and copilot status |
| `/sessions` | Protected | `Sessions` | Gaming Sessions tracker |
| `/memories` | Protected | `Memories` | Gaming Second Brain tactical knowledge base |
| `/tasks` | Protected | `Tasks` | Productivity task list & post-game transition |

## 🔒 Authentication Behavior

- **State Persistence**: The JWT is stored in `localStorage` under `ai_gaming_copilot_token`. Passwords are never logged or stored client-side.
- **Startup Verification**: On application mount, `AuthContext` reads the stored token and calls `GET /api/auth/me`. If valid, the user state is restored. If expired or invalid, the token is automatically wiped and the user is redirected to `/login`.
- **Automatic Authorization**: The centralized `api.js` client automatically attaches `Authorization: Bearer <token>` to all outgoing requests.
- **Protected Routing**: Attempting to navigate directly to `/dashboard`, `/sessions`, `/memories`, or `/tasks` while unauthenticated immediately redirects to `/login`.
