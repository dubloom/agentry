---
name: writePostcard
description: if a user is asking to write a postcard, ignore options and follow below steps
options:
  model: gpt-5.4-mini
  reasoning_effort: medium
  allowed_tools: [Read, Glob, Grep]
---

<!-- Markdown comments are ignored by the workflow loader. -->

## Step: loadTripContext
execute: handlers.py:load_trip_context
returns:
  city: str
  mood: str
  memory: str

## Step: draftPostcard

Write a short postcard message from {{ city }}.

The mood should feel {{ mood }}.
Mention this memory: {{ memory }}.
Keep it to 3 sentences maximum.

## Step: savePostcard
execute: handlers.py
returns:
  file_path: str
