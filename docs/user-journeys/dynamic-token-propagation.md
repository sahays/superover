# User Journeys: Dynamic Token Propagation

## Personas

### 1. Alex, a New Developer
- **Context**: Just cloned the repo and ran `./scripts/dev-up.sh`.
- **Goal**: Wants to see the app working in their own sandbox GCP project.
- **Pain Point**: Doesn't want to deal with complex IAM settings or CLI login.

### 2. Sam, a Product Manager
- **Context**: Wants to demo the app to a client.
- **Goal**: Login with a corporate account and show generated image adapts immediately.

---

## User Journeys

### Journey 1: The "Zero-Config" Setup (Persona: Alex)
1. **Initial Access**: Alex opens `http://localhost:3000`. Instead of the dashboard, they see a "Welcome to Super Over Alchemy" landing page with a **Login with Google** button.
2. **Authentication**: Alex logs in. The browser requests scopes for `cloud-platform`.
3. **Onboarding Check**: After login, the API detects this is a new project. Alex is redirected to an **Onboarding & Verification** page.
4. **Automatic Provisioning**: Alex sees a checklist:
   - [x] API: Cloud Storage ... Enabled
   - [x] API: Firestore ... Enabled
   - [x] API: Vertex AI ... Enabling... Success!
   - [x] Storage: Creating bucket `alex-project-uploads`... Success!
5. **Dashboard Transition**: Once the checklist is green, the dashboard appears.
6. **Background Success**: Alex uploads an image. Even though the worker is a separate Docker container, it "just works" because it has inherited Alex's token.

### Journey 2: Returning User (Persona: Sam)
1. **Access**: Sam opens the app.
2. **Token Refresh**: The frontend detects a valid previous session but an expired token. It silently refreshes the token via Google Identity Services.
3. **Skip Onboarding**: The backend sees the `onboarding_completed: true` flag in Sam's project.
4. **Instant Action**: Sam is taken directly to the Media Gallery, skipping the verification page.
