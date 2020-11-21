
import sqlite3 

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class DataAccess():
    def __init__(self, db_path):
        self.db_path = db_path
        self.connected = False
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = dict_factory
        self.cursor = self.conn.cursor()

    def close(self):
        self.cursor.close()
        self.conn.close()

    def init_db(self, schema_sql_file):
        with open(schema_sql_file) as f:
            self.cursor.executescript(f.read())
        self.conn.commit()

    def add_player(self, player_name, rating, dominant_hand=None, racket_type=None):
        sql = """
        insert into player (
            name,
            dominant_hand,
            racket_type,
            rating
        )
        values (?, ?, ?, ?)
        """
        self.cursor.execute(sql, (player_name, dominant_hand, racket_type, rating))
        self.conn.commit()
        return self.cursor.lastrowid

    def add_match(self, p1_id, p2_id, group_number, session_id, p1_wins=None, p2_wins=None):
        sql = """
        insert into match (
            player_1_id,
            player_1_wins,
            player_2_id,
            player_2_wins,
            group_number,
            session_id,
            ordinal
        )
        values (?, ?, ?, ?, ?, ?, ?)
        """
        self.cursor.execute(sql, (p1_id, p1_wins, p2_id, p2_wins, group_number, session_id, 1))
        # symmetric table so need to insert opposite side as well (keep track of this with "ordinal")
        self.cursor.execute(sql, (p2_id, p2_wins, p1_id, p1_wins, group_number, session_id, 2))
        self.conn.commit()

    def update_match(self, p1_id, p2_id, session_id, p1_wins=None, p2_wins=None):
        sql = """
        update match
            set player_1_wins = ?,
                player_2_wins = ?
        where player_1_id = ?
        and player_2_id = ?
        and session_id = ?
        """
        self.cursor.execute(sql, (p1_wins, p2_wins, p1_id, p2_id, session_id))
        # symmetric table so need to insert opposite side as well (keep track of this with "ordinal")
        self.cursor.execute(sql, (p2_wins, p1_wins, p2_id, p1_id, session_id))
        self.conn.commit()

    def get_matches_by_group(self, session_id, group_number):
        sql = """
        select
            p1.player_id player_1_id,
            p1.name player_1_name,
            p1.rating player_1_rating,
            m.player_1_wins,
            p2.player_id player_2_id,
            p2.name player_2_name,
            p2.rating player_2_rating,
            m.player_2_wins
        from match m
        join player p1
            on p1.player_id = m.player_1_id
        join player p2
            on p2.player_id = m.player_2_id
        where m.session_id = ?
        and m.group_number = ?
        and m.ordinal = 1
        """
        self.cursor.execute(sql, (session_id, group_number))
        return self.cursor.fetchall()

    def get_group_count(self, session_id):
        sql = """
        select 
            count(distinct group_number) c
        from session_to_player 
        where session_id = ?
        """
        self.cursor.execute(sql, (session_id,))
        return self.cursor.fetchone()['c']

    def get_match_results(self, session_id):
        sql = """
        select
            p1.player_id player_1_id,
            p1.name player_1_name,
            p1.rating player_1_rating,
            m.player_1_wins,
            p2.player_id player_2_id,
            p2.name player_2_name,
            p2.rating player_2_rating,
            m.player_2_wins
        from match m
        join player p1
            on p1.player_id = m.player_1_id
        join player p2
            on p2.player_id = m.player_2_id
        where m.session_id = ?
        and m.ordinal = 1
        """
        self.cursor.execute(sql, (session_id,))
        return self.cursor.fetchall()

    def get_match(self, session_id, p1_id, p2_id):
        sql = """
        select 
            player_1_wins,
            player_2_wins,
            group_number
        from match
        where player_1_id = ?
        and player_2_id = ?
        and session_id = ?
        """
        self.cursor.execute(sql, (p1_id, p2_id, session_id))
        return self.cursor.fetchone()

    def add_session(self, session_date):
        sql = """
        insert into session (session_date)
        values (?)
        """
        self.cursor.execute(sql, (session_date,))
        self.conn.commit()
        return self.cursor.lastrowid

    def add_rating(self, player_id, session_id, previous_rating, rating, won_group=0):
        check_sql = """
        select 1 
        from rating
        where player_id = ?
        and session_id = ?
        """
        self.cursor.execute(check_sql, (player_id, session_id))
        if self.cursor.fetchone():
            return 

        sql = """
        insert into rating (
            player_id,
            session_id,
            previous_rating,
            rating,
            won_group
        )
        values (?, ?, ?, ?, ?)
        """
        self.cursor.execute(sql, (player_id, session_id, previous_rating, rating, won_group))
        self.conn.commit()

    def get_player(self, player_id):
        sql = """
        select 
            player_id,
            name,
            rating
        from player
        where player_id = ?
        """
        self.cursor.execute(sql, (player_id,))
        return self.cursor.fetchone()

    def update_player_rating(self, player_id, rating):
        sql = """
        update player
            set rating = ?
        where player_id = ?
        """
        self.cursor.execute(sql, (rating, player_id))
        self.conn.commit()

    def get_player_rating_by_session(self, session_id, player_id):
        sql = """
        select 
            previous_rating,
            rating
        from rating
        where session_id = ?
        and player_id = ?
        """
        self.cursor.execute(sql, (session_id, player_id))
        return self.cursor.fetchone()

    def get_players(self):
        sql = """
        select 
            player_id,
            name,
            rating
        from player
        order by name asc
        """
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def get_sessions(self):
        sql = """
        select 
            session_id,
            session_date
        from session
        order by session_id asc
        """
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def add_session_to_player(self, session_id, player_id):
        sql = """
        insert into session_to_player (
            session_id,
            player_id
        )
        values (?, ?)
        """
        self.cursor.execute(sql, (session_id, player_id))
        self.conn.commit()

    def update_player_group(self, session_id, player_id, group_number):
        sql = """
        update session_to_player
        set group_number = ?
        where session_id = ? 
        and player_id = ?
        """
        self.cursor.execute(sql, (group_number, session_id, player_id))
        self.conn.commit()

    def get_players_by_session_id(self, session_id):
        sql = """
        select 
            p.player_id,
            p.name,
            p.rating,
            stp.group_number
        from session_to_player stp 
        join player p
            on stp.player_id = p.player_id
        where stp.session_id = ?
        order by stp.group_number asc, p.rating desc
        """
        self.cursor.execute(sql, (session_id,))
        return self.cursor.fetchall()

    def get_ratings_history(self, player_id):
        sql = """
        select 
            s.session_date,
            r.rating
        from rating r
        join session s
            on r.session_id = s.session_id
        where r.player_id = ?
        order by s.session_id
        """
        self.cursor.execute(sql, (player_id,))
        return self.cursor.fetchall()

    def get_players_by_group(self, session_id, group_number):
        sql = """
        select 
            p.player_id,
            p.name,
            p.rating
        from session_to_player stp 
        join player p
            on stp.player_id = p.player_id
        where stp.session_id = ?
        and stp.group_number = ?
        order by p.rating desc
        """
        self.cursor.execute(sql, (session_id, group_number))
        return self.cursor.fetchall()


if __name__ == '__main__':
    da = DataAccess('test_db_file.db')
    da.connect()
    da.init_db('schema.sql')
    pid = da.add_player('Nick', 1500, 'r', 'shakehand')
    print('added player id: {}'.format(pid))
    da.close()
