from flask import Flask, render_template, request, redirect, session, send_file, send_from_directory
from datetime import datetime, timedelta
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import sqlite3
import os
import time

def init_db():
    conn = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        membership_type TEXT,
        join_date TEXT,
        expiry_date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER,
        file_name TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    cursor.execute("SELECT * FROM admin WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO admin (username,password) VALUES (?,?)",
            ("admin","admin123")
        )

    conn.commit()
    conn.close()

app = Flask(__name__)
app.secret_key = "memberhub_secret"
init_db()

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory("uploads", filename)

UPLOAD_FOLDER = "uploads"
os.makedirs("uploads", exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER




  # Home Page
@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("memberhub.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM admin WHERE username=? AND password=?",
            (username,password)
        )

        admin = cursor.fetchone()
        conn.close()

        if admin:
            session["admin"] = username
            return redirect("/dashboard")
        else:
            return "Invalid Login"

    return render_template("login.html")

  # Add Member Page
@app.route("/add_member")
def add_member(): 
    return render_template("add_member.html")


  # Save Member to Database
@app.route("/save_member", methods=["POST"])
def save_member(): 
    name            = request.form["name"]
    email           = request.form["email"]
    phone           = request.form["phone"]
    membership_type = request.form["membership_type"]
    join_date       = request.form["join_date"]
    expiry_date     = request.form["expiry_date"]

    conn   = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO members (name,email,phone,membership_type,join_date,expiry_date)
    VALUES (?,?,?,?,?,?)
    """,(name,email,phone,membership_type,join_date,expiry_date))

    conn.commit()
    conn.close()

    return redirect("/add_member")


  #view members
@app.route("/members")
def members(): 

    conn   = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members")
    members = cursor.fetchall()

    conn.close()

    return render_template("members.html", members=members)


  #dashboard
@app.route("/dashboard")
def dashboard():

    if "admin" not in session:
        return redirect("/")
    
    conn = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    # TOTAL MEMBERS
    cursor.execute("SELECT COUNT(*) FROM members")
    total = cursor.fetchone()[0]

    # EXPIRING MEMBERS (within 7 days)
    cursor.execute("""
    SELECT COUNT(*) FROM members
    WHERE expiry_date <= date('now','+7 day')
    """)
    expiring = cursor.fetchone()[0]

    # EXPIRING MEMBER LIST
    cursor.execute("""
    SELECT name, expiry_date
    FROM members
    WHERE expiry_date <= date('now','+7 day')
    ORDER BY expiry_date
    """)
    
    expiring_members = cursor.fetchall()

    # RECENT MEMBERS
    cursor.execute("""
    SELECT name,email,membership_type
    FROM members
    ORDER BY id DESC
    LIMIT 5
    """)
    recent = cursor.fetchall()

    # MEMBERSHIP TYPES
    cursor.execute("""
    SELECT membership_type, COUNT(*)
    FROM members
    GROUP BY membership_type
    """)
    type_data = cursor.fetchall()

    # MEMBER GROWTH (LAST 7 DAYS)
    cursor.execute("""
    SELECT date(join_date), COUNT(*)
    FROM members
    GROUP BY date(join_date)
    """)
    
    data = dict(cursor.fetchall())

    growth_data = []
    
    for i in range(6, -1, -1):
        day = (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = data.get(day, 0)
        growth_data.append([day, count])

    # CERTIFICATES COUNT
    cursor.execute("SELECT COUNT(*) FROM documents")
    certificates = cursor.fetchone()[0]

    conn.close()

    return render_template(
       "dashboard.html",
       total=total,        
       expiring=expiring,
       recent=recent,
       type_data=type_data,
       growth_data=growth_data,
       certificates=certificates,
       expiring_members=expiring_members
       
    )
  #delete member
@app.route("/delete/<int:id>")
def delete_member(id): 

    conn   = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM members WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/members")


#generate certificates 
@app.route("/generate_certificate/<name>")
def generate_certificate(name):

    file_path = f"certificates/{name}_certificate.pdf"
    os.makedirs("certificates", exist_ok=True)
    c = canvas.Canvas(file_path, pagesize=letter)

    # Border
    c.setStrokeColor(black)
    c.rect(30, 30, 550, 730)

    # Title
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(300, 700, "Certificate of Membership")

    # Subtitle
    c.setFont("Helvetica", 18)
    c.drawCentredString(300, 640, "This certificate is proudly presented to")

    # Member Name
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(300, 600, name)

    # Description
    c.setFont("Helvetica", 16)
    c.drawCentredString(300, 560, "for being a valued member of MemberHub")

    # Footer
    c.setFont("Helvetica", 14)
    c.drawCentredString(300, 500, "Congratulations!")

    c.save()

    return send_file(file_path, as_attachment=True)


@app.route("/search", methods=["GET"])
def search():

    query = request.args.get("query", "")

    conn = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM members WHERE name LIKE ? OR email LIKE ?",
        ('%' + query + '%', '%' + query + '%')
    )

    members = cursor.fetchall()

    conn.close()

    return render_template("members.html", members=members)


@app.route("/edit/<int:id>")
def edit_member(id):

    conn = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM members WHERE id=?", (id,))
    member = cursor.fetchone()

    conn.close()

    return render_template("edit_member.html", member=member)


@app.route("/update_member", methods=["POST"])
def update_member():

    id = request.form["id"]
    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]
    membership_type = request.form["membership_type"]
    join_date = request.form["join_date"]
    expiry_date = request.form["expiry_date"]

    conn = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE members
    SET name=?, email=?, phone=?, membership_type=?, join_date=?, expiry_date=?
    WHERE id=?
    """,(name,email,phone,membership_type,join_date,expiry_date,id))

    conn.commit()
    conn.close()

    return redirect("/members")


@app.route("/upload/<int:id>", methods=["GET","POST"])
def upload(id):

    if request.method == "POST":

        file = request.files["file"]

        if file:

            timestamp = int(time.time())

            filename = f"{id}_{timestamp}_{file.filename}"

            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            file.save(filepath)

            conn = sqlite3.connect("memberhub.db")
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO documents (member_id,file_name) VALUES (?,?)",
                (id, filename)
            )

            conn.commit()
            conn.close()

            return redirect("/members")

    return render_template("upload.html", member_id=id)


@app.route("/documents/<int:id>")
def documents(id):

    conn = sqlite3.connect("memberhub.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_name FROM documents WHERE member_id=?",
        (id,)
    )

    docs = cursor.fetchall()

    conn.close()

    return render_template("documents.html", docs=docs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
