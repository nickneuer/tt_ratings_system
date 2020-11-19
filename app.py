
from flask import (
    g, flash, Response, 
    Flask, render_template,
    request, url_for, jsonify, redirect
)
import json
import os
from data_access.data_access import DataAccess
from ratings.groupings import Group, GroupResult, Player, Match, make_groups
from ratings.ratings import bttc_algorithm
from wtforms import (
    Form, BooleanField, StringField, 
    PasswordField, IntegerField, validators, FieldList, FormField)
import time

app = Flask(__name__)
app.secret_key = 'some secret key'

DATABASE_DIR = '/Users/nickneuer/code/rating_system/data/'
SCHEMA_PATH = '/Users/nickneuer/code/rating_system/data_access/schema.sql'

def get_db(db_name):
    db = getattr(g, '_database', None)
    db_path = os.path.join(DATABASE_DIR, db_name)
    if db is None:
        db = DataAccess(db_path)
        db.connect()
        g._database = db
    # check if we are switching leagues
    elif db.db_path != db_path:
        # close the old conn and switch
        db.close()
        db = DataAccess(db_path)
        db.connect()
        g._database = db
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

class LeagueForm(Form):
    league_name = StringField('League Name', [validators.Length(min=4, max=25)])

class PlayerForm(Form):
    player_name = StringField('Player Name', [validators.required()])
    rating = IntegerField('Rating', [validators.NumberRange(min=100, max=3000)])

class SessionForm(Form):
    session_date = StringField('Session Date', [validators.Length(min=4, max=25)])

class GroupForm(Form):
    max_group_size = IntegerField('Max Group Size', [])
    min_group_size = IntegerField('Min Group Size', [])
    num_groups = IntegerField('Number of Groups', [])

class MatchForm(Form):
    p1_wins = IntegerField('', [])
    p2_wins = IntegerField('', [])

@app.route('/new_league', methods=['GET', 'POST'])
def create_league():
    form = LeagueForm(request.form)
    if request.method == 'POST' and form.validate():
        league_name = form.league_name.data
        db_name = league_name.lower().strip().replace(' ', '_') + '.db'
        db = get_db(db_name)
        db.init_db(SCHEMA_PATH)
        return redirect(url_for('choose_league'))
    return render_template('new_league.html', form=form)

@app.route('/leagues', methods=['GET', 'POST'])
def choose_league():
    leagues = os.listdir(DATABASE_DIR)
    if request.method == 'POST':
        league = request.form.get('league')
        db = get_db(league)
        return redirect(url_for('league_view', league=league))
    return render_template('leagues.html', leagues=leagues)

@app.route('/leagues/<league>')
def league_view(league):
    db = get_db(league)
    ### look at existing sessions /leages/<league>/<session_id>/
    ### create a new session /leagues/<league>/new_session -> /leagues/<league>/<session_id>/check-in/
    ### from /leagues/<league>/<session_id>/check-in/ you should be able to add or select players
    ### then submit, which should create the groups, allow you to edit them (move players around)  
    return jsonify(
        {
            'league': db.db_path,
            'players': db.get_players()
        }
    )

@app.route('/leagues/<league>/player', methods=['GET', 'POST'])
def create_player(league):
    db = get_db(league)
    form = PlayerForm(request.form)
    if request.method == 'POST' and form.validate():
        player_name = form.player_name.data
        rating = form.rating.data
        player_id = db.add_player(player_name=player_name, rating=rating)
        return redirect(url_for('league_view', league=league))
    return render_template('new_player.html', form=form)

@app.route('/leagues/<league>/session', methods=['GET', 'POST'])
def add_session(league):
    db = get_db(league)
    form = SessionForm(request.form)
    if request.method == 'POST' and form.validate():
        session_date = form.session_date.data
        session_id = db.add_session(session_date)
        return redirect(url_for('add_players_to_session', league=league, session_id=session_id))
    return render_template('new_session.html', form=form)


@app.route('/leagues/<league>/session/<session_id>', methods=['GET', 'POST'])
def add_players_to_session(league, session_id):
    db = get_db(league)
    #form = SessionForm(request.form)
    players = db.get_players()
    selected_players = db.get_players_by_session_id(session_id)
    if request.method == 'POST':
        player_id = int(request.form.get('player'))
        db.add_session_to_player(session_id, player_id)
        return redirect(
            url_for('add_players_to_session', league=league, session_id=session_id))
    return render_template(
        'session_player_select.html', 
        players=players, 
        selected_players=selected_players,
        league=league,
        session_id=session_id
    )

@app.route('/leagues/<league>/session/<session_id>/groups', methods=['GET', 'POST'])
def edit_groups(league, session_id):
    db = get_db(league)
    form = GroupForm(request.form)
    players = db.get_players_by_session_id(session_id)
    groups = []
    if request.method == 'POST':
        min_group_size = form.min_group_size.data
        max_group_size = form.max_group_size.data
        num_groups = form.num_groups.data
        player_list = [Player.from_player_row(p) for p in players]
        groups = make_groups(
            player_list, 
            min_per_group=min_group_size,
            max_per_group=max_group_size,
            num_groups=num_groups
        )
        for group in groups:
            for player in group.players:
                db.update_player_group(session_id, player.player_id, group.group_number)
        return render_template('group_edit.html', form=form, groups=groups)
    return render_template('group_edit.html', form=form, groups=groups)

@app.route('/leagues/<league>/session/<session_id>/results', methods=['GET', 'POST'])
def save_results(league, session_id):
    # eventually will render things like ranking-pre ranking-post
    # group winners etc.
    db = get_db(league)
    match_records = db.get_match_results(session_id)
    summaries = []
    #if request.method == 'POST':
    for m in match_records:
        # player1
        # player2
        # p1_wins
        # p2_wins
        match = Match.from_match_row(m)
        # calculate rating change and update player's ratings for the session
        # a1 = bttc_algorithm(rating1, player_1_wins, rating2, player_2_wins)
        # TODO: need to do this across ALL matches for each player
        r1 = match.player1.rating
        r2 = match.player2.rating
        w1 = match.p1_wins
        w2 = match.p2_wins
        p1_adjustment = bttc_algorithm(r1, w1, r2, w2)
        p2_adjustment = bttc_algorithm(r2, w2, r1, w1)
        r1_new = r1 + p1_adjustment
        r2_new = r2 + p2_adjustment
        # add the new ratings for each player
        db.add_rating(
            player_id=match.player1.player_id, 
            session_id=session_id, 
            previous_rating=r1, 
            rating=r1_new
        )
        db.add_rating(
            player_id=match.player2.player_id, 
            session_id=session_id, 
            previous_rating=r2, 
            rating=r2_new
        )
        # should update player's rating too (on player record)
        summary = '{0} -- old rating: {1}, new rating: {2}'.format(
            match.player1.name,
            r1,
            r1_new
        )
        summary = '{0} -- old rating: {1}, new rating: {2}'.format(
            match.player2.name,
            r2,
            r2_new
        )
        summaries.append(summary)
    return jsonify(summaries)

    

@app.route('/leagues/<league>/session/<session_id>/groups/input', methods=['GET', 'POST'])
def match_edit(league, session_id):
    db = get_db(league)
    players = db.get_players_by_session_id(session_id)
    groups = []
    group = Group(1, [])
    # arrange them into groups
    for player in players:
        p = Player.from_player_row(player)
        if player['group_number'] != group.group_number:
            groups.append(group)
            group = Group(player['group_number'], [])
            group.add_player(p)
        else:
            group.add_player(p)
    groups.append(group)
    # initialize any missing matches
    group_results = []
    for g in groups:
        for p1, p2 in g.make_matches():
            if not db.get_match(session_id, p1.player_id, p2.player_id):
                db.add_match(p1.player_id, p2.player_id, g.group_number, session_id)

        match_rows = db.get_matches_by_group(session_id, g.group_number)
        group_result = GroupResult.from_match_rows(g.group_number, match_rows)
        group_result.players = g.players
        group_results.append(group_result)

    return render_template('groups.html', group_results=group_results, session_id=session_id, league=league)

@app.route('/leagues/<league>/session/<session_id>/groups/input/<player_id1>/<player_id2>', methods=['GET', 'POST'])
def save_match_score(league, session_id, player_id1, player_id2):
    form = MatchForm(request.form)
    db = get_db(league)
    player1 = Player.from_player_row(db.get_player(player_id1))
    player2 = Player.from_player_row(db.get_player(player_id2))
    if request.method == 'POST' and form.validate():
        p1_wins = form.p1_wins.data
        p2_wins = form.p2_wins.data
        db.update_match(player_id1, player_id2, session_id, p1_wins=p1_wins, p2_wins=p2_wins)
        return redirect(url_for('match_edit', league=league, session_id=session_id))
    return render_template('match.html', form=form, player1=player1, player2=player2)

@app.route('/', methods=['GET', 'POST'])
def index():
    # should let you choose league
    # create new league
    return redirect(url_for('choose_league'))


if __name__ == '__main__':
    app.run()
