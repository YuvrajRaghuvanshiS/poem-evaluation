# Hindi Poem Evaluator

A minimal web application for human evaluation of AI-generated Hindi poetry.

## Project Structure

```
project/
├── main.py           # FastAPI backend
├── poems.json        # Source poems (edit this to add your real poems)
├── ratings.json      # Auto-created on first submission; all results stored here
├── requirements.txt
└── static/
    └── index.html    # Full frontend (HTML + CSS + JS)
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add your poems

Edit `poems.json`. The structure is:

```json
{
  "artists": [
    {
      "artist_id": "unique_id",
      "artist_name": "कवि का नाम",
      "poem_prompt": "The prompt used",
      "poems": [
        { "poem_id": "unique_poem_id", "model_label": "Model A", "text": "poem text..." },
        { "poem_id": "...",            "model_label": "Model B", "text": "..." },
        { "poem_id": "...",            "model_label": "Model C", "text": "..." },
        { "poem_id": "...",            "model_label": "Model D", "text": "..." },
        { "poem_id": "...",            "model_label": "Model E", "text": "..." }
      ]
    }
  ]
}
```

**Important:** Each artist must have exactly 5 poems (one per model). The `model_label` 
values (Model A–E) are what evaluators see — they do not reveal which AI generated which poem.

### 3. Run the server

```bash
uvicorn main:app --reload
```

Then open http://localhost:8000 in your browser.

## API Endpoints

| Method | Path          | Description                                    |
|--------|---------------|------------------------------------------------|
| GET    | /             | Serves the frontend                            |
| GET    | /api/poems    | Returns a random artist's 5 poems (shuffled)   |
| POST   | /api/submit   | Accepts and stores a completed evaluation      |

## Data Collection

All submissions are stored in `ratings.json`. Each entry records:
- Evaluator name and email
- Artist/poem set evaluated
- All 5 ratings (1–5 stars) per poem per criterion
- Any inline annotations (highlighted text + comment)
- Timestamp and unique submission ID

## Notes

- Evaluator identity is stored in browser `localStorage` — returning evaluators won't need to re-enter details.
- The 5 poems are shuffled in random order on each page load so column position cannot be used to infer the model.
- All 25 ratings (5 poems × 5 criteria) must be filled before the Submit button becomes active.
- Annotations are optional and do not block submission.
