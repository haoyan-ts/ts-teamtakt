# Reference Template (Diátaxis)

<!-- AGENT INSTRUCTIONS: Fill every section below for the specific topic. Remove these comments in the final file. A reference doc is INFORMATION-ORIENTED — describe the system accurately and completely. Avoid tutorials or how-to steps; just document what exists. -->

---

title: "<Topic Name> Reference"
type: reference
audience: all
date: YYYY-MM-DD

---

# \<Topic Name\> Reference

One sentence stating what this document covers and its scope.

## Overview

Two to four sentences providing enough context for the reader to understand what they are looking at. Do not teach — just orient.

## \<Primary concept or object\>

Describe the main entity, API endpoint, schema, or module being documented.

### Properties / Fields

| Name         | Type     | Required | Default | Description               |
| ------------ | -------- | -------- | ------- | ------------------------- |
| `field_name` | `string` | Yes      | —       | What this field contains. |

### Constraints

List any validation rules, invariants, or business rules that apply.

- Constraint 1 (e.g., "`is_primary` must be true for exactly one entry per record")
- Constraint 2

## \<Secondary concept, if applicable\>

Repeat the pattern for additional objects, endpoints, or modules.

## Enumerated values

If the topic includes ENUMs, status codes, or fixed value sets:

| Value     | Meaning     |
| --------- | ----------- |
| `value_a` | Description |
| `value_b` | Description |

## Related endpoints / modules

| Path / Module     | Purpose           |
| ----------------- | ----------------- |
| `GET /api/v1/...` | Brief description |

## See also

- [How-to: Related task](../how-to/related-task.md)
- [Explanation: Why this works this way](../explanation/related.md)
