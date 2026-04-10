# Explanation Template (Diátaxis)

<!-- AGENT INSTRUCTIONS: Fill every section below for the specific topic. Remove these comments in the final file. An explanation is UNDERSTANDING-ORIENTED — explore the "why" and "how it works" behind a concept. Avoid step-by-step instructions; focus on reasoning, tradeoffs, and context. -->

---

title: "<Topic Name>: How It Works"
type: explanation
audience: all
date: YYYY-MM-DD

---

# \<Topic Name\>: How It Works

One sentence framing the concept and why understanding it matters in this codebase.

## The problem this solves

Two to four sentences: what real problem existed before this design, and what a naive alternative would look like. This sets up the "why."

## Design decisions

### \<Decision 1\>

Explain the tradeoff or constraint that led to this choice. Mention alternatives that were considered and why they were rejected.

### \<Decision 2\>

Repeat for each significant design choice.

## How it fits together

Describe how this concept interacts with related parts of the system. Use either prose or a simple diagram.

```
ComponentA ──→ ComponentB ──→ ComponentC
    (role A)       (role B)       (role C)
```

## Constraints and invariants

List the rules this concept must uphold, and what breaks if they are violated.

- Invariant 1 (e.g., "Absence and DailyRecord are mutually exclusive per user per date")
- Invariant 2

## Common misconceptions

| Misconception        | Reality                      |
| -------------------- | ---------------------------- |
| "X works by doing Y" | It actually does Z because … |

## Related reading

- [Reference: Topic schema](../reference/related.md)
- [How-to: Task that uses this concept](../how-to/related-task.md)
