# Manthan AI Notebook

**Manthan AI Notebook** is a free educational AI mentor for students. It goes beyond PDF Q&A: upload a textbook, lecture PDF, notes, question bank, CV, or project report and ask Manthan to explain, summarize, make notes, quiz you, compare ideas, evaluate material, or guide your study.

## Included
- Real account signup/login with salted PBKDF2 password hashing and session tokens
- Per-user notebook ownership
- Per-user server-side chat history
- Profile personalization (name + class/level)
- Library search, pin, archive, restore, delete
- New chat / clear chat history
- Light/dark mode
- Responsive desktop/mobile UI
- OCR fallback for scanned PDFs
- Batched Gemini embeddings
- Page-aware retrieval for questions such as “what is on page 27?”
- Grounded but analytical mentor-style answers

## Run
1. Copy `backend/.env.example` to `backend/.env`.
2. Set `GEMINI_API_KEY`.
3. Run `docker compose up --build`.
4. Open `http://localhost:5173`.
5. Create an account.

For a public deployment, put the application behind HTTPS, use a managed database, store secrets outside source control, and configure the production CORS origin.
