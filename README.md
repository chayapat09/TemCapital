

# Tem Capital



## Setup Instructions

### 1. Clone the Repository

```
git clone <repository-url>
cd TemCapital
```

### 2. Create and Activate a Virtual Environment
On UNIX/Linux/MacOS:

```
python3 -m venv venv
source venv/bin/activate
```

On Windows:
```
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```
pip install -r requirements.txt
```

### 4. Run the Application
```
python app.py
```

The app will start on http://127.0.0.1:5000.

## Optional: Running via Provided Scripts
For UNIX-like systems, you can run:
```
./run.sh
```
For Windows, double-click or run run.bat from the command prompt.

```
investment_tracker/
├── app.py
└── templates/
    ├── base.html
    ├── dashboard.html
    ├── transaction.html
    ├── cash.html
    ├── edit_position.html
    └── summary.html

```