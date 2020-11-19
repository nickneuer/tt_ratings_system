

def usatt_algorithm(rating, wins, player_2_rating, player_2_wins):
    # should use this: https://www.teamusa.org/usa-table-tennis/ratings/rating-system
    pass

# From BTTC methodology:
# 16 points to a 3-0 winner over an equally rated opponent. 
# If the players in a match do not have equal rating (the usual case), 
# these 16 points are modified, up or down, with 4% of the rating difference between the involved players. 
# This means, for example, that a player rated 400 points or more above his opponent 
# gains 0 point for a 3-0 victory (4% of 400 is 16). In addition, individual games won by the 
# loser in a match count for 2 points each, i.e. if the same player as in the example above beats his/her 
# opponent (rated 400 points or more below) with 3-2, he/she will in fact lose 4 points

# 1400 loses to 1600 
# 1400 --> 1400 - (16 - .04 * (1600 - 1400)) 
# 1600 --> 1600 + (16 - .04 * (1600 - 1400))

# 1600 loses to 1400
# 1400 --> 1400 + (16 + .04 * (1600 - 1400)) 
# 1600 --> 1600 - (16 + .04 * (1600 - 1400))

def bttc_algorithm(rating, wins, player_2_rating, player_2_wins):
    '''
    args:
        rating1 int
        player_1_wins int (number of wins for player 1)
        rating2 int
        player_2_wins int (number of wins for player 2)
    returns:
        rating adjustment (signed int)
    '''
    if wins == player_2_wins == 0:
        return 0
    
    rating_difference = abs(rating - player_2_rating)
    # which player won? 
    won_match = True
    if wins < player_2_wins:
        won_match = False
    # adjustments
    adjustment_factor = int(round(.04 * rating_difference, 0)) # 4% adjustment per BTTC
    # adjust scores
    if won_match:
        # this is expected result, adjust downward
        if rating > player_2_rating:
            adjustment = max(16 - adjustment_factor, 0)
        # this is an upset, adjust upward
        else: 
            adjustment = 16 + adjustment_factor

    else:
        # lost but this is expected
        if player_2_rating > rating:
            # if adjustment factor > 16 no change
            adjustment = -1 * max((16 - adjustment_factor), 0)
        # lost, and it's an upset
        else: 
            adjustment = -1 * (16 + adjustment_factor)

    return adjustment


if __name__ == '__main__':
    rating1 = 1000
    player_1_wins = 0
    rating2 = 957
    player_2_wins = 0
    a1 = bttc_algorithm(rating1, player_1_wins, rating2, player_2_wins)
    a2 = bttc_algorithm(rating2, player_2_wins, rating1, player_1_wins)
    print("New ratings:")
    print("Player 1: {}".format(rating1 + a1))
    print("player 2: {}".format(rating2 + a2))

