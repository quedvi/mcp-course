#!/usr/bin/env python3
"""
Module 1: Basic MCP Server - Starter Code
"""

import json
import subprocess
from pathlib import Path
from typing import Optional
# import asyncio
import os

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("pr-agent")

# PR template directory (shared across all modules)
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# Default PR templates
DEFAULT_TEMPLATES = {
    "bug.md": "Bug Fix",
    "feature.md": "Feature",
    "docs.md": "Documentation",
    "refactor.md": "Refactor",
    "test.md": "Test",
    "performance.md": "Performance",
    "security.md": "Security"
}

# Type mapping for PR templates
TYPE_MAPPING = {
    "bug": "bug.md",
    "fix": "bug.md",
    "feature": "feature.md",
    "enhancement": "feature.md",
    "docs": "docs.md",
    "documentation": "docs.md",
    "refactor": "refactor.md",
    "cleanup": "refactor.md",
    "test": "test.md",
    "testing": "test.md",
    "performance": "performance.md",
    "optimization": "performance.md",
    "security": "security.md"
}


@mcp.tool()
async def analyze_file_changes(
    base_branch: str = "main", 
    include_diff: bool = True,
    max_diff_lines: int = 500,
    working_dir: Optional[str] = None
) -> str:
    """Get the diff and list of changed files in the current git repository with smart output limiting.

    Args:
        base_branch: Base branch to compare against (default: main)
        include_diff: Include the full diff content (default: true)
        max_diff_lines: Maximum number of diff lines to return (default: 500)
        working_dir: Optional working directory to run git commands in (default: None, uses MCP context root)
    """
    if working_dir is None:
        try:
            context = mcp.get_context()
            roots_result = await context.session.list_roots()
            working_dir = roots_result.roots[0].uri.path
        except Exception:
            pass # use current working directory
        finally:
            working_dir = working_dir or os.getcwd()
    try:
        result = subprocess.run(
            ["git", "diff", f"{base_branch}..HEAD"], 
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        
        diff_output = result.stdout
        if not diff_output:
            return json.dumps({"message": "No changes detected."})
        
        # Limit the diff output to max_diff_lines
        diff_lines = diff_output.splitlines()
        if len(diff_lines) > max_diff_lines:
            truncated = "\n".join(diff_lines[:max_diff_lines]) + "\n... (truncated)"
            
        stats_result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}..HEAD"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        
        # get files changed
        file_status = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
            capture_output=True,
            text=True,
            cwd=working_dir
        )

        # get files changed
        changed_files = file_status.stdout.strip().splitlines()
        
        # Get commit messages for context
        commits_result = subprocess.run(
            ["git", "log", "--oneline", f"{base_branch}..HEAD"],
            capture_output=True,
            text=True,
            cwd=working_dir
        )
        
    except subprocess.CalledProcessError as e:
        return json.dumps({"error": f"Git error: {e.stderr}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

    result = {
        "base_branch": base_branch,
        "files_changed": changed_files,
        "statistics": stats_result.stdout.strip(),
        "commits": commits_result.stdout.strip(),
        "diff": diff_output.strip() if include_diff else "Use include_diff=True to see the diff.",
        "truncated": truncated if len(diff_lines) > max_diff_lines else diff_output.strip(),
        "total_diff_lines": len(diff_lines) if include_diff else 0,
    }
    
    return json.dumps(result, indent=2)


@mcp.tool()
async def get_pr_templates() -> str:
    """List available PR templates with their content."""
    templates = [
        {
            "filename": filename,
            "type": template_type,
            "content": (TEMPLATES_DIR / filename).read_text()
        }
        for filename, template_type in DEFAULT_TEMPLATES.items()
    ]
    
    return json.dumps(templates, indent=2)


@mcp.tool()
async def suggest_template(changes_summary: str, change_type: str) -> str:
    """Let Claude analyze the changes and suggest the most appropriate PR template.
    
    Args:
        changes_summary: Your analysis of what the changes do
        change_type: The type of change you've identified (bug, feature, docs, refactor, test, etc.)
    """
    
    # Get available templates
    templates_response = await get_pr_templates()
    templates = json.loads(templates_response)
    
    # Find matching template
    template_file = TYPE_MAPPING.get(change_type.lower(), "feature.md")
    selected_template = next(
        (t for t in templates if t["filename"] == template_file),
        templates[0]  # Default to first template if no match
    )
    
    suggestion = {
        "recommended_template": selected_template,
        "reasoning": f"Based on your analysis: '{changes_summary}', this appears to be a {change_type} change.",
        "template_content": selected_template["content"],
        "usage_hint": "Claude can help you fill out this template based on the specific changes in your PR."
    }
    
    return json.dumps(suggestion, indent=2)

if __name__ == "__main__":
    mcp.run()
    # print("Starting MCP server...")
    # print("working_dir:", os.getcwd())
    # print("")
    # result = asyncio.run(
    #     analyze_file_changes(base_branch="develop", include_diff=True, max_diff_lines=100, working_dir=os.getcwd())
    # )
    # print(result)  # For testing purposes, run the tool directly