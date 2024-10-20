# activity-api

Teams Notifier's activity api component.
Used to send/update/delete messages (activities) to MS Teams.


Environment variables or `.env`:

* `PORT`: port to listen to (def: `3980`)
* `MICROSOFT_APP_ID`: App registration application id
* `MICROSOFT_APP_PASSWORD`: Application password
* `MICROSOFT_APP_TENANT_ID`: Tenant ID
* `DATABASE_URL`: Database DSN in the form: `postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}`
