from flask import Flask, request, jsonify
from ..database_helper import get_db_connection
from emailService.sendMail import SendMail
from flask_mail import Mail
from emailService.config import Config

from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)
mail = Mail()

app.config.from_object(Config)

mail.init_app(app)


@app.route("/send-mail/", methods=["POST"])
def handle_sendmail():
    body = request.get_json()

    email = body.get('email')
    token = body.get('token')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("select email from users where email = ?", (email,)).findone()

    
    mail_manager = SendMail(
        email,
        "VERIFICATION",
        token,
        "Email Verification For secureforensic_fyp account",
        mail
        )

    try:

        mail_manager.send()
        return jsonify({"ok": True, "message": "Email sent"})
    except Exception as e:
        print("CRITICAL ERROR:", e)
        return jsonify({"ok": False, "message": "Failed to send email"}), 500


@app.route("/verify-mail/<token>", methods=["GET"])
def handle_token_verification(token):
    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute(
        "SELECT name FROM users WHERE verification_token = ?",
        (token,)
    ).fetchone()

    if not user:
        return jsonify({"ok": False, "message": "Invalid Token"}), 404

    cursor.execute(
        "UPDATE users SET is_verified = 1 WHERE verification_token = ?",
        (token,)
    )
    conn.commit()

    return jsonify({"ok": True, "message": "User Verified Successfully"})


if __name__ == '__main__':
    app.run(debug=True)
