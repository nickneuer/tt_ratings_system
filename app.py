
from flask import (
    g, flash, Response, 
    Flask, render_template,
    request, url_for, jsonify, redirect
)
import json
import io
import os
from data_access.data_access import DataAccess
from ratings.groupings import Group, GroupResult, Player, Match, make_groups
from ratings.ratings import bttc_algorithm
from wtforms import (
    Form, BooleanField, StringField, 
    PasswordField, IntegerField, validators, FieldList, FormField)
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.pylab import plt
from matplotlib.ticker import (
    MultipleLocator
)
import time

app = Flask(__name__)
app.secret_key = 'some secret key'

app_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(app_dir, 'data')
SCHEMA_PATH = os.path.join(app_dir, 'data_access/schema.sql')

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

@app.route('/leagues/<league>', methods=['GET', 'POST'])
def league_view(league):
    db = get_db(league)
    players = db.get_players()
    sessions = db.get_sessions()
    print('got sessions: {}'.format(sessions))
    if request.method == 'POST':
        player_id = int(request.form.get('player'))
        return redirect(url_for('player_view', league=league, player_id=player_id))
    return render_template('league_home.html', players=players, league=league, sessions=sessions)

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
        # return render_template('group_edit.html', form=form, groups=groups)
    return render_template(
        'group_edit.html', form=form, groups=groups, league=league, session_id=session_id)

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

@app.route('/leagues/<league>/session/<session_id>/results', methods=['GET', 'POST'])
def session_results(league, session_id):
    # eventually will render things like ranking-pre ranking-post
    # group winners etc.
    db = get_db(league)
    # for some of this should only do on POST
    match_records = db.get_match_results(session_id)
    session_date = db.get_session_date(session_id)
    # calculate the total rating change per player
    # TODO: should probably encapsulate this logic somewhere else
    # what if rules like "bonus points" need to be added?
    player_ratings = {}
    for m in match_records:
        # player1
        # player2
        # p1_wins
        # p2_wins
        match = Match.from_match_row(m)
        # calculate rating change and update player's ratings for the session
        # a1 = bttc_algorithm(rating1, player_1_wins, rating2, player_2_wins)
        ratings1 = db.get_player_rating_by_session(session_id, match.player1.player_id)
        if ratings1 is not None:
            r1 = ratings1['previous_rating']
        else:
            r1 = match.player1.rating

        ratings2 = db.get_player_rating_by_session(session_id, match.player2.player_id)
        if ratings2 is not None:
            r2 = ratings2['previous_rating']
        else:
            r2 = match.player2.rating
        # initialize these with the starting rating for this session
        if match.player1.player_id not in player_ratings:
            player_ratings[match.player1.player_id] = r1
        if match.player2.player_id not in player_ratings:
            player_ratings[match.player2.player_id] = r2

        w1 = match.p1_wins
        w2 = match.p2_wins
        p1_adjustment = bttc_algorithm(r1, w1, r2, w2)
        p2_adjustment = bttc_algorithm(r2, w2, r1, w1)
        # add the adjustment to the ongoing rating tally for this player
        player_ratings[match.player1.player_id] += p1_adjustment
        player_ratings[match.player2.player_id] += p2_adjustment
        # add the new ratings for each player
    rating_change = {}
    for player_id, new_rating in player_ratings.items():
        p = db.get_player(player_id)
        player = Player.from_player_row(p)

        rating_pair = db.get_player_rating_by_session(session_id, player_id)
        if rating_pair is not None:
            previous_rating = rating_pair['previous_rating']
        else:
            previous_rating = player.rating
        # make a lookup of previous and new rating for session
        rating_change[player_id] = {}
        rating_change[player_id]['previous_rating'] = previous_rating
        rating_change[player_id]['new_rating'] = new_rating

        if request.method == 'POST':
            db.add_rating(
                player_id=player_id, 
                session_id=session_id, 
                previous_rating=previous_rating, 
                rating=new_rating
            )
            db.update_player_rating(player_id=player_id, rating=new_rating)

    group_results = []
    num_groups = db.get_group_count(session_id)
    for n in range(num_groups):
        group_number = n + 1
        match_rows = db.get_matches_by_group(session_id, group_number)
        group_result = GroupResult.from_match_rows(group_number, match_rows)
        player_rows = db.get_players_by_group(session_id, group_number)
        players = [Player.from_player_row(p) for p in player_rows]
        for p in players:
            p.new_rating = rating_change[p.player_id]['new_rating']
            p.previous_rating = rating_change[p.player_id]['previous_rating']
        group_result.players = players
        group_results.append(group_result)

    return render_template(
        'session_results.html', 
        group_results=group_results, 
        league=league, 
        session_date=session_date)

@app.route('/leagues/<league>/player/<player_id>', methods=['GET'])
def player_view(league, player_id):
    db = get_db(league)
    player = db.get_player(player_id)
    return render_template('player.html', league=league, player=player)

#### GRAPHING PLAYER RATING OVER TIME

def plot_player_history(name, sessions, ratings):
    fig = plt.figure(figsize=(20,5))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(sessions, ratings, label=name)
    ax.legend(loc='upper left')
    ax.xaxis.set_major_locator(MultipleLocator(12))
    return fig

@app.route('/leagues/<league>/player/<player_id>/rating-history', methods=['GET', 'POST'])
def graph_ratings(league, player_id):
    db = get_db(league)
    player = db.get_player(player_id)
    ratings_by_session = db.get_ratings_history(player_id)
    ratings = [r['rating'] for r in ratings_by_session]
    sessions = [r['session_date'] for r in ratings_by_session]
    fig = plot_player_history(player['name'], sessions, ratings)
    output = io.BytesIO()
    FigureCanvas(fig).print_png(output)
    return Response(output.getvalue(), mimetype='image/png')

#### MATCH SUMMARIES BY PLAYER

@app.route('/leagues/<league>/player/<player_id>/match-stats', methods=['GET', 'POST'])
def match_history(league, player_id=None, num_weeks=None):
    db = get_db(league)
    if player_id is None:
        player_id = request.form.get('player')

    num_weeks = request.args.get('num_weeks')
    if num_weeks is not None:
        num_weeks = int(num_weeks)

    player = db.get_player(player_id)
    sessions = db.get_ratings_history(player_id)
    start_session_id = None
    num_sessions = len(sessions)
    if num_weeks is not None and num_sessions > num_weeks:
        start_idx = num_sessions - num_weeks
        start_session_id = sessions[start_idx]['session_id']

    match_rows = db.get_matches_by_player(player_id, start_session_id=start_session_id)
    # repurposing GroupResult for a collection of matches
    matches = GroupResult.from_match_rows(0, match_rows).matches
    match_stats = {}
    for match in matches:
        player_2_id = match.player2.player_id
        if match.p2_wins > match.p1_wins:
            p1_won = 0
            p2_won = 1
        elif match.p1_wins > match.p2_wins:
            p1_won = 1
            p2_won = 0
        else:
            p1_won = 0
            p2_won = 0

        if player_2_id not in match_stats:
            match_stats[player_2_id] = {
                'opponent': match.player2,
                'match_wins': p1_won,
                'match_losses': p2_won,
                'match_win_pct': 0,
                'total_game_wins': match.p1_wins,
                'total_game_losses': match.p2_wins,
                'game_win_pct': 0,
                'total_matches': 1,
                'total_games': match.p1_wins + match.p2_wins
            }
        else:
            match_stats[player_2_id]['match_wins'] += p1_won
            match_stats[player_2_id]['match_losses'] += p2_won
            match_stats[player_2_id]['total_game_wins'] += match.p1_wins
            match_stats[player_2_id]['total_game_losses'] += match.p2_wins
            match_stats[player_2_id]['total_games'] += (match.p1_wins + match.p2_wins)
            match_stats[player_2_id]['total_matches'] += 1
    # go back and calculate percentages
    for player_2_id, stats in match_stats.items():
        stats['match_win_pct'] = round(float(stats['match_wins']) / stats['total_matches'] * 100, 1)
        stats['game_win_pct'] = round(float(stats['total_game_wins']) / stats['total_games'] * 100, 1)

    return render_template('match_history.html', match_stats=match_stats, player=player, league=league)

#################################################################

@app.route('/', methods=['GET', 'POST'])
def index():
    # should let you choose league
    # create new league
    return redirect(url_for('choose_league'))


if __name__ == '__main__':
    app.run()
