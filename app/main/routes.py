from flask import session, render_template, flash, redirect, url_for, request, current_app, jsonify
from app import db, oauth
from app.forms import PostForm, EditProfileForm, EmptyForm, MessageForm
from app.models import User, Post, Message, Notification
from langdetect import detect, LangDetectException
from datetime import datetime, timezone
import sqlalchemy as sa
import logging

logging.basicConfig(level=logging.DEBUG)

from app.main import bp

def get_current_user():
    if 'user' in session:
        user_info = session['user']['userinfo']
        current_app.logger.debug(f"Checking user with email: {user_info['email']}")
        user = db.session.scalar(sa.select(User).where(User.email == user_info['email']))
        if not user:
            current_app.logger.debug("User not found in database, should have been created in callback")
        return user
    current_app.logger.debug("No user in session")
    return None

@bp.context_processor
def inject_current_user():
    return dict(get_current_user=get_current_user)

@bp.before_request
def before_request():
    user = get_current_user()
    if user:
        user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        current_app.logger.debug('Rendering landings.html')
        return render_template('landings.html', title='Welcome to FitTrack', is_landing_page=True)
    user = get_current_user()
    if user is None:
        current_app.logger.error("User is None despite session, forcing logout")
        session.clear()
        return redirect(url_for('main.login'))
    form = PostForm()
    if form.validate_on_submit():
        try:
            language = detect(form.post.data)
        except LangDetectException:
            language = ''
        post = Post(body=form.post.data, author=user, language=language)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(user.following_posts(), page=page,
                        per_page=current_app.config.get('POSTS_PER_PAGE', 10), error_out=False)
    next_url = url_for('main.index', page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) if posts.has_prev else None
    return render_template('index.html', title='Home', form=form,
                           posts=posts.items, next_url=next_url, prev_url=prev_url, is_landing_page=False)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('main.index'))
    current_app.logger.debug('Initiating Auth0 login')
    callback_url = current_app.config.get('AUTH0_CALLBACK_URL')
    if not callback_url:
        current_app.logger.error("AUTH0_CALLBACK_URL is not set in app.config")
        return "Configuration error: AUTH0_CALLBACK_URL is missing", 500
    return oauth.auth0.authorize_redirect(redirect_uri=callback_url)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user' in session:
        return redirect(url_for('main.index'))
    current_app.logger.debug('Initiating Auth0 signup')
    callback_url = current_app.config.get('AUTH0_CALLBACK_URL')
    if not callback_url:
        current_app.logger.error("AUTH0_CALLBACK_URL is not set in app.config")
        return "Configuration error: AUTH0_CALLBACK_URL is missing", 500
    authorize_params = {'screen_hint': 'signup'}
    return oauth.auth0.authorize_redirect(
        redirect_uri=callback_url,
        **authorize_params
    )

@bp.route('/callback')
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        current_app.logger.debug(f"Token received: {token}")
        session['user'] = token
        user_info = token['userinfo']
        current_app.logger.debug(f"User info: {user_info}")
        user = db.session.scalar(sa.select(User).where(User.email == user_info['email']))
        if not user:
            user = User(
                username=user_info.get('nickname', user_info['email'].split('@')[0]),
                email=user_info['email']
            )
            db.session.add(user)
            db.session.commit()
            current_app.logger.debug(f"New user added: {user.email}")
        else:
            current_app.logger.debug(f"Existing user found: {user.email}")
        current_app.logger.debug(f"Session after callback: {session}")
        return redirect(url_for('main.index'))
    except Exception as e:
        current_app.logger.error(f"Error in callback: {str(e)}")
        return f"An error occurred during login: {str(e)}", 500

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(
        f"https://{current_app.config['AUTH0_DOMAIN']}/v2/logout?"
        f"returnTo={url_for('main.index', _external=True)}&client_id={current_app.config['AUTH0_CLIENT_ID']}"
    )

@bp.route('/user/<username>')
def user(username):
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    query = user.posts.select().order_by(Post.timestamp.desc())
    posts = db.paginate(query, page=page,
                        per_page=current_app.config.get('POSTS_PER_PAGE', 10), error_out=False)
    next_url = url_for('main.user', username=user.username, page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username, page=posts.prev_num) if posts.has_prev else None
    form = EmptyForm()
    return render_template('user.html', user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form)

@bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user = get_current_user()
    form = EditProfileForm(user.username)
    if form.validate_on_submit():
        user.username = form.username.data
        user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = user.username
        form.about_me.data = user.about_me
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@bp.route('/follow/<username>', methods=['POST'])
def follow(username):
    if 'user' not in session:
        return redirect(url_for('main.login'))
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        current_user = get_current_user()
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot follow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(f'You are following {username}!')
        return redirect(url_for('main.user', username=username))
    return redirect(url_for('main.index'))

@bp.route('/unfollow/<username>', methods=['POST'])
def unfollow(username):
    if 'user' not in session:
        return redirect(url_for('main.login'))
    form = EmptyForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == username))
        current_user = get_current_user()
        if user is None:
            flash(f'User {username} not found.')
            return redirect(url_for('main.index'))
        if user == current_user:
            flash('You cannot unfollow yourself!')
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You are not following {username}.')
        return redirect(url_for('main.user', username=username))
    return redirect(url_for('main.index'))

@bp.route('/messages')
def messages():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    current_user = get_current_user()
    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    query = current_user.messages_received.select().order_by(Message.timestamp.desc())
    messages = db.paginate(query, page=page,
                           per_page=current_app.config.get('POSTS_PER_PAGE', 10), error_out=False)
    next_url = url_for('main.messages', page=messages.next_num) if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) if messages.has_prev else None
    return render_template('messages.html', messages=messages.items,
                           next_url=next_url, prev_url=prev_url)

@bp.route('/notifications')
def notifications():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    current_user = get_current_user()
    since = request.args.get('since', 0.0, type=float)
    query = current_user.notifications.select().where(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    notifications = db.session.scalars(query)
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])

@bp.route('/send_message/<recipient>', methods=['GET', 'POST'])
def send_message(recipient):
    if 'user' not in session:
        return redirect(url_for('main.login'))
    current_user = get_current_user()
    recipient_user = db.session.scalar(sa.select(User).where(User.username == recipient))
    if recipient_user is None:
        flash(f'User {recipient} not found.')
        return redirect(url_for('main.index'))
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=recipient_user, body=form.message.data)
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent.')
        return redirect(url_for('main.user', username=recipient))
    return render_template('send_message.html', title='Send Message', form=form, recipient=recipient)