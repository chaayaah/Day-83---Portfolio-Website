from flask import Flask, render_template, abort, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from datetime import date

from forms import RegisterForm, LoginForm, CommentForm, CreateProjectForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'adadadadasdasdasdasasd'
ckeditor = CKEditor(app)
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

# For adding profile images to the comment section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///projects.db'
db = SQLAlchemy()
db.init_app(app)

# CONFIGURE TABLES
class ProjectPost(db.Model):
    __tablename__ = "project_posts"
    id = db.Column(db.Integer, primary_key=True)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="projects")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # Parent relationship to the comments
    comments = relationship("Comment", back_populates="parent_project")


# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    # This will act like a list of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    projects = relationship("ProjectPost", back_populates="author")
    # Parent relationship: "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


# Create a table for the comments on the blog posts
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    # Child relationship:"users.id" The users refers to the tablename of the User class.
    # "comments" refers to the comments property in the User class.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    # Child Relationship to the BlogPosts
    project_id = db.Column(db.Integer, db.ForeignKey("project_posts.id"))
    parent_project = relationship("ProjectPost", back_populates="comments")


with app.app_context():
    db.create_all()


# Create an admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function

@app.route("/")
def get_all_projects():
    result = db.session.execute(db.select(ProjectPost))
    projects = result.scalars().all()
    return render_template("index.html", all_projects=projects, current_user=current_user)

# Add a POST method to be able to post comments
@app.route("/project/<int:project_id>", methods=["GET", "POST"])
def show_project(project_id):
    requested_project = db.get_or_404(ProjectPost, project_id)
    # Add the CommentForm to the route
    comment_form = CommentForm()
    # Only allow logged-in users to comment on posts
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=comment_form.comment_text.data,
            comment_author=current_user,
            parent_project=requested_project
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("project.html", project=requested_project, current_user=current_user, form=comment_form)

@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)

@app.route("/contact")
def contact():
    return render_template("contact.html",  current_user=current_user)

@app.route("/login", methods=['POST', 'GET'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        password = form.password.data
        user = result.scalar()
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash("Password is incorrect, please try again.")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_projects'))
    return render_template("login.html", form=form, current_user=current_user)

@app.route("/register", methods=['POST', 'GET'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        result = db.session.execute(db.Select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up using this email, log in instead!")
            return redirect(url_for('login'))
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for('get_all_projects'))
    return render_template("register.html", form=form, current_user=current_user)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("get_all_projects"))

# Use a decorator so only an admin user can create new posts
@app.route("/new-project", methods=["GET", "POST"])
@admin_only
def add_new_project():
    form = CreateProjectForm()
    if form.validate_on_submit():
        new_post = ProjectPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_projects"))
    return render_template("make-project.html", form=form, current_user=current_user)

# Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):
    project = db.get_or_404(ProjectPost, project_id)
    edit_form = CreateProjectForm(
        title=project.title,
        subtitle=project.subtitle,
        img_url=project.img_url,
        author=project.author,
        body=project.body
    )
    if edit_form.validate_on_submit():
        project.title = edit_form.title.data
        project.subtitle = edit_form.subtitle.data
        project.img_url = edit_form.img_url.data
        project.author = current_user
        project.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_project", project_id=project.id))
    return render_template("make-project.html", form=edit_form, is_edit=True, current_user=current_user)

# Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:project_id>")
@admin_only
def delete_project(project_id):
    post_to_delete = db.get_or_404(ProjectPost, project_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_projects'))


if __name__ == "__main__":
    app.run(debug=True)