# Supported curl Flags & Options Reference

The `curl-to-skill` engine inspects incoming curl commands and extracts relevant parameters according to this matrix:

| Flag | Description | Engine Action |
| :--- | :--- | :--- |
| `-X`, `--request` | HTTP Method (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`) | Explicitly assigned to runner script. Default is `POST` if body present, else `GET`. |
| `-H`, `--header` | Custom HTTP Headers | Headers like `Authorization: Bearer <token>` are converted to API Key environment variables. |
| `-d`, `--data`, `--data-raw`, `--data-binary` | Request Body | Inferred as JSON; object keys are parsed into CLI `--flags`. |
| `-u`, `--user` | HTTP Basic Auth | Explicitly rejected in v1 with a clear guidance message. |
| `-F`, `--form` | Multipart form data | Explicitly rejected in v1. |
| `--data-urlencode` | URL-encoded form data | Explicitly rejected in v1. |
