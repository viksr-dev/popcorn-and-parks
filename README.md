# Popcorn & Parks

A family planner for movie nights and weekend activities. It is a single HTML file with no build step and no dependencies.

## Features

**Movie nights**
- Family members take turns picking the movie, in an order you can rearrange, with a "skip this turn" option
- A shared pile of movie suggestions with year, runtime, genre and who suggested it
- Everyone can vote on each movie; sort by votes, newest or shortest
- "Pick one at random" spins the pile, weighted towards movies with more votes
- Book a movie for a date, then mark it watched and give it a star rating, which passes the pick to the next person

**Weekend activities**
- Ideas in three categories: parks and outdoors, paid activities for kids, and things to do together
- Cost, location and notes on each idea, plus votes from each family member
- Plan an idea for a specific day, then mark it done and rate it

**Discover**
- **Tonight**: "What do you feel like?" Tap moods (Feel-good, Make us laugh, Edge of your seat, Cosy, Mind-bending, Big adventure, Spooky) and genres, choose how long you've got, and tick "Kids are watching" to keep to G and PG. Pick who's watching and films they voted for, or that suit the genres they like, move up the list. Below that, "Because you liked…" suggests related films for your recent 4 and 5 star ratings. "Surprise us" picks one of the best matches. Data comes from TMDB via `python3 tools/fetch_details.py`, which writes the `MOVIE_DATA` block in `index.html`; re-run it after adding titles to `tools/extra-titles.json`.
- Top 10 movies in New Zealand on Netflix, Prime Video, Disney+, HBO Max and Apple TV, read from a `charts/streaming` document in the shared database so the lists can be refreshed without changing the page
- A list of movies from IMDb's Top 250 released from 1990 onwards, filterable by decade and by family-friendly rating (G or PG)
- Every DC animated feature film to date (about 100), filterable by line: DC Universe Animated Originals, cinema releases, kids and LEGO films, and others, with a watched count
- One tap adds any of them to the movie pile

**About this movie**: on claude.ai, an About button on any movie asks Claude for a spoiler-free synopsis, the NZ and US age ratings, an approximate IMDb score and a note on suitability for kids. Answers are saved in the shared database (`info` collection) so each movie is looked up once.

**Movie posters**: tiles show real poster art when the page has a downloaded image for the title in `posters/` (the page's content security policy blocks remote images, so posters are published with the page). Titles without one keep the coloured tile. To add posters, run `python3 tools/fetch_posters.py`; it reads the page's built-in lists plus `tools/extra-titles.json`, finds each film on TMDB with the TMDB API (set `TMDB_API_KEY` to a free TMDB API key, or add the token as a network secret for api.themoviedb.org in a Claude cloud environment), downloads the poster from image.tmdb.org and updates the `POSTERS` map in `index.html`. Re-running only fetches new titles; `--title "Name" --year 2024` adds one. Poster images come from [TMDB](https://www.themoviedb.org/).

**History** of every movie watched and activity done, with ratings.

Starter buttons fill an empty planner with a few family movies and general activity ideas you can delete.

## Running it

Open `index.html` in a browser. Data is saved in that browser's local storage.

When the page is published as a Claude artifact with the `db` capability, it saves to the artifact's shared database instead, so everyone who opens the link sees the same plans.
