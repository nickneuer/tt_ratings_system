webapp here: https://tt-ratings.herokuapp.com/leagues/sams_garage.db
notes to self... should be able to: 

* decide groups based on players and ratings, taking into account promotion from winning the previous group
* input match outcomes, determining group winner and rating changes
* Display and provide analytics on match histories

need webapp with forms to 
* create new league (e.g. new league "Sam's Garage" which will create new db of players / matches etc.)
* input players (lookup existing / create)
* create groups
* edit groups (move players as needed)
* input match outcomes (e.g. Nick [3] Sam [1])

`app/`
-- Leagues
-- New League

`app/<league>`
-- new session
-- session history

`app/<league>/<session_create>/`
-- form for 

`app/<league>/analytics/`
-- where all of the player match history and graphing players is

