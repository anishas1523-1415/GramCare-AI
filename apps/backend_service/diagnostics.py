import os
from dotenv import load_dotenv

# Ensure we're in the right directory and loading the right .env
load_dotenv()

report = []

def format_result(name, key_exists, auth_ok, status_code, error_msg, root_cause, skipped, used):
    return f"""
### {name}
- **API Key Detected**: {'Yes' if key_exists else 'No'}
- **Authentication Successful**: {'Yes' if auth_ok else 'No'}
- **HTTP Status Code**: {status_code}
- **Provider Error**: {error_msg}
- **Root Cause**: {root_cause}
- **Skipped**: {'Yes' if skipped else 'No'}
- **Used**: {'Yes' if used else 'No'}
"""

# ----------------- GEMINI -----------------
gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key:
    report.append(format_result("Gemini", False, False, "N/A", "None", "Missing Credentials", True, False))
else:
    try:
        from google import genai
        from google.genai.errors import ClientError, APIError
        client = genai.Client(api_key=gemini_key)
        # Test basic completion
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents="Say 'OK'"
        )
        report.append(format_result("Gemini", True, True, "200", "None", "Healthy", False, True))
    except ClientError as e:
        status_code = getattr(e, "code", "Unknown")
        msg = str(e)
        if "403" in msg or "PERMISSION_DENIED" in msg:
            root_cause = "Disabled API or Invalid Credentials"
            auth_ok = False
        elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            root_cause = "Quota Exceeded"
            auth_ok = True
        else:
            root_cause = "API Error"
            auth_ok = False
        report.append(format_result("Gemini", True, auth_ok, status_code, msg, root_cause, False, False))
    except APIError as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            root_cause = "Quota Exceeded"
            auth_ok = True
        elif "403" in msg or "PERMISSION_DENIED" in msg:
            root_cause = "Disabled API or Invalid Credentials"
            auth_ok = False
        else:
            root_cause = "API Error"
            auth_ok = False
        report.append(format_result("Gemini", True, auth_ok, getattr(e, "code", "Unknown"), msg, root_cause, False, False))
    except Exception as e:
        report.append(format_result("Gemini", True, False, "Unknown", str(e), "Code/Network Error", False, False))

# ----------------- OPENAI -----------------
openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    report.append(format_result("OpenAI", False, False, "N/A", "None", "Missing Credentials", True, False))
else:
    try:
        import openai
        client = openai.OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'OK'"}]
        )
        report.append(format_result("OpenAI", True, True, "200", "None", "Healthy", False, True))
    except openai.AuthenticationError as e:
        report.append(format_result("OpenAI", True, False, "401", str(e), "Invalid Credentials", False, False))
    except openai.RateLimitError as e:
        report.append(format_result("OpenAI", True, True, "429", str(e), "Quota Exceeded", False, False))
    except openai.APIError as e:
        report.append(format_result("OpenAI", True, True, "500", str(e), "API Error", False, False))
    except Exception as e:
        report.append(format_result("OpenAI", True, False, "Unknown", str(e), "Network/Code Error", False, False))

# ----------------- GROQ -----------------
groq_key = os.getenv("GROQ_API_KEY")
if not groq_key:
    report.append(format_result("Groq", False, False, "N/A", "None", "Missing Credentials", True, False))
else:
    try:
        import groq
        client = groq.Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Say 'OK'"}]
        )
        report.append(format_result("Groq", True, True, "200", "None", "Healthy", False, True))
    except groq.AuthenticationError as e:
        report.append(format_result("Groq", True, False, "401", str(e), "Invalid Credentials", False, False))
    except groq.RateLimitError as e:
        report.append(format_result("Groq", True, True, "429", str(e), "Quota Exceeded", False, False))
    except groq.APIError as e:
        report.append(format_result("Groq", True, True, "500", str(e), "API Error", False, False))
    except Exception as e:
        report.append(format_result("Groq", True, False, "Unknown", str(e), "Network/Code Error", False, False))

# ----------------- ANTHROPIC -----------------
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_key:
    report.append(format_result("Anthropic", False, False, "N/A", "None", "Missing Credentials", True, False))
else:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say 'OK'"}]
        )
        report.append(format_result("Anthropic", True, True, "200", "None", "Healthy", False, True))
    except anthropic.AuthenticationError as e:
        report.append(format_result("Anthropic", True, False, "401", str(e), "Invalid Credentials", False, False))
    except anthropic.RateLimitError as e:
        report.append(format_result("Anthropic", True, True, "429", str(e), "Quota Exceeded", False, False))
    except anthropic.APIError as e:
        report.append(format_result("Anthropic", True, True, "500", str(e), "API Error", False, False))
    except Exception as e:
        report.append(format_result("Anthropic", True, False, "Unknown", str(e), "Network/Code Error", False, False))

print("# Provider Diagnostics Report")
print("\n".join(report))

# Determine ultimate server
print("### Ultimate Provider Served:")
if "Gemini" in report[0] and "- **Used**: Yes" in report[0]:
    print("Gemini served the request.")
elif "OpenAI" in report[1] and "- **Used**: Yes" in report[1]:
    print("OpenAI served the request.")
elif "Groq" in report[2] and "- **Used**: Yes" in report[2]:
    print("Groq served the request.")
elif "Anthropic" in report[3] and "- **Used**: Yes" in report[3]:
    print("Anthropic served the request.")
else:
    print("Mock Provider served the request. All real providers failed or were skipped.")

