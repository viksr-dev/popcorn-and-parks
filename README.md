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
- **Where shall we go?** Pick what you feel like (animals, beach, walks and waterfalls, hot pools, thrills, learning, island trips, markets, art, free), how far you'll go (nearby, up to an hour, or a day trip of up to 2½ hours such as Hamilton Zoo or Hobbiton), where you're starting from (or your location) and the weather. About 45 real places around Auckland, Waikato and Northland show with drive-time estimates, cost, directions and an Add to our ideas button.
- Ideas in three categories: parks and outdoors, paid activities for kids, and things to do together
- Cost, location and notes on each idea, plus votes from each family member
- Plan an idea for a specific day, then mark it done and rate it

**Discover**
- **Tonight**: "What do you feel like?" Tap moods (Feel-good, Make us laugh, Edge of your seat, Cosy, Mind-bending, Big adventure, Spooky) and genres, choose how long you've got, and choose who it's for: Anyone, Kids (G & PG) or Grown-ups (M and above, using the NZ rating where known, otherwise US PG-13 or higher). Pick who's watching and films they voted for, or that suit the genres they like, move up the list. Below that, "Because you liked…" suggests related films for your recent 4 and 5 star ratings. Suggestions show as a poster wall. "Show me different ones" swaps in a fresh batch, ✕ hides a film you're not keen on, and "Surprise us" reveals one of the best matches full-screen. Data comes from TMDB via `python3 tools/fetch_details.py`, which writes the `MOVIE_DATA` block in `index.html`; re-run it after adding titles to `tools/extra-titles.json`.
- Top 10 movies in New Zealand on Netflix, Prime Video, Disney+, HBO Max and Apple TV, read from a `charts/streaming` document in the shared database so the lists can be refreshed without changing the page
- **Where to watch**: every suggestion shows where it streams in New Zealand, or where to rent or buy it (JustWatch data via TMDB). The Surprise reveal lists every option with a link to the full list. A "Streaming on" filter keeps Tonight to the services you have. Streaming deals change, so refresh with `python3 tools/fetch_details.py --where`.
- **Marathon**: pick a film series (Star Wars, Indiana Jones, Harry Potter, Bond and about 50 more) to see its total running time, then plan it: choose a start date and time, spread it over 1 to 5 days, set break lengths and untick films to skip. You get a day-by-day schedule with start and finish times, the highest age rating, where each film streams, and an "Add all to the pile" button. The series list is `tools/marathons.json`; `python3 tools/fetch_marathons.py` downloads them and their posters.
- A list of movies from IMDb's Top 250 released from 1990 onwards, filterable by decade and by family-friendly rating (G or PG)
- Every DC animated feature film to date (about 100), filterable by line: DC Universe Animated Originals, cinema releases, kids and LEGO films, and others, with a watched count
- One tap adds any of them to the movie pile

**About this movie**: on claude.ai, an About button on any movie asks Claude for a spoiler-free synopsis, the NZ and US age ratings, an approximate IMDb score and a note on suitability for kids. Answers are saved in the shared database (`info` collection) so each movie is looked up once.

**Movie posters**: tiles show real poster art when the page has a downloaded image for the title in `posters/` (the page's content security policy blocks remote images, so posters are published with the page). Titles without one keep the coloured tile. To add posters, run `python3 tools/fetch_posters.py`; it reads the page's built-in lists plus `tools/extra-titles.json`, finds each film on TMDB with the TMDB API (set `TMDB_API_KEY` to a free TMDB API key, or add the token as a network secret for api.themoviedb.org in a Claude cloud environment), downloads the poster from image.tmdb.org and updates the `POSTERS` map in `index.html`. Re-running only fetches new titles; `--title "Name" --year 2024` adds one. Poster images come from [TMDB](https://www.themoviedb.org/).

**Which service this month?**: a card above the pile ranks streaming services by how many unwatched films in your pile they have (films with more votes count for more), so you know which subscription to switch on.

**Movie night mode**: a 🍿 button on the Next movie night ticket opens a full-screen countdown with the poster, start time, finish time, where to watch and a get-ready checklist.

**Kids' picks**: in Discover > Tonight, kids pick their name and swipe (or tap 👍/👎) through G and PG films; a yes puts the film in the pile with their vote.

**Streaming changes**: after each `fetch_details.py --where` refresh, the Which service card says when a film in your pile has arrived on or left a service.

**Family stats** at the top of History: films and hours this year, average rating, best picker, favourite genres, top-rated film, outings and DC progress. "Because you liked…" follows who's watching, using films they voted for.

**History** of every movie watched and activity done, with ratings.

Starter buttons fill an empty planner with a few family movies and general activity ideas you can delete.

## Running it

Open `index.html` in a browser. Data is saved in that browser's local storage.

When the page is published as a Claude artifact with the `db` capability, it saves to the artifact's shared database instead, so everyone who opens the link sees the same plans.
