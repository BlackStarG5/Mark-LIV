"""One-time user-run Outlook connection. Passwords stay in Microsoft's browser UI."""
import argparse
import json
import uuid
from core.home_llm import CONFIG_PATH, load_config
from core.outlook_auth import connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-id', help='Your registered Microsoft public-client application ID (not a secret).')
    args = parser.parse_args()
    client_id = args.client_id or load_config().get('outlook_client_id') or input('Microsoft application client ID: ').strip()
    uuid.UUID(client_id)
    print('Sign in and consent in the Microsoft browser window. JARVIS does not receive your password.')
    connect(client_id)
    config = load_config()
    config['outlook_client_id'] = client_id
    CONFIG_PATH.write_text(json.dumps(config, indent=4), encoding='utf-8')
    print('Outlook calendar connected. Restart JARVIS if it is running.')


if __name__ == '__main__':
    main()
