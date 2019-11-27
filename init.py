from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

SALT = 'cs3083'

app = Flask(__name__)
app.secret_key = "tmCVrJ1srQpgre4q4rpmjeNK8gcX9A5h" # secret key

IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    username = session["username"]
    groupsLst = groups(username)
    return render_template("upload.html",groups=groupsLst)

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo"
    with connection.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        hashedPassword = hashlib.sha256((requestData["password"] + SALT).encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        hashedPassword = hashlib.sha256((requestData["password"] + SALT).encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

# part 3 implementation

def groups(username):
    groups = []
    query = "SELECT groupName FROM friendgroup WHERE groupOwner = %s"
    with connection.cursor() as cursor:
        cursor.execute(query, (username))
        result = cursor.fetchall() # [{groupName:group1},{groupName:group2}...]
        for data in result:
            groups.append(data['groupName'])
        cursor.close()
    return groups

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    username = session["username"]
    groupsLst = groups(username)
    if request.files:
        image_file = request.files.get("imageFile", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        caption = request.form["caption"]
        image_file.save(filepath)
        try:
            if request.form["allFollowers"]:
                allFollowers = 1
        except:
            allFollowers = 0

        # upload file to database
        insert = "INSERT INTO photo \
            (postingdate, filePath, allFollowers, caption, photoPoster)\
            VALUES (%s, %s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(insert, (time.strftime('%Y-%m-%d %H:%M:%S'),\
                filepath, allFollowers, caption, username))
            connection.commit()
        cursor.close()
        message = "Image has been successfully uploaded."
        if not allFollowers: # share the photo with groups specified
            groupSelected = request.form.getlist("groups")
            for group in groupSelected:
                insert = "INSERT INTO sharedwith(groupOwner, groupName, photoID)\
                    VALUES(%s, %s, LAST_INSERT_ID())"
                with connection.cursor() as cursor:
                    cursor.execute(insert, (username, group))
                    connection.commit()
            cursor.close()

        return render_template("upload.html", groups=groupsLst,message=message, color="green")
    else:
        message = "Failed, to upload. Please select a file."
        return render_template("upload.html", groups=groupsLst,message=message, color="red")

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()