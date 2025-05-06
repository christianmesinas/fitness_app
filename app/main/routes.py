from flask import session, render_template, flash, redirect, url_for, request, current_app, jsonify
from app import db, oauth
from app.forms import PostForm, EditProfileForm, EmptyForm, MessageForm
from app.models import User, Post, Message, Notification
from langdetect import detect, LangDetectException
from datetime import datetime, timezone
import sqlalchemy as sa
import logging
import secrets

logging.basicConfig(level=logging.DEBUG)

from app.main import bp


def get_current_user():
    if 'user' not in session:
        current_app.logger.debug("No user in session")
        return None
    user_info = session['user']['userinfo']
    sub = user_info.get('sub')
    if not sub:
        current_app.logger.error("No 'sub' in session user_info, forcing logout")
        session.clear()
        return None
    user = db.session.scalar(sa.select(User).where(User.sub == sub))
    if not user:
        current_app.logger.debug(f"User with sub {sub} not found in database")
    return user


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


@bp.route('/login')
def login():
    if 'user' in session:
        current_app.logger.debug("User already in session, redirecting to index")
        return redirect(url_for('main.index'))
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session.modified = True
    current_app.logger.debug(f"Generated OAuth state: {state}")
    redirect_uri = url_for('main.callback', _external=True)
    return oauth.auth0.authorize_redirect(redirect_uri=redirect_uri, state=state)


@bp.route('/signup')
def signup():
    if 'user' in session:
        current_app.logger.debug("User already in session, redirecting to index")
        return redirect(url_for('main.index'))
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session.modified = True
    current_app.logger.debug(f"Generated OAuth state for signup: {state}")
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for('main.callback', _external=True),
        screen_hint='signup',
        state=state
    )


@bp.route('/callback')
def callback():
    try:
        received_state = request.args.get('state')
        expected_state = session.get('oauth_state')
        current_app.logger.debug(f"Received state: {received_state}, Expected state: {expected_state}")

        if not expected_state or received_state != expected_state:
            current_app.logger.error(f"State mismatch: received={received_state}, expected={expected_state}")
            session.pop('oauth_state', None)
            flash('Login failed due to state mismatch. Please try again.', 'danger')
            return redirect(url_for('main.login'))

        token = oauth.auth0.authorize_access_token()
        current_app.logger.debug(f"Token received: {token}")
        session['user'] = token
        user_info = token['userinfo']
        current_app.logger.debug(f"User info: {user_info}")

        sub = user_info.get('sub')
        if not sub:
            current_app.logger.error("No 'sub' found in user_info")
            session.pop('oauth_state', None)
            flash('Login failed: No user identifier provided.', 'danger')
            return redirect(url_for('main.login'))

        user = db.session.scalar(sa.select(User).where(User.sub == sub))
        if not user:
            username = user_info.get('nickname', user_info.get('email', sub.split('|')[-1]))
            email = user_info.get('email', '')
            user = User(
                username=username,
                email=email,
                sub=sub
            )
            db.session.add(user)
            db.session.commit()
            current_app.logger.debug(f"New user added: {user.username}, sub: {sub}")
        else:
            current_app.logger.debug(f"Existing user found: {user.username}, sub: {sub}")

        session['user']['id'] = user.id
        session.modified = True
        session.pop('oauth_state', None)
        current_app.logger.debug("Login successful")
        flash('You have been logged in!', 'success')
        return redirect(url_for('main.index'))
    except Exception as e:
        current_app.logger.error(f"Error in callback: {str(e)}")
        session.pop('oauth_state', None)
        flash(f'Login failed: {str(e)}', 'danger')
        return redirect(url_for('main.login'))


@bp.route('/logout')
def logout():
    session.clear()
    current_app.logger.debug("Session cleared")
    return redirect(
        f"https://{current_app.config['AUTH0_DOMAIN']}/v2/logout?"
        f"client_id={current_app.config['AUTH0_CLIENT_ID']}&"
        f"returnTo={url_for('main.index', _external=True)}"
    )


@bp.route('/user/<username>')
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    posts = db.paginate(
        user.posts.select().order_by(Post.timestamp.desc()),
        page=page,
        per_page=current_app.config.get('POSTS_PER_PAGE', 10),
        error_out=False
    )
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
    if user is None:
        session.clear()
        return redirect(url_for('main.login'))
    form = EditProfileForm(user.username)
    if form.validate_on_submit():
        user.username = form.username.data
        user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('main.user', username=user.username))
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


@bp.route('/send_message/<recipient>', methods=['GET', 'POST'])
def send_message(recipient):
    if 'user' not in session:
        return redirect(url_for('main.login'))
    current_user = get_current_user()
    if current_user is None:
        session.clear()
        return redirect(url_for('main.login'))
    recipient_user = db.session.scalar(sa.select(User).where(User.username == recipient))
    if recipient_user is None:
        flash(f'User {recipient} not found.')
        return redirect(url_for('main.index'))
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=recipient_user, body=form.message.data)
        db.session.add(msg)
        current_user.add_notification('unread_message_count', current_user.unread_message_count())
        db.session.commit()
        flash('Your message has been sent!')
        return redirect(url_for('main.user', username=recipient))
    return render_template('send_message.html', title='Send Message', form=form, recipient=recipient)


@bp.route('/messages')
def messages():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    current_user = get_current_user()
    if current_user is None:
        session.clear()
        return redirect(url_for('main.login'))
    current_user.last_message_read_time = datetime.now(timezone.utc)
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    messages = db.paginate(
        current_user.messages_received.select().order_by(Message.timestamp.desc()),
        page=page,
        per_page=current_app.config.get('POSTS_PER_PAGE', 10),
        error_out=False
    )
    next_url = url_for('main.messages', page=messages.next_num) if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) if messages.has_prev else None
    return render_template('messages.html', messages=messages.items, next_url=next_url, prev_url=prev_url)


@bp.route('/notifications')
def notifications():
    if 'user' not in session:
        return jsonify([])
    current_user = get_current_user()
    if current_user is None:
        session.clear()
        return jsonify([])
    since = request.args.get('since', 0.0, type=float)
    notifications = db.session.scalars(
        current_user.notifications.select().where(
            Notification.timestamp > since).order_by(Notification.timestamp.asc())
    )
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])