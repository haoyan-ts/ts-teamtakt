# Diátaxis Framework Reference

Diátaxis is a documentation framework that classifies all technical docs into four distinct types. Each type serves a different user need and has a different structure.

## The Four Types

```
                     PRACTICAL
                        │
              tutorials  │  how-to guides
                         │
LEARNING ─────────────── ┼ ─────────────── DOING
                         │
           explanation   │  reference
                         │
                    THEORETICAL
```

| Type            | User's state | User's goal                    | Analogy       |
| --------------- | ------------ | ------------------------------ | ------------- |
| **Tutorial**    | Learning     | Acquire skill through practice | Cooking class |
| **How-to**      | Working      | Accomplish a specific task     | Recipe        |
| **Reference**   | Working      | Look up accurate information   | Encyclopedia  |
| **Explanation** | Studying     | Understand a concept or design | Essay         |

---

## Tutorial

- **Oriented by**: Learning
- **Answers**: "How do I get started?" / "Help me understand by doing."
- **Tone**: Encouraging, hand-holding, sequential
- **Key rule**: The reader follows steps and achieves a working result. Teaching happens through doing, not abstract explaining.
- **Pitfall**: Mixing in reference material or explanation derails the learning flow.

## How-to Guide

- **Oriented by**: Tasks
- **Answers**: "How do I accomplish X?"
- **Tone**: Direct, imperative, minimal
- **Key rule**: Assume a competent reader who knows the basics. Skip motivation. State prerequisites, then give steps.
- **Pitfall**: Teaching when guiding — if you find yourself explaining _why_, it belongs in an explanation doc.

## Reference

- **Oriented by**: Information
- **Answers**: "What exactly is/does X?"
- **Tone**: Neutral, precise, exhaustive
- **Key rule**: Describe the system as it is. No instructions, no opinions. Structured and scannable.
- **Pitfall**: Adding how-to or tutorial content dilutes accuracy and makes scanning harder.

## Explanation

- **Oriented by**: Understanding
- **Answers**: "Why does X work this way?" / "What is the reasoning behind X?"
- **Tone**: Discursive, analytical, exploratory
- **Key rule**: Illuminate the design space. Discuss tradeoffs, alternatives, and context. Do not add steps.
- **Pitfall**: Turning into a reference page by listing facts without connecting them to reasoning.

---

## Choosing the Right Type

Ask yourself what need the reader has **right now**:

1. "I want to learn" → **Tutorial**
2. "I need to do X" → **How-to**
3. "I need to look something up" → **Reference**
4. "I want to understand why" → **Explanation**

A single feature often warrants all four types. They complement rather than replace each other.

---

## Source

Diátaxis is by Daniele Procida. Full framework: https://diataxis.fr
