import json
from k_means_constrained import KMeansConstrained
import numpy as np
import itertools


class Player(): 
    def __init__(self, player_id, name, rating, won_group_number=None):
        self.player_id = player_id
        self.name = name
        self.rating = rating
        self.won_group_number = won_group_number

    @property
    def adjusted_rating(self):
        if self.won_group_number:
            return self.rating + 200
        return self.rating

    @staticmethod
    def from_player_row(p):
        player = Player(p['player_id'], p['name'], p['rating'])
        return player


def flip_indicies(n):
    return int(1/4 * (-1 + (-1) ** n - 2 * (-1) ** n * n))

def interleave_list(li):
    return [li[flip_indicies(i + 1)] for i in range(len(li))]


class Group():
    def __init__(self, group_number, players):
        self.group_number = group_number
        self.players = players

    @property
    def size(self):
        return len(self.players)

    def add_player(self, player):
        self.players.append(player)

    def get_highest_rated_player(self):
        return sorted(self.players, key=lambda p: p.rating)[-1]

    def get_lowest_rated_player(self):
        return sorted(self.players, key=lambda p: -p.rating)[-1]

    def remove_player(self, player_id):
        self.players = list(filter(lambda p: p.player_id != player_id, self.players))

    def make_matches(self):
        matches = list(itertools.combinations(self.players, 2))
        return interleave_list(matches)

    def __str__(self):
        player_list = [p.__dict__ for p in self.players]
        g = {
            "Group": self.group_number,
            "Players": player_list
        }
        return json.dumps(g, indent=4)


class Match():
    def __init__(self, player1, player2, p1_wins, p2_wins):
        self.player1 = player1
        self.player2 = player2
        self.p1_wins = p1_wins
        self.p2_wins = p2_wins

    @staticmethod
    def from_match_row(match_row):
        p1 = Player(
            match_row['player_1_id'], 
            match_row['player_1_name'], 
            match_row['player_1_rating']
        )
        p2 = Player(
            match_row['player_2_id'], 
            match_row['player_2_name'], 
            match_row['player_2_rating']
        )
        match = Match(
            p1, 
            p2, 
            match_row['player_1_wins'], 
            match_row['player_2_wins']
        )
        return match

class GroupResult():
    def __init__(self, group_number, matches, players=[]):
        self.group_number = group_number
        self.matches = matches
        self.players = players

    @staticmethod
    def from_match_rows(group_num, match_rows):
        # DB response
        # p1.player_id player_1_id,
        # p1.name player_1_name,
        # p1.rating player_1_rating,
        # m.player_1_wins,
        # p2.player_id player_2_id,
        # p2.name player_2_name,
        # p2.rating player_2_rating,
        # m.player_2_wins
        matches = []
        for m in match_rows:
            match = Match.from_match_row(m)
            matches.append(match)

        return GroupResult(group_num, matches)


def make_groups(players, num_groups, min_per_group=None, max_per_group=None):
    # sort ratings high to low
    sorted_players = sorted(players, key=lambda p: -p.rating)
    num_players = len(sorted_players)

    ratings = np.array([[float(p.rating)] for p in sorted_players])
    clf = KMeansConstrained(
        n_clusters=num_groups,
        size_min=min_per_group or 0,
        size_max=max_per_group or len(players),
        random_state=0
    )
    clf.fit(ratings)
    # build up groups based on cluster labels
    groups = []
    last_cluster_index = None
    group_number = 1
    group = Group(1, [])
    for player, cluster_index in zip(sorted_players, clf.labels_):
        if last_cluster_index is None:
            last_cluster_index = cluster_index
        if cluster_index != last_cluster_index:
            groups.append(group)
            group_number += 1
            group = Group(group_number, [])
            group.add_player(player)
            last_cluster_index = cluster_index
        else:
            group.add_player(player)
    groups.append(group)

    return groups

if __name__ == '__main__':
    # fake player data
    import random
    players = []
    rating = 2400
    num_players = 42
    for n in range(num_players):
        proposed_rating = rating - random.choice(range(200))
        if proposed_rating < 400:
            rating = rating - 5
        else:
            rating = proposed_rating
        players.append(
            Player(
                player_id=n + 1,
                name="Player {}".format(n + 1),
                rating=rating
            )
        )
    players[7].won_group_number = True
    groups = make_groups(
        players, 
        min_per_group=5,
        max_per_group=7
    )
    for group in groups:
        print(group)


