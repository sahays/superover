# Specification: Dynamic Token Propagation (DTP)

## 1. Crisp Problem Description
Currently, local development and portable deployments of "Super Over Alchemy" require manual GCP authentication (gcloud CLI) and environment variable configuration. This creates friction for new developers or users who want to run the system in their own GCP accounts. 

We need a way to dynamically "inject" GCP credentials and bootstrap the required infrastructure (APIs, Buckets, Firestore) directly from a "Login with Google" flow in the web frontend.

## 2. Key Challenges
- **Token Propagation**: Moving a short-lived OAuth2 access token from the browser to headless background workers running in Docker.
- **Project Context**: Ensuring the backend knows which GCP Project ID to target, as this may change per user.
- **Infrastructure Bootstrapping**: Detecting and enabling APIs (Vertex AI, Firestore, GCS) programmatically without requiring the user to visit the GCP Console.
- **State Management**: Identifying if an account has already been onboarded to avoid repetitive setup checks.

## 3. Technical Solution
### Summary
The system will use a **Browser-to-Volume Propagation** strategy. The frontend obtains a Google OAuth2 token and hands it to the API. The API persists this token in a shared Docker volume, allowing background workers to "inherit" the user's identity and project context.

### Mapping to Problems
| Problem/Challenge | Solution Component |
| :--- | :--- |
| **Token Propagation** | Shared `active_session.json` file in the `./storage` volume accessible by all containers. |
| **Project Context** | Frontend sends `project_id` during handoff; Backend initializes clients using this specific project. |
| **API Enablement** | JIT Check using the `serviceusage.googleapis.com` API to verify and enable required services. |
| **Onboarding State** | A `system_config` document in Firestore used as a flag for completion. |

## 4. Success/Acceptance Criteria
- **Functional**: A new user can login with Google and start using the app without ever touching the terminal or GCP Console.
- **Automation**: Required APIs (Vertex, Firestore, GCS) are automatically enabled if the user has permission.
- **Seamlessness**: Background workers process jobs using the identity of the user currently logged into the frontend.
- **Persistence**: The session remains valid for the duration of the OAuth2 token (typically 1 hour, refreshed via frontend).

## 5. FAQs
**Q: Is this secure?**
A: The token is stored in a local volume. Access is restricted to the Docker network. It is safer than static service account keys.

**Q: What if the user doesn't have "Owner" permissions?**
A: The onboarding will fail with a descriptive error, asking them to contact their GCP administrator or enable APIs manually.

**Q: Does it work with impersonation?**
A: The frontend login provides the direct user identity. If the user has permission to impersonate, they can do so, but the initial DTP flow focuses on the logged-in user's direct access.
