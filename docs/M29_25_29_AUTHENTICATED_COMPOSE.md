# M29.25–M29.29 — Authenticated HTTPS deployment

| Phase | Implementation |
| --- | --- |
| M29.25 | Add an opt-in Compose override for installations that need authenticated access. |
| M29.26 | Accept HTTPS only on the published listener and serve the application and API through one authenticated origin. |
| M29.27 | Unpublish API and optional PostgreSQL ports and keep the container health probe on loopback. |
| M29.28 | Load the TLS files and bcrypt credential database from operator-managed secret files. Strip the browser credential header before forwarding API calls. |
| M29.29 | Exercise trusted HTTPS, missing and invalid credentials, authorized UI and API access, and host port configuration in packaged CI. |

## Start the authenticated stack

Use Docker Compose 2.24.4 or later for the port override. Create an initial bcrypt credential using Apache `htpasswd`. Provide a TLS certificate chain valid for the hostname that clients will use, and its corresponding private key. Use a location outside the repository for these files. The Nginx worker needs read access to the password file. [Docker Compose overrides](https://docs.docker.com/reference/compose-file/merge/) · [Apache htpasswd](https://httpd.apache.org/docs/2.4/programs/htpasswd.html)

```sh
htpasswd -cB -C 10 /path/to/aeroforge.htpasswd editor
export AEROFORGE_HTPASSWD_FILE=/path/to/aeroforge.htpasswd
export AEROFORGE_TLS_CERT_FILE=/path/to/fullchain.pem
export AEROFORGE_TLS_KEY_FILE=/path/to/privkey.pem
docker compose -f docker-compose.yml -f compose.authenticated.yml up --build --wait
```

Open `https://<certificate-hostname>:8443`. The HTTPS socket binds to loopback by default. To expose this mode to a trusted network, set `AEROFORGE_HTTPS_BIND_ADDRESS` to the desired host interface and use the same certificate hostname on clients. Set `AEROFORGE_HTTPS_PORT` if the default port is unavailable. This mode grants each authenticated user the same application access and is intended for a trusted single-instance deployment. [Nginx HTTPS](https://nginx.org/en/docs/http/configuring_https_servers.html) · [Nginx Basic authentication](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html)

Use the same Compose project name when replacing an existing stack to reuse the saved-design volume. Always supply the same pair of Compose files when managing this deployment. The [packaged-app guide](M29_10_14_PACKAGED_APP_ACCEPTANCE.md) also describes the migration path for older volume layouts.

## Verify a local stack

From the repository root on a host with Docker Compose, Bash, `htpasswd`, OpenSSL and Python, run `bash scripts/check_authenticated_compose.sh`. The check uses its own Compose project, temporary credentials and certificate, and loopback port 5443. It verifies the certificate with curl and removes the test project and its temporary volume on exit.
