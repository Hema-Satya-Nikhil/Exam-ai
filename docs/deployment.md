# Deployment

Use Docker for local deployment and environment-variable-driven configuration for production. PostgreSQL must be managed separately or via a managed service in production. The backend is HTTPS-ready and the frontend only communicates with the backend API.

MongoDB is reserved for future document/session storage and should be configured through `MONGODB_URI` and `MONGODB_DATABASE` when that layer is enabled.
