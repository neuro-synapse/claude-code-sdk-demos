# Claude Agent SDK Demos

> ⚠️ **IMPORTANT**: These are demo applications by Anthropic. They are intended for local development only and should NOT be deployed to production or used at scale.

This repository contains multiple demonstrations of the [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview), showcasing different ways to build AI-powered applications with Claude.

## Available Demos

### 📧 [Email Agent](./email-agent)
An in-development IMAP email assistant that can:
- Display your inbox
- Perform agentic search to find emails
- Provide AI-powered email assistance

### 📊 [Excel Demo](./excel-demo)
Demonstrations of working with spreadsheets and Excel files using Claude.

### 👋 [Hello World](./hello-world)
A simple getting-started example to help you understand the basics of the Claude Agent SDK.

### 🔬 [Research Agent](./research-agent)
A multi-agent research system that coordinates specialized subagents to research topics and generate comprehensive reports:
- Breaks research requests into subtopics
- Spawns parallel researcher agents to search the web
- Synthesizes findings into detailed reports
- Demonstrates detailed subagent activity tracking

## Quick Start

Each demo has its own directory with dedicated setup instructions. Navigate to the specific demo folder and follow its README for setup and usage details.


## Prerequisites

- [Bun](https://bun.sh) runtime (or Node.js 18+)
- An Anthropic API key ([get one here](https://console.anthropic.com))

## Getting Started

1. **Clone the repository**
```bash
git clone https://github.com/anthropics/claude-code-sdk-demos.git
cd claude-code-sdk-demos
```

2. **Choose a demo and navigate to its directory**
```bash
cd email-agent  # or excel-demo, or hello-world
```

3. **Follow the demo-specific README** for setup and usage instructions

## Resources

- [Claude Agent SDK Documentation](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview)
- [API Reference](https://docs.anthropic.com/claude)
- [GitHub Issues](https://github.com/anthropics/sdk-demos/issues)

## Support

These are demo applications provided as-is. For issues related to:
- **Claude Agent SDK**: [SDK Documentation](https://docs.anthropic.com/claude-code)
- **Demo Issues**: [GitHub Issues](https://github.com/anthropics/sdk-demos/issues)
- **API Questions**: [Anthropic Support](https://support.anthropic.com)

## 📋 Coupling Compliance Audit

A comprehensive architectural audit has been conducted on this codebase. **12 coupling violations** have been identified, including 2 critical issues requiring immediate attention.

**Health Score**: 45/100 (Critical)

### Quick Links
- **Start Here**: [Coupling Audit Quick Start](./COUPLING_AUDIT_QUICKSTART.md) (5 min read)
- **Executive Summary**: [Coupling Audit Summary](./COUPLING_AUDIT_SUMMARY.md) (15 min read)
- **Full Report**: [Coupling Audit Report](./COUPLING_AUDIT_REPORT.md) (30 min read)
- **Detailed Issues**: [Coupling Violations](./COUPLING_VIOLATIONS/) (Issue specifications)

### Top 2 Critical Issues
1. **Multiple Uncoordinated Database Instances** - 7 independent SQLite connections (data corruption risk)
2. **Duplicated EmailRecord Interfaces** - Inconsistent field naming (camelCase vs snake_case)

**Recommended Action**: Allocate 2 engineers for 4 weeks to address critical architectural technical debt.

---

## License

MIT - This is sample code for demonstration purposes.
