"""
Google Calendar OAuth Setup — run this to authenticate.
Always prompts for account selection so you can pick the right Google account.
Usage:  python auth_calendar.py
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def main():
    if not os.path.exists('credentials.json'):
        print("Error: credentials.json not found in this directory!")
        return

    # Delete existing token so we always get a fresh login
    if os.path.exists('token.json'):
        os.remove('token.json')
        print("Removed old token.json")

    print("Starting OAuth flow — a browser window will open.")
    print("Please sign in with: imthedangersaymyname@gmail.com")
    print()

    try:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        # prompt='consent' forces the account picker + consent screen every time
        creds = flow.run_local_server(port=0, prompt='consent')

        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        print()
        print("Success! token.json saved for the selected account.")
        print("Restart the backend to pick up the new token.")
    except Exception as e:
        print(f"An error occurred during authentication: {e}")

if __name__ == '__main__':
    main()
