---
name: [skill-name-in-kebab-case]
description: [Concise one-sentence description: what this skill accomplishes and when the agent must activate it]
---

# [Readable Skill Title]

## 1. Context and Objective
[Briefly describe the purpose of this skill, what problem it solves, and the project architectural standard it enforces.]

---

## 2. When to Use (Triggers)
Activate this skill whenever the task involves:
- [Trigger 1, e.g. authoring a new code-drawn pixel asset]
- [Trigger 2, e.g. defining a new StylePack palette]

---

## 3. Associated Tools and MCP Servers
- **MCP Servers:** `None (local CLI and filesystem)`
- **CLI Tools / Scripts:** `pnpm test`, `pixelforge check`, `pixelforge render`

---

## 4. Step-by-Step Operational Procedure

### Step 1: [Preparation / Discovery]
[What to verify or inspect before making modifications.]

### Step 2: [Implementation]
[Step-by-step logic. Specify which layers to touch and in what order.]

### Step 3: [Validation & Testing]
[How to verify that the implementation adheres to the required standard.]

---

## 5. Code Standards and Canonical Examples

### Standard Implementation Example
```typescript
// Canonical strictly typed example following project conventions
```

---

## 6. Known Gotchas and Anti-Patterns
- **DO NOT:** [Common pitfall or anti-pattern to avoid]
- **DO:** [Correct expected project pattern]

---

## 7. Skill Completion Checklist
- [ ] [Schema or contract requirement verified]
- [ ] [Unit or guard tests covering the workflow]
- [ ] [Linter and strict typing validation passes]
