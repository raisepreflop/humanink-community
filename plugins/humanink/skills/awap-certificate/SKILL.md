---
name: awap-certificate
description: "Genera y gestiona el certificado de autoría AWAP. Actívalo cuando el autor diga «firma el certificado», «genera el certificado AWAP», «he terminado el libro», «quiero el PDF de autoría», «sincroniza con la nube» o «awap sync»."
tools:
  - mcp__plugin_humanink_awap__awap_sign
  - mcp__plugin_humanink_awap__awap_sync
  - mcp__plugin_humanink_awap__awap_session_end
model: haiku
---


## 0. Antes de nada: ¿está conectado AWAP?

Este colaborador no puede hacer su trabajo sin el conector **awap** — es donde vive el registro de
autoría. Cowork **no lo conecta solo al instalar el plugin**: hay que pulsar un botón una vez, y
si el autor no lo sabe se encuentra un error de herramienta sin explicación.

Llama a `awap_ping`. Si responde, sigue con normalidad y no menciones nada de esto. Si la
herramienta no existe o devuelve error, **para aquí** y dile exactamente esto:

> ⚠️ **Falta conectar AWAP** — es cosa de diez segundos y sólo se hace una vez.
>
> 1. Abre **Plugins** (el icono de la barra lateral).
> 2. Entra en **HumanInk**.
> 3. Pestaña **Connectors**.
> 4. En **awap**, pulsa **Connect**.
>
> Vuelve y repite el comando. El resto de colaboradores funcionan sin esto: solo el auditor y el
> certificado necesitan el conector, porque son los que registran y firman tu autoría.

# AWAP — Authorship Certificate

> **Draft vs Official.** `--certificate` produces an unlimited **draft** certificate
> (a free self-audit, signed but not registered). It is **not** the official, publicly-verifiable HumanInk certificate, and
> its QR does **not** resolve online until the book is registered. The official certificate (the
> $25 product — frozen, anchored, verifiable) is registered via **/humanink:auditor --official**.
> See `AWAP-CERTIFICATE-MODEL.md`. Never present a locally-signed certificate as "official".

## Generate the draft certificate (awap_sign)

When the user says they've finished the book or wants the certificate:

1. If a session is active, call `awap_session_end` first.
2. Call `awap_sign` with the manuscript content if available:
   - `manuscript_content`: the full book text (optional but recommended for the hash)
2b. **Save a legible PDF.** `awap_sign` returns `pdf_base64` + a `download_url`. Never write
   `pdf_base64` directly into a `.pdf` (it becomes unreadable). Write it to `.awap/cert.b64` and
   decode: `base64 -d .awap/cert.b64 > .awap/awap-license.pdf` (or `curl -L <download_url> -o .awap/awap-license.pdf`).
3. Show the user, framed as a **draft / self-audit**:
   - Current HAS score
   - Path of the generated PDF
   - Certificate hash
   - A note that the QR will **not** verify online until they register the official certificate
     (`/humanink:auditor --official`).

## What the certificate contains

The generated PDF includes:
- **HAS Score** (0–100) with a breakdown by document level
- **Section 6 — JSON-LD**: verifiable metadata with SHA-256 integrity
- **Section 7 — QR**: a QR code linking to the public verification page
- Cryptographic hashes of the manuscript and the event log
- A declaration of the AI models used

## Official registration & public verification

A **draft** certificate is **not** publicly verifiable — its QR has no resolving page. Public,
tamper-proof verification is what the **official** certificate buys: registering with HumanInk
freezes the final manuscript (by its hash), records it in HumanInk's tamper-evident registry with
a secure timestamp, and publishes a page at `verify.humanink.io/c/<id>` that anyone can reach by
scanning the QR — no account needed.

To register the official certificate, the user runs **/humanink:auditor --official**, which
requires a HumanInk Certificate credit ($25/title · pack of 5 $99 — https://humanink.io/#pricing).
Do not tell the user a locally-signed draft can be verified online.

## Cloud sync (awap_sync)

If the user wants to sync certificates with Turso (cloud database):
- Check whether it's configured with `awap_sync`
- If not configured, tell them to run `awap sync --enable` in the terminal

## After signing

The project is marked "finished". For a new book, create a new project with `awap_init` or switch directory with `awap_set_project`.
