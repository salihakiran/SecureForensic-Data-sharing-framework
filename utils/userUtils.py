import requests

__SERVER = 'http://127.0.0.1:5000'

def send_verification_token(email):
    try:
        response = requests.post(
            f'{__SERVER}/send-mail',
            json={"email": email}
        )

        if not response.ok:
            return "Something went wrong. Please try again.", False

        return "If an account with this email exists, check your inbox for further instructions.", True

    except requests.exceptions.RequestException:
        return "Unable to process request right now. Please try later.", False
