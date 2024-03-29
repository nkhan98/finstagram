'''
Nabiha Khan 
Databases Project - Finstagram 
CS 3083, Professor Frankl
Last Updated: 12/11/19 

Optional Features:
Add Friend Group 
Manage Requests 

'''



from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time
from PIL import Image

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
    username = session["username"]
    # get the users information
    cursor = connection.cursor()
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    data = cursor.fetchone()
    firstName = data["firstName"]
    lastName = data["lastName"]
    # get the photos visible to the username 
    query = "SELECT photoID,postingdate,filepath,caption,photoPoster FROM photo WHERE photoPoster = %s OR photoID IN \
    (SELECT photoID FROM Photo WHERE photoPoster != %s AND allFollowers = 1 AND photoPoster IN \
    (SELECT username_followed FROM follow WHERE username_follower = %s AND username_followed = photoPoster AND followstatus = 1)) OR photoID IN \
    (SELECT photoID FROM sharedwith NATURAL JOIN belongto NATURAL JOIN photo WHERE member_username = %s AND photoPoster != %s) ORDER BY postingdate DESC"
    cursor.execute(query, (username, username, username, username, username))
    data = cursor.fetchall()
    for post in data: # post is a dictionary within a list of dictionaries for all the photos
        # append the users tagged in the photo, if any 
        query = 'SELECT username, firstName, lastName FROM tagged NATURAL JOIN person WHERE tagstatus = 1 AND photoID = %s'
        cursor.execute(query, (post['photoID']))
        result = cursor.fetchall()
        if (result):
            post['tagees'] = result
        # append the owner info 
        query = 'SELECT firstName, lastName FROM person WHERE username = %s'
        cursor.execute(query, (post['photoPoster']))
        ownerInfo = cursor.fetchone()
        post['firstName'] = ownerInfo['firstName']
        post['lastName'] = ownerInfo['lastName']
        # append the users that liked the photo with rating 
        query = "SELECT username,rating FROM likes WHERE photoID = %s"
        cursor.execute(query, (post['photoID']))
        result = cursor.fetchall()
        if (result):
            post['likers'] = result 


    cursor.close()
    print(data)
    return render_template("images.html", images=data)

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


@app.route("/tag", methods=["POST","GET"])
@login_required
def tag():
    return render_template("tag.html")

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        hashedPassword = hashlib.sha256((requestData["password"] + SALT).encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        bio = requestData["bio"]
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName, bio) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName, bio))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    
        flash("Account created successfully! You can now login!", "success")
        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/follow", methods = ["GET", "POST"])
@login_required
def follow():
    if request.form: # submitted
        username = request.form["username"]
        # check if the username exists
        cursor = connection.cursor()
        query = "SELECT * FROM person WHERE username = %s" #query to check 
        cursor.execute(query, (username))
        data = cursor.fetchone() 

        if data: # if there is a username with 'username'
            # we found the username, send a follow request 
            query = "SELECT * FROM follow WHERE username_followed = %s \
            AND username_follower = %s"
            # check if request has been sent already
            cursor.execute(query, (username, session['username']))
            data = cursor.fetchone()
            if (data): # we already sent the request before
                # check the followstatus 
                if (data['followstatus'] == 1):
                    flash(f"You already follow {username}!", "danger")
                else:
                    flash(f"You already sent a request to {username}","danger")

            else:  # good to go 
                query = "INSERT INTO follow VALUES(%s,%s,0)"
                connection.commit()
                cursor.execute(query, (username, session['username']))
                flash(f"Successfully sent a request to {username}","success")

        else: # the username was not found
            flash("That username does not exist, try another one", "danger")
        return redirect(url_for("follow"))

    return render_template("follow.html")

@app.route("/manageFriendRequests", methods=["GET","POST"])
@login_required
def manageRequests():
    # get all the requests that have followstatus = 0 for the current user 
    cursor = connection.cursor()
    query = "SELECT username_follower FROM follow WHERE username_followed = %s AND followstatus = 0"
    cursor.execute(query, (session["username"]))
    data = cursor.fetchall()
    if request.form:
        chosenUsers = request.form.getlist("chooseUsers")
        for user in chosenUsers:
            if request.form['action'] ==  "Accept":
                query = "UPDATE follow SET followstatus = 1 WHERE username_followed=%s\
                AND username_follower = %s"
                cursor.execute(query, (session['username'], user))
                connection.commit()
                flash("The selected friend requests have been accepted!", "success")
            elif request.form['action'] == "Decline":
                query = "DELETE FROM follow WHERE username_followed = %s\
                AND username_follower = %s"
                cursor.execute(query, (session['username'], user))
                connection.commit()
                flash("The selected friend requests have been deleted", "success")
        return redirect(url_for("manageRequests"))
        # handle form goes here 
    cursor.close()
    return render_template("manageFriendRequests.html", followers = data)


@app.route("/createFriendGroup", methods = ["GET", "POST"])
@login_required
def creategroup():
    if request.form: #perform a check to ensure that the current user doesn't have the specific group
        groupName = request.form["groupName"]
        description = request.form["description"]
        cursor = connection.cursor()
        query = "SELECT * FROM friendgroup WHERE groupOwner = %s AND groupName = %s"
        cursor.execute(query, (session["username"], groupName))
        data = cursor.fetchone()
        if data: 
            flash(f"You already own a friend group with the name {groupName}. Please try another.")
            return redirect(url_for("creategroup"))
        else:
            query = "INSERT INTO friendgroup VALUES(%s,%s,%s)"
            cursor.execute(query, (session['username'], groupName, description))
            connection.commit()
            flash(f"Successfully created the {groupName} group", "success")
            return redirect(url_for("creategroup"))
    return render_template("createFriendGroup.html")

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

def save_picture(picture):
    picture_path = os.path.join(app.root_path, 'static/images', picture.filename)
    output_size = (400, 500)
    i = Image.open(picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture.filename

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    username = session["username"]
    groupsLst = groups(username)
    if request.files:
        image_file = request.files.get("imageFile", "")
        filepath = save_picture(image_file)
        caption = request.form["caption"]
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