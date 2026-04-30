from flask_mail import Message


_DOMAIN="localhost:5000"
class SendEmail():
    def __init__(self, recipient_email , type_email , verfication_token , subject, mail):
        self.recipient_email = recipient_email
        self.verification_token = verfication_token
        self.subject = subject
        self.verify_url = f"http://{_DOMAIN}/verify-mail/{self.verification_token}"
        self.type = type_email
        self.body = ""
        self.mail = mail 

    def send(self):


        if self.type == "verify":
            self.body = f"Click on the link to verify your account: {self.verify_url}"
        
        print(f"Sending verification code {self.verification_token} to {self.recipient_email}")

        msg = Message(self.subject, recipients=[self.recipient_email], body=self.body)

        self.mail.send(msg)

