# PaperCorpus2Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml) [![Input](https://img.shields.io/badge/Input-PDF%20%7C%20Markdown-orange.svg)](#快速开始) [![Export](https://img.shields.io/badge/Export-Claude%20%7C%20ChatGPT%20%7C%20Codex%20%7C%20Cursor-purple.svg)](#输出什么)

把几十到上百篇论文，变成可复用的 AI 学术写作 Skill。

> 面向 SCI 论文写作、领域语料分析、Claude Skill、ChatGPT Project Instructions、Codex AGENTS.md、Cursor Rules 的本地优先工具。

## 解决什么问题

网页版 GPT / Claude 适合临时问几篇论文，但不适合处理一个领域的几十个 PDF。

PaperCorpus2Skill 专门解决这个问题：

- **论文太多**：按文件夹批量读取 PDF / Markdown
- **上下文不够**：按章节抽取表达模式，而不是一次塞全文
- **参考文献干扰**：自动过滤 References / Bibliography
- **章节写法不同**：分别总结 Introduction、Related Work、Method、Experiments、Discussion、Conclusion
- **工具之间不通用**：一次生成 Claude、ChatGPT、Codex、Cursor 可用的 Skill Pack

## 它会生成什么

从你的论文语料中提取：

- 领域术语和常见搭配
- 各章节写作逻辑
- 各章节常用表达
- 学术改写规则
- AI 味检查清单
- 可迁移的 Markdown Skill 文件

## 快速开始

配置 API Key：

```bash
cp .env.example .env
```

配置模型和导出参数：

```bash
cp papercorpus2skill.yaml.example papercorpus2skill.yaml
```

整理论文：

```text
corpus/
  topic-a/
    paper1.pdf
    paper2.pdf
  topic-b/
    paper1.pdf
    paper2.md
```

预览：

```bash
uv run papercorpus2skill batch-preview ./corpus
```

生成：

```bash
uv run papercorpus2skill batch ./corpus
```

默认处理策略：

```text
PDF -> Markdown cache
每 5 篇论文总结一次
每 5 个 summary 再合并一次
持续合并章节表达和篇章 concept threads
断点续跑：batch summary / merge summary / working skill state 会缓存到本地
```

## 输出什么

```text
outputs/
  topic-a-academic-writing-skill/
    SKILL.md
    files/
      phrasebook.md
      section-logic.md
      section-expressions.md
      concept-threads.md
      paper-level-patterns.md
      rewrite-rules.md
      ai-taste-checklist.md
    corpus-report.md
    exports/
      claude/SKILL.md
      chatgpt/project-instructions.md
      codex/AGENTS.md
      cursor/corpus2skill.mdc
```

## 适合谁

- 想从大量 SCI 论文中提取写作风格的研究者
- 想建立领域论文写作助手的学生和作者
- 想把论文语料变成 Claude / ChatGPT / Codex / Cursor 指令资产的人
- 想用 DeepSeek、OpenAI-compatible API、Anthropic 或 Ollama 处理本地语料的人

## 关键词

`论文语料` `SCI论文写作` `学术写作助手` `论文写作风格提取` `PDF转Skill` `Claude Skill` `ChatGPT Project Instructions` `Codex AGENTS.md` `Cursor Rules` `academic writing` `paper corpus` `AI skill generator` `PDF to skill` `section-aware writing style extraction`

## License

MIT License. See [LICENSE](LICENSE).

---

# PaperCorpus2Skill

Turn dozens or hundreds of research papers into reusable AI academic writing skills.

## What it solves

Web GPT / Claude is fine for a few papers. It breaks down when you want to learn writing style from a full paper corpus.

PaperCorpus2Skill:

- reads local PDF / Markdown papers in batches
- removes noisy reference sections
- extracts section-aware writing patterns
- summarizes terminology, section logic, common expressions, and rewrite rules
- exports portable Skill Packs for Claude, ChatGPT, Codex, and Cursor

## Quick Start

```bash
cp .env.example .env
cp papercorpus2skill.yaml.example papercorpus2skill.yaml
uv run papercorpus2skill batch-preview ./corpus
uv run papercorpus2skill batch ./corpus
```

Recommended layout:

```text
corpus/
  topic-a/
    paper1.pdf
    paper2.md
  topic-b/
    paper1.pdf
```

## Keywords

`academic writing` `SCI paper writing` `paper corpus` `PDF to skill` `AI skill generator` `Claude Skill` `ChatGPT Project Instructions` `Codex AGENTS.md` `Cursor Rules` `research writing assistant` `section-aware writing style extraction`

## License

MIT License. See [LICENSE](LICENSE).
