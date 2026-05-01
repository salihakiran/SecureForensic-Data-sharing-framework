import os
class Config():
    MAIL_SERVER = os.getenv('MAIL_SERVER') 
    MAIL_PORT = os.getenv('MAIL_PORT') 
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

