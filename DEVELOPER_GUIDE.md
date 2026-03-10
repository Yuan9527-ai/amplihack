# Developer Guide

> This guide is for human developers. For AI agent configuration, see CLAUDE.md.

## What is Amplihack?

Amplihack is a framework for building AI-powered applications with autonomous agents.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/rysweet/amplihack.git
cd amplihack

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```python
# Import the framework
from amplihack import Agent

# Create an agent
agent = Agent(name="my-agent")

# Run a task
result = agent.run("Your task here")
```

## Core Concepts

### Agents
AI entities that can execute tasks autonomously.

### Workflows
Predefined sequences of steps for common patterns.

### Tasks
Individual units of work that agents can perform.

## Learning Path

1. Read CLAUDE.md for agent configuration
2. Start with simple tasks
3. Gradually explore workflows
4. Build complex applications

## Need Help?

- Check the FAQ in the docs folder
- Open an issue on GitHub
- Join the community

---
*Part of amplihack documentation improvement effort - Issue #2978*
