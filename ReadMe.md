# ⚙️ Setup Instructions

Before running the application, make sure all required backend services are properly set up and running.

## 🔴 Important Requirements

### 1. Create and Activate Virtual Environment

It is **strongly recommended** to run everything inside a virtual environment.

#### Create venv:

```bash
python -m venv venv
```

#### Activate venv:

* **Windows:**

```bash
venv\Scripts\activate
```

* **Linux / macOS:**

```bash
source venv/bin/activate
```

---

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3. Run Flask Service (Main Backend)

Make sure the Flask server is running before using the application.

```bash
python app.py
```

---

### 4. Run Email Service (Required ⚠️)

The email service is a separate backend and **must be running**.

Navigate to the email service directory and start the server:

```bash
cd secureforensics_fyp/emailService
python server.py
```

---

## 🚨 Important Notes

* The application **will not work correctly** if:

  * Flask backend is not running
  * Email service is not running
  * Virtual environment is not activated

* Always start both services before using the system.

---

## ✅ Quick Start Summary

```bash
git clone {paste repo url} secureforensics_fyp
then move into project dir

cd secureforensics_fyp


# activate venv
# install dependencies

pip install -r requirements.txt

# run main backend
python app.py

# run email service (in another terminal)
cd emailService
python server.py
```

---

If you run into issues, double-check that both servers are active and no ports are conflicting.

