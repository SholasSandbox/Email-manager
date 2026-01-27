#!/usr/bin/env python3
"""
Configuration Checker
Verifies that all required files and dependencies are present
"""

import os
import sys
import json

def check_file_exists(filepath, description, required=True):
    """Check if a file exists"""
    exists = os.path.exists(filepath)
    status = "✓" if exists else ("✗" if required else "○")
    req_text = "REQUIRED" if required else "optional"
    print(f"  [{status}] {description} ({filepath}) - {req_text}")
    return exists

def check_json_file(filepath, description, required_keys=None):
    """Check if JSON file exists and has required keys"""
    if not os.path.exists(filepath):
        print(f"  [✗] {description} - NOT FOUND")
        return False
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if required_keys:
            missing = [key for key in required_keys if key not in data]
            if missing:
                print(f"  [✗] {description} - MISSING KEYS: {missing}")
                return False
        
        print(f"  [✓] {description} - OK")
        return True
    except json.JSONDecodeError:
        print(f"  [✗] {description} - INVALID JSON")
        return False
    except Exception as e:
        print(f"  [✗] {description} - ERROR: {e}")
        return False

def check_python_modules():
    """Check if required Python modules are installed"""
    print("\n📦 Checking Python Dependencies...")
    
    modules = [
        ('google.auth', 'google-auth'),
        ('google_auth_oauthlib', 'google-auth-oauthlib'),
        ('googleapiclient', 'google-api-python-client'),
        ('msal', 'msal'),
        ('requests', 'requests'),
    ]
    
    all_installed = True
    for module_name, package_name in modules:
        try:
            __import__(module_name)
            print(f"  [✓] {package_name}")
        except ImportError:
            print(f"  [✗] {package_name} - NOT INSTALLED")
            all_installed = False
    
    return all_installed

def main():
    print("="*60)
    print("Email Manager - Configuration Checker")
    print("="*60)
    
    # Check Python version
    print(f"\n🐍 Python Version: {sys.version}")
    if sys.version_info < (3, 7):
        print("  [✗] Python 3.7 or higher required!")
        return False
    else:
        print("  [✓] Version OK")
    
    # Check dependencies
    deps_ok = check_python_modules()
    
    # Check main script files
    print("\n📄 Checking Script Files...")
    scripts_ok = True
    scripts_ok &= check_file_exists('email_manager.py', 'Main script')
    scripts_ok &= check_file_exists('gmail_handler.py', 'Gmail handler')
    scripts_ok &= check_file_exists('outlook_handler.py', 'Outlook handler')
    scripts_ok &= check_file_exists('requirements.txt', 'Requirements file')
    
    # Check credential files
    print("\n🔑 Checking Credentials...")
    
    print("\nGmail:")
    gmail_creds = check_json_file('gmail_credentials.json', 'Gmail credentials')
    gmail_token = check_file_exists('gmail_token.pickle', 'Gmail token (auto-generated)', required=False)
    
    print("\nOutlook:")
    outlook_creds = check_json_file(
        'outlook_credentials.json', 
        'Outlook credentials',
        required_keys=['client_id']
    )
    
    # Check templates
    print("\n📋 Template Files (for reference):")
    check_file_exists('outlook_credentials.json.template', 'Outlook template', required=False)
    
    # Summary
    print("\n" + "="*60)
    print("📊 Summary")
    print("="*60)
    
    issues = []
    
    if not deps_ok:
        issues.append("Missing Python dependencies")
        print("\n💡 To install dependencies, run:")
        print("   pip install -r requirements.txt")
    
    if not scripts_ok:
        issues.append("Missing script files")
        print("\n❌ Script files missing - please re-download the project")
    
    if not gmail_creds:
        issues.append("Gmail credentials not configured")
        print("\n💡 To set up Gmail:")
        print("   1. Follow SETUP_GUIDE.md - Gmail section")
        print("   2. Download credentials from Google Cloud Console")
        print("   3. Save as 'gmail_credentials.json'")
    
    if not outlook_creds:
        issues.append("Outlook credentials not configured")
        print("\n💡 To set up Outlook:")
        print("   1. Follow SETUP_GUIDE.md - Outlook section")
        print("   2. Copy outlook_credentials.json.template")
        print("   3. Add your Azure AD Client ID")
    
    if not issues:
        print("\n✅ All checks passed!")
        print("\n🚀 Next steps:")
        print("   1. Run authentication setup:")
        print("      python email_manager.py --setup-only")
        print("   2. Test in dry-run mode:")
        print("      python email_manager.py")
        print("   3. Run live mode when ready:")
        print("      python email_manager.py --live")
    else:
        print(f"\n⚠️  Found {len(issues)} issue(s):")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("\n📖 See SETUP_GUIDE.md for detailed setup instructions")
    
    print("\n" + "="*60)

if __name__ == '__main__':
    main()
