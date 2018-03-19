from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from functools import wraps
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Movie_Items
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
import datetime

#CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']
#json_data = json.loads(open('client_secrets.json', 'r'))

#CLIENT_ID = json_data['web']['client_id']

app = Flask(__name__)

engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html')

@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output

@app.route('/category/<int:category_id>/movie/JSON')
def movieJSON(category_id):
    movie = session.query(Movie_Items).all()
    return jsonify(Movie_Items=[i.serialize for i in movie])

    #category = session.query(Category).filter_by(id=category_id).all()
    #movie = session.query(Movie_Items).filter_by(category_id=category_id).all()
    #return jsonify(Movie_Items=[i.serialize for i in movie])

#Function to shall all Categories
@app.route('/')
@app.route('/category')
def showCategory():
    categories = session.query(Category).order_by(asc(Category.name))
    return render_template('category.html', categories = categories)

#Function to create a new Category
@app.route('/category/new',  methods=['GET','POST'])
def newCategory():
    if request.method == 'POST':
        newCategory = Category(name=request.form['name'])
        session.add(newCategory)
        session.commit()
        flash('New Category %s Successfully Created' % (newCategory.name))
        return redirect(url_for('showCategory'))
    else:
        return render_template('newCategory.html')

#Function to edit a Category
@app.route('/category/<int:category_id>/edit', methods=['GET','POST'])
def editCategory(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if request.method == 'POST':

        if request.form['name']:
            category.name = request.form['name']
            session.commit()
            flash('%s Successfully Edited' % category.name)
            return redirect(url_for('showMovie', category_id=category.id))
    else:
        return render_template('editCategory.html', category=category.id)

#Function to delete a Category and all contents
@app.route('/category/<int:category_id>/delete', methods=['GET', 'POST'])
def deleteCategory(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    movies = session.query(Movie_Items).filter_by(category_id=category.id).all()
    if request.method == 'POST':
        session.delete(category)
        for movie in movies:
            session.delete(movie)
        flash('%s Category and All Items Associated with this Category Successfully Deleted' %category.name)
        session.commit()
        return redirect(url_for('showCategory'))
    else:
        return render_template('deleteCategory.html', category=category)

#Fuction to show all movies in a specific category
@app.route('/category/<int:category_id>')
@app.route('/category/<int:category_id>/movie')
def showMovie(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    movies = session.query(Movie_Items).filter_by(category_id=category.id)
    return render_template('movie.html', category = category, movies=movies)

#Fuction to create new movies in a specific function
@app.route('/category/<int:category_id>/movie/new', methods=['GET', 'POST'])
def newMovieItem(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if request.method == 'POST':
        newMovie = Movie_Items(
            name=request.form['name'],
            description=request.form['description'],
            category_id=category.id)
        session.add(newMovie)
        session.commit()
        flash('New Item -  %s  Successfully Created' % (newMovie.name))
        return redirect(url_for('showCategory'))
    else:
        return render_template('newMovieItem.html')

#Fuction to edit movies in a specific category
@app.route('/category/<int:category_id>/movie/<int:movie_id>/edit', methods=['GET', 'POST'])
def editMovieItem(category_id, movie_id):
    category = session.query(Category).filter_by(id=category_id).one()
    movie = session.query(Movie_Items).filter_by(id=movie_id).all()
    if request.method == 'POST':
        if request.form['name']:

            movie.name = request.form['name']
            movie.description = request.form['description']
            session.commit()
            flash('%s Successfully Edited' % movie.name)
            return redirect(url_for('showMovie', category_id=category.id))
    else:
        return render_template('editMovieItem.html', category=category, movie=movie)

#Function to delete movies in a specific category
@app.route('/category/<int:category_id>/movie/<int:movie_id>/delete', methods=['GET', 'POST'])
def deleteMovieItem(category_id, movie_id):
    category = session.query(Category).filter_by(id=category_id).one()
    movies = session.query(Movie_Items).filter_by(id=movie_id).one()
    if request.method == 'POST':
        session.delete(movies)
        session.commit()
        flash('%s Successfully Deleted' % movies.name)
        return redirect(url_for('showMovie', category_id=category.id))
    else:
        return render_template('deleteMovieItem.html', category=category, movies=movies)



if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host = '0.0.0.0', port = 8000)
