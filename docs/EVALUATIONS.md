# Evaluations

How Agentic QE Platform measures whether an agent is accurate. Nothing here is estimated: a number appears only when a metric really ran, and every other state says why there is no number.

## The four states of a score

| State | Meaning |
|---|---|
| A percentage | The metric ran. The card also says if it was self-graded or if its labels are not yet reviewed |
| Not measured | It has not been run, or the tool it needs (RAGAS, a judge model) is missing. The reason is shown |
| n/a | The metric does not apply to this agent. A generated test, for example, is not a claim to check against context |
| Failed or Not available | It was tried and could not run, for example the judge model refused or the endpoint has no embeddings model |

A ratio whose denominator is zero has no value. It is never shown as 0 percent or 100 percent.

## Free metrics (code only, no model tokens)

### Groundedness

Question: do the citations really exist?

Formula: groundedness = verified citations / all citations. A citation is a file, a line, and a quote. A citation is verified when the file exists inside the repository, the quote is found in it (whitespace is ignored, since models reflow code), or, with no quote, the line exists. On benchmarks the check is against the given context text instead of the disk.

How to read: 100 percent means every citation was real. It says nothing about whether the claim is right, only that the evidence exists. A reply with no citations has no value, because nothing was there to check.

Limits: a real quote can still be used for a wrong claim. Prose such as "see cart.py:27" is checked only for the file and the line.

It runs on every real agent call that cites files, costs nothing, and is stored with the agent call.

### Precision, Recall, F1

Question: did the agent find the right items, without extras?

Formulas, with TP the items found that match the answer key, FP the extras, and FN the key items missed:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 TP / (2 TP + FP + FN)

Items match one to one: a key item can be matched once. A bug or requirement matches when the file is the same and the line is within the key's tolerance, which is usually 0 to 2 lines. A facts-in-text key (used for the business analyst) counts which labelled facts appear in the document. It cannot count extras in prose, so only Recall has a value there.

How to read: low precision means false alarms, low recall means missed items, and F1 is the balance. In the bug reviewer, a finding in a clean file is a false alarm.

Limits: the score is only as good as the labels. While labels are not reviewed by a person, cards say "labels not yet reviewed". Matching by line is strict and may miss a correct finding that cites a slightly different line.

### Mutation score

Question: do the generated tests catch real bugs?

Method: a bug is planted in a temporary copy of the repository, the generated tests run with the same runner the platform uses, and the mutant is killed when a test fails.

Formula: mutation score = killed / (killed + survived). A mutant whose text cannot be applied exactly once is "not applied" and is left out.

If no test was executed, or the tests already fail on the unchanged code, the result is INCONCLUSIVE and there is no number.

How to read: 100 percent means every planted bug was caught. A surviving mutant names the behavior no test checks.

Limits: a few hand-written mutants are a sample, not proof. The real repository is never changed.

## Model-graded metrics (RAGAS)

These use a judge model and cost tokens. They need the optional package: install requirements-evals.txt. Without it every one reads "Not measured: RAGAS is not installed".

The judge model is set with ATLAS_EVAL_MODEL. If it is unset, or the same as the agent's model, every score is labelled self-graded, because a model grading its own work is a weak check. Scores vary between runs, so read the spread over repeated runs and judge trends, not single numbers.

| Metric | Question | Needs |
|---|---|---|
| Faithfulness | Is each claim in the answer supported by the context? Claims supported / all claims | Context |
| Context recall | Did the context hold what the answer needs? Reference statements found in the context / all reference statements | Context and reference |
| Context precision | Was the context relevant, with the useful parts ranked first? | Context and reference |
| Factual correctness (F1 mode) | Does the answer agree with the reference? F1 over claims in the answer and in the reference | Reference |
| Response relevancy | Does the answer address the question? Needs an embeddings model | An embeddings model |

Response relevancy is named AnswerRelevancy in RAGAS 0.4.3. The model endpoint in use offers no embeddings model, so it reads "Not available" with that reason.

Limits: the judge can be wrong, and a reasoning model may need many tokens per score. Faithfulness can fail if the judge runs out of output tokens; the metric then reads Failed with the reason, never a guess.

## Plugin skill cases and the grader

Plugin skill cases hold sentences describing expected behavior. Where code can check a sentence it does. The rest need a grader: with ATLAS_EVAL_MODEL set, the judge reads the output and, for each sentence, answers PASS or FAIL and must quote the evidence from the output. Code then checks that the quote is in the output. A PASS without a found quote becomes FAIL. Without a judge model these cases stay "needs grader" and are neither passed nor failed.

## Benchmarks

| Benchmark | Contents |
|---|---|
| evals/benchmarks/shop | A small shop with 5 planted bugs, 2 clean files, labelled requirements, failures, and questions |
| evals/benchmarks/finance | Labels for personal-finance-mcp at a pinned commit, src/tools/tvm.py, with 5 bugs and 9 requirements found by reading the code |

Every label file has reviewed set to false. The labels were drafted by reading the code and must be checked by a person who knows the repository. Until then, cards show "labels not yet reviewed". A good score on a benchmark does not guarantee results on real code, so read it beside the live groundedness.

## Where the numbers appear

- Agents page: four tiles on each card, Groundedness, Faithfulness, Recall, and F1.
- Agent page: every metric, the trend by prompt version, the spread over repeated runs, and every case of the latest run with its question, context, answer, and reason, worst first.
- Prompts page: the tiles of each prompt version, so a new version can be compared with the one before.

Evaluations are started by an administrator, run in a hidden project, and never count against a user's token limits.

## Running them

On demand and when a prompt changes, never on a page view. Use Measure on the agent page, or POST /api/agents/{agent}/evals with benchmark, repeats, and ragas. The result reports the tokens used.
