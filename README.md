# activity-api

Teams Notifier's activity api component.
Used to send/update/delete messages (activities) to MS Teams.

Authentication is either relying on `MICROSOFT_APP_PASSWORD` or `MICROSOFT_APP_CERTIFICATE` AND `MICROSOFT_APP_PRIVATEKEY`.

Environment variables or `.env`:

* `PORT`: port to listen to (def: `3980`)
* `MICROSOFT_APP_ID`: App registration application id
* `MICROSOFT_APP_PASSWORD`: Application password

* `MICROSOFT_APP_CERTIFICATE`: Base64 representation of the PEM certificate
* `MICROSOFT_APP_PRIVATEKEY`: Base64 representation of PEM privatekey

* `MICROSOFT_APP_TENANT_ID`: Tenant ID
* `DATABASE_URL`: Database DSN in the form: `postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}`
