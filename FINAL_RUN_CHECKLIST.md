# Final run checklist

Use the canonical `OnboardAI_Final_Capstone.ipynb`.

1. Add `GROQ_API_KEY` and `LANGSMITH_API_KEY` to Colab Secrets and enable notebook access.
2. Run the Colab bootstrap cell and upload `OnboardAI_Final_Capstone.zip` if asked.
3. Confirm the package imports from `src/onboardai`.
4. Confirm automated tests pass.
5. Confirm LangSmith key verification passes.
6. Confirm RAG evidence reports Hugging Face, loaded documents, chunks, stored chunks, and cited
   retrieved passages.
7. Confirm all retrieval smoke tests pass.
8. Confirm live routing sends different natural-language requests to different specialists while
   all three workers are available.
9. Confirm a live worker prints at least one `[MODEL TOOL CALL]`.
10. Confirm the cross-thread Store demo writes in `thread-A` and reads in `thread-B`.
11. Confirm the missing-start-date error demo pauses and then resumes.
12. Confirm the main live workflow prints `attempt #1`, the simulated transient failure, and
    `attempt #2` through `RetryPolicy`.
13. Confirm the main workflow pauses for HR approval.
14. Confirm the next cell resumes the **same** `thread_id` with `Command(resume=...)`.
15. Confirm the final result is `completed`, training memory contains approved course IDs, and the
    audit event is written.
16. Confirm the LangSmith inspection cell returns real runs and prints a trace-based observation.
17. Save the notebook with every output visible.
18. Scan the repository and Git history for secrets before pushing.
19. Push with meaningful incremental commits rather than one giant final commit.
