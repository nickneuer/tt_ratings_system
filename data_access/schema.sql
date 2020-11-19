
drop table if exists player;
create table player (
    player_id integer PRIMARY KEY, -- will autoincrement
    name varchar(500) NOT NULL,
    dominant_hand varchar(1), -- l or r
    racket_type varchar(10), -- penhold, shakehand
    rating integer
);

-- new session for every match played by the same two players
drop table if exists session;
create table session (
    session_id integer PRIMARY KEY,
    session_date varchar(12) -- '03/11/20' (extra room for test matches 03/11/20-1st)
);

-- will have to be symmetric (2 entries for each match)
-- just let this get row_id assigned
drop table if exists match;
create table match (
    player_1_id integer,
    player_1_wins integer,
    player_2_id integer,
    player_2_wins integer,
    group_number integer,
    session_id integer,
    ordinal integer,
    FOREIGN KEY(player_1_id) REFERENCES player(player_id),
    FOREIGN KEY(player_2_id) REFERENCES player(player_id),
    FOREIGN KEY(session_id) REFERENCES session(session_id)
);

drop table if exists rating;
create table rating (
    player_id integer,
    session_id integer,
    previous_rating integer,
    rating integer,
    won_group integer DEFAULT 0,
    FOREIGN KEY(player_id) REFERENCES player(player_id),
    FOREIGN KEY(session_id) REFERENCES session(session_id),
    CONSTRAINT player_per_session UNIQUE(player_id,session_id)
);

drop table if exists session_to_player;
create table session_to_player (
    session_id integer,
    player_id integer,
    group_number integer DEFAULT 0,
    FOREIGN KEY(player_id) REFERENCES player(player_id),
    FOREIGN KEY(session_id) REFERENCES session(session_id)
);

