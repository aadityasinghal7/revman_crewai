"""Email validation tools for plain text email content"""

from typing import Any, Dict
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class EmailValidatorInput(BaseModel):
    """Input schema for EmailValidatorTool"""
    text_content: str = Field(..., description="Plain text content to validate")
    subject_line: str = Field(..., description="Email subject line to validate")


class EmailValidatorTool(BaseTool):
    name: str = "Plain Text Email Validator"
    description: str = (
        "Validates plain text email content and subject line. Checks for required sections, "
        "proper formatting, subject line length, and overall quality for TBS Price Change emails."
    )
    args_schema: type[BaseModel] = EmailValidatorInput

    def _run(self, text_content: str, subject_line: str) -> str:
        """
        Validate plain text email content

        Args:
            text_content: Plain text email content
            subject_line: Email subject line

        Returns:
            Validation report as JSON string
        """
        issues = []
        warnings = []

        # Check for required title
        if "Highlights (Price Before Tax and Deposit)" not in text_content:
            issues.append("Missing required title: 'Highlights (Price Before Tax and Deposit)'")

        # Check for at least one brewer section
        brewers = ["LABATT", "MOLSON", "SLEEMAN"]
        has_brewer = any(brewer in text_content for brewer in brewers)
        if not has_brewer:
            issues.append("No brewer sections found (LABATT, MOLSON, SLEEMAN)")

        # Check for change type sections
        sections = ["Begin LTO", "End LTO"]
        has_section = any(section in text_content for section in sections)
        if not has_section:
            warnings.append("No change type sections found (Begin LTO, End LTO)")

        # Check for deprecated sections that should NOT exist
        if "Permanent Changes" in text_content or "End LTO & Perm Change" in text_content:
            warnings.append(
                "Found deprecated section: 'Permanent Changes' or 'End LTO & Perm Change'. "
                "Only 'Begin LTO' and 'End LTO' sections should exist per plan.md."
            )

        # Check subject line
        if not subject_line:
            issues.append("Empty subject line")
        elif len(subject_line) > 100:
            warnings.append(f"Subject line too long ({len(subject_line)} chars). Recommended: <100 chars")

        # Check content length
        if len(text_content) < 50:
            issues.append("Content too short - may be incomplete")

        # Calculate quality score
        quality_score = 100
        quality_score -= len(issues) * 25  # Each critical issue: -25 points
        quality_score -= len(warnings) * 10  # Each warning: -10 points
        quality_score = max(0, quality_score)

        # Determine status
        if issues:
            status = "FAIL"
        elif warnings:
            status = "PASS WITH WARNINGS"
        else:
            status = "PASS"

        # Build result
        result = {
            "status": status,
            "quality_score": quality_score,
            "critical_issues": issues,
            "warnings": warnings,
            "summary": f"Validation {status}. Quality score: {quality_score}/100"
        }

        import json
        return json.dumps(result, indent=2)
