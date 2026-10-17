# Deployment guide

## Environment variables
Copy app/.env.example to app/.env and fill in SECRET_KEY, DATABASE_URL (Postgres for production), CORS_ORIGINS, LLM_PROVIDER, SMTP values and legal tokens.

## Docker
Run `docker compose up -d --build`. The api, web (nginx serving built frontend and proxying /api) and postgres services start. Postgres data is in a named volume. Migrations run on api startup.

## Custom domain
Point DNS A record to the server IP. Add an nginx server block with the desired server_name on ports 80 and 443. Use certbot or your provider to issue a certificate. Set HSTS once HTTPS is stable. Restart nginx.

## Backup and restore
Back up the Postgres volume nightly: `pg_dump -F c -f backup.dump $DATABASE_URL`. Restore with `pg_restore -d $DATABASE_URL backup.dump`. Uploads directory is included in the same backup job.

## Manual steps left to the operator
- Buy the domain and set the DNS records.
- Fill legal tokens in legal.config.ts and have a lawyer review the legal pages before launch.
- Configure SMTP and model keys.
- Run the launch gate: `npm run check:launch`.
