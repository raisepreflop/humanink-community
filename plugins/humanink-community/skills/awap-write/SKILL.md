---
name: awap-write
description: "Modo escritura AWAP con registro automático de la conversación. Actívalo cuando el autor diga «activa el modo escritura AWAP», «empieza a escribir con registro», «escribe el capítulo X», «he escrito la premisa», «revísame esto», o siempre que estéis en una sesión de escritura activa. En este modo TODA generación de texto se registra automáticamente en AWAP."
tools:
  - mcp__plugin_humanink_awap__awap_log_event
  - mcp__plugin_humanink_awap__awap_session_start
  - mcp__plugin_humanink_awap__awap_set_project
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

# AWAP — Conversation Auto-logging

## CORE RULE

**In any active AWAP writing session, you must call `awap_log_event` BEFORE replying with creative text and AFTER the user shares a document.**

Never generate creative writing without logging it. Logging is part of the protocol, not optional.

## When and what to log

### 1. The user shares a document of theirs (premise, synopsis, etc.)

Immediately after reading the document, log:

```
awap_log_event(
  event_type: "document_created",
  document_type: "premise" | "synopsis" | "bible" | "outline" | "style_instructions",
  tokens_revised_by_human: <word estimate>,
  description: "Premise written by the author: [first words...]"
)
```

### 2. You're about to generate creative text (chapter, scene, dialogue, etc.)

Log AFTER generating, with the real output tokens:

```
awap_log_event(
  event_type: "text_generated",
  document_type: "draft",
  ai_model: "claude-opus-4",   ← or whichever model you are
  tokens_generated: <output tokens>,
  tokens_revised_by_human: 0,
  description: "Chapter X — [title or first words]"
)
```

### 3. The user revises / rewrites generated text

```
awap_log_event(
  event_type: "text_revised",
  document_type: "revision",
  tokens_generated: <original tokens>,
  tokens_revised_by_human: <tokens the user changed>,
  description: "Revision of chapter X"
)
```

### 4. A directive conversation turn from the user

When the user gives substantial instructions (not just "go on" or "ok"):

```
awap_log_event(
  event_type: "conversation_turn",
  document_type: "draft",
  directive_weight: 0.8,   ← 0.1 for trivial instructions, 1.0 for important decisions
  description: "The author decides: [summary of the instruction]"
)
```

## Token estimation

- ~1 token ≈ 0.75 words in English
- For the user's documents: count the words in their message
- For your output: use the real token count if available, otherwise estimate

## Full session flow

```
awap_session_start
→ user shares premise → awap_log_event (document_created / premise)
→ user gives instructions → awap_log_event (conversation_turn)
→ you generate chapter 1 → awap_log_event (text_generated / draft)
→ user corrects → awap_log_event (text_revised)
→ awap_session_end when the session ends
```

## Working directory

If the user mentions a different folder for this book, use `awap_set_project` to switch the active directory before logging.
