# Mogranco Designer Project Instructions

## Project

This repository contains the Mogranco Designer POC for Modern Grace & Co.

The application should allow a customer to upload a room photograph, receive a redesigned room image, and see recommended products from the Mogranco catalog.

## Repository rules

- Treat the repository root as the working directory.
- Inspect existing code before implementing changes.
- Do not replace working systems merely to simplify implementation.
- Preserve existing catalog data.
- Preserve SKU-based image naming conventions.
- Product images may use names such as:
  - mg-p520-016-rc.1.jpg
  - mg-p520-016-rc.2.jpg
- Do not assume the Vite app directory contains the entire project.
- Prefer small, verifiable changes.
- Run tests or validation commands after changes.
- Report exactly which files were changed.
- Do not commit or push unless explicitly instructed.

## Current architecture goals

1. Maintain a Mogranco product catalog independent of Square.
2. Connect the mobile-first web app to the catalog.
3. Support room-photo upload.
4. Add basic tag-based product recommendations.
5. Add AI interpretation and room redesign capabilities later.

## Development priorities

- Keep POC costs low.
- Use the existing Supabase project where appropriate.
- Do not introduce paid infrastructure without explaining the cost.
- Keep secrets in environment files, never source-controlled files.
- Never expose Supabase service-role keys in frontend code.