
### Manual Sentiment Run (AM/PM)
You can trigger the Google+OpenAI sentiment job on demand:

**Command Prompt (from project root):**
```
run_sentiment_once.cmd am
run_sentiment_once.cmd pm
run_sentiment_once.cmd auto        # AM before noon ET, else PM
run_sentiment_once.cmd am --keep-weekends
```

**Direct Python:**
```
.\.venv\Scripts\python -m app.tools.run_sentiment_once --am
.\.venv\Scripts\python -m app.tools.run_sentiment_once --pm
```

Output JSON is written to `data\sentiment\YYYY-MM-DD.json` and files older than 30 days are pruned.
If Google CSE keys are missing, it falls back to Google News RSS. OpenAI key is required.
