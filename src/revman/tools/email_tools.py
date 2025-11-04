"""Email formatting and validation tools for generating HTML emails"""

from typing import Any, Dict
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import re
from datetime import datetime


class TextToHTMLInput(BaseModel):
    """Input schema for TextToHTMLFormatterTool"""
    text_content: str = Field(..., description="Plain text content to convert to HTML")
    title: str = Field("Price Change Highlights", description="Email title")


class TextToHTMLFormatterTool(BaseTool):
    name: str = "Text to HTML Email Formatter"
    description: str = (
        "Converts structured plain text into professional HTML email format. "
        "Applies ABI styling, colors price changes (green for decreases, red for increases), "
        "and ensures mobile-responsive design with inline CSS."
    )
    args_schema: type[BaseModel] = TextToHTMLInput

    def _run(self, text_content: str, title: str = "Price Change Highlights") -> str:
        """
        Convert plain text to formatted HTML email

        Args:
            text_content: Plain text content with structure
            title: Email title

        Returns:
            Complete HTML email string
        """
        try:
            # Start building HTML
            html_parts = []

            # HTML header with DOCTYPE and meta tags
            html_parts.append('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>''' + title + '''</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="padding: 20px 0; text-align: center;">
                <table role="presentation" style="width: 600px; margin: 0 auto; background-color: #ffffff; border-collapse: collapse;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 30px; background-color: #c8102e; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">''' + title + '''</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 30px;">
''')

            # Process content line by line
            lines = text_content.strip().split('\n')

            for line in lines:
                line = line.strip()

                if not line:
                    # Empty line - add spacing
                    html_parts.append('<div style="margin: 10px 0;"></div>')
                    continue

                # Check if it's a brewer header (all caps, short)
                if line.isupper() and len(line.split()) <= 3 and not any(c in line for c in '+-$()'):
                    html_parts.append(f'<h2 style="margin: 20px 0 10px 0; color: #c8102e; font-size: 20px; font-weight: bold;">{line}</h2>')

                # Check if it's a section header (Begin LTO, End LTO, etc.)
                elif any(keyword in line for keyword in ['Begin LTO', 'End LTO', 'Permanent Changes', 'Perm Change']):
                    html_parts.append(f'<h3 style="margin: 15px 0 8px 0; color: #333333; font-size: 16px; font-weight: bold;">{line}</h3>')

                # Product line with price change
                elif '-$' in line or '+$' in line:
                    # Determine color based on price change
                    if '-$' in line:
                        # Price decrease (green)
                        color = '#28a745'
                    elif '+$' in line:
                        # Price increase (red)
                        color = '#dc3545'
                    else:
                        color = '#0066cc'

                    html_parts.append(f'<div style="margin: 5px 0; padding-left: 20px; color: {color}; font-size: 14px;">{line}</div>')

                # Default paragraph
                else:
                    html_parts.append(f'<p style="margin: 10px 0; color: #333333; font-size: 14px;">{line}</p>')

            # Footer
            current_date = datetime.now().strftime("%B %d, %Y")
            html_parts.append('''
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px; background-color: #f8f9fa; text-align: center; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0; color: #6c757d; font-size: 12px;">
                                Generated on ''' + current_date + '''<br>
                                Anheuser-Busch InBev Revenue Management<br>
                                Price Before Tax and Deposit
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>''')

            html_email = '\n'.join(html_parts)

            return html_email

        except Exception as e:
            return f"Error converting text to HTML: {str(e)}"


class EmailValidatorInput(BaseModel):
    """Input schema for EmailValidatorTool"""
    html_content: str = Field(..., description="HTML content to validate")
    subject_line: str = Field(..., description="Email subject line to validate")


class EmailValidatorTool(BaseTool):
    name: str = "Email Validator"
    description: str = (
        "Validates HTML email content and subject line. Checks HTML structure, "
        "email client compatibility, subject line length, and overall quality."
    )
    args_schema: type[BaseModel] = EmailValidatorInput

    def _run(self, html_content: str, subject_line: str) -> str:
        """
        Validate email content and structure

        Args:
            html_content: HTML email content
            subject_line: Email subject line

        Returns:
            Validation report as JSON string
        """
        try:
            import json

            issues = []
            warnings = []

            # Validate HTML structure
            if not html_content.strip().startswith('<!DOCTYPE'):
                warnings.append("Missing DOCTYPE declaration")

            if '<html' not in html_content:
                issues.append("Missing <html> tag")

            if '<head' not in html_content:
                issues.append("Missing <head> section")

            if '<body' not in html_content:
                issues.append("Missing <body> tag")

            # Check for inline CSS (required for email clients)
            if 'style=' not in html_content:
                warnings.append("No inline CSS found - may not render well in email clients")

            # Validate subject line
            if len(subject_line) > 60:
                warnings.append(f"Subject line too long ({len(subject_line)} chars, recommended max 60)")

            if len(subject_line) < 10:
                warnings.append("Subject line too short (min 10 chars recommended)")

            # Check for common issues
            if '<script' in html_content.lower():
                issues.append("JavaScript detected - not supported in emails")

            if '<link' in html_content.lower() and 'rel=' in html_content.lower():
                warnings.append("External stylesheet link detected - may not work in all email clients")

            # Check for mobile responsiveness
            if 'viewport' not in html_content:
                warnings.append("Missing viewport meta tag - may not be mobile-responsive")

            # Determine validation status
            if issues:
                status = "FAIL"
                quality_score = 50
            elif warnings:
                status = "PASS WITH WARNINGS"
                quality_score = 75
            else:
                status = "PASS"
                quality_score = 100

            result = {
                "validation_status": status,
                "quality_score": quality_score,
                "critical_issues": issues,
                "warnings": warnings,
                "html_length": len(html_content),
                "subject_line_length": len(subject_line),
                "has_inline_css": 'style=' in html_content,
                "is_mobile_responsive": 'viewport' in html_content,
                "summary": f"Validation {status}. Found {len(issues)} critical issues and {len(warnings)} warnings."
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error validating email: {str(e)}"
