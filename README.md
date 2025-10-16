# Email Agent

> ⚠️ **IMPORTANT**: This is a demo application by Anthropic. It is intended for local development only and should NOT be deployed to production or used at scale.

This is an in-development IMAP email assistant powered by Claude and the [Claude Code SDK](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview).

## Still in Development

This agent will be continually developed over time. Currently it can:
- display your inbox
- do agentic search to find emails
- display a 'profile' of you

We'll be building more features and sharing them here as we go.


## 🔒 Security Warning

**This application should ONLY be run locally on your personal machine.** It:
- Stores email credentials in plain text environment variables
- Has no authentication or multi-user support
- Is not designed for production security standards

## Prerequisites

- [Bun](https://bun.sh) runtime (or Node.js 18+)
- An Anthropic API key ([get one here](https://console.anthropic.com))
- Email account with IMAP access enabled

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/anthropics/sdk-demos.git
cd sdk-demos/email-agent
```

### 2. Install Dependencies

```bash
bun install
# or npm install
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials (see IMAP Setup below).

### 4. Run the Application

```bash
bun run dev
# or npm run dev
```

### 5. Open Browser

Navigate to `http://localhost:3000`

## IMAP Setup Guide

### Gmail Setup

Gmail requires an **App Password** instead of your regular password:

1. **Enable 2-Factor Authentication** (required for app passwords):
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Click on "2-Step Verification" and follow the setup

2. **Generate an App Password**:
   - Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" from the dropdown
   - Select your device (or choose "Other" and name it "Email Agent")
   - Click "Generate"
   - **Copy the 16-character password** (you won't see it again!)

3. **Configure `.env`**:
```env
ANTHROPIC_API_KEY=your-anthropic-api-key
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-16-char-app-password  # NOT your regular password!
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
```

## Features

- **Natural Language Search**: Find emails using conversational queries
- **AI-Powered Assistance**: Claude helps draft replies, summarize threads, and extract information
- **SQLite Integration**: Fast local email caching and search
- **Real-time Streaming**: WebSocket-based UI updates
- **Multi-turn Conversations**: Complex email workflows with context retention

## Resources

- [Claude Code SDK Documentation](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview)
- [API Reference](https://docs.anthropic.com/claude)
- [GitHub Issues](https://github.com/anthropics/sdk-demos/issues)

## Support

This is a demo application provided as-is. For issues related to:
- **Claude Code SDK**: [SDK Documentation](https://docs.anthropic.com/claude-code)
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