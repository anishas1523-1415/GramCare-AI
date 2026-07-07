import urllib.request
import urllib.error
import sys

def test_endpoint(name, url):
    print(f"Testing {name} at {url}...")
    try:
        urllib.request.urlopen(url, timeout=2)
        print(f"[{name}] SUCCESS")
        return True
    except urllib.error.URLError as e:
        print(f"[{name}] FAILED - Connection Refused: {e}")
        return False
    except Exception as e:
        print(f"[{name}] FAILED - {e}")
        return False

def main():
    print("--- Starting API Integration Tests ---")
    workflows = [
        ("Authentication", "http://localhost:8000/auth/login"),
        ("Registration", "http://localhost:8000/auth/register"),
        ("Family Profiles", "http://localhost:8000/family"),
        ("Wallet", "http://localhost:8000/wallet"),
        ("AI Triage", "http://localhost:8000/ai/triage"),
        ("OCR", "http://localhost:8000/ai/ocr"),
        ("Voice", "http://localhost:8000/ai/voice"),
        ("SOS", "http://localhost:8000/emergency/sos"),
        ("Emergency escalation", "http://localhost:8000/emergency/escalate"),
        ("Payments", "http://localhost:8000/payments/checkout"),
        ("Doctor workflow", "http://localhost:8000/doctor/dashboard"),
        ("Pharmacy workflow", "http://localhost:8000/pharmacy/inventory"),
        ("Appointment workflow", "http://localhost:8000/appointments"),
        ("Offline synchronization", "http://localhost:8000/sync/offline")
    ]
    
    all_passed = True
    for name, url in workflows:
        if not test_endpoint(name, url):
            all_passed = False
            
    if not all_passed:
        print("\nSUMMARY: Tests failed. Backend server is offline or unreachable.")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
