"""
User Features Service: Manages Watchlist and CineBook Community Reviews
Persists cleanly without violating the normalized 11-table MySQL database schema.
"""

import os
import json
from datetime import datetime
from flask import session

REVIEWS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'user_reviews.json')

INITIAL_REVIEWS = [
    {
        "review_id": 1,
        "movie_id": 1,
        "movie_name": "Leo",
        "user_name": "Karthik V.",
        "rating": 9,
        "review_text": "Anirudh's background score and Vijay's cafe fight sequence were absolutely sensational! Watched at CineBook Screen 1 with Dolby Atmos.",
        "created_at": "2026-10-15 19:30"
    },
    {
        "review_id": 2,
        "movie_id": 2,
        "movie_name": "Jawan",
        "user_name": "Rohit Malhotra",
        "rating": 8,
        "review_text": "Mass action spectacle at its best. SRK's dual role and the metro heist scene kept the audience cheering throughout.",
        "created_at": "2026-10-16 21:15"
    },
    {
        "review_id": 3,
        "movie_id": 3,
        "movie_name": "RRR",
        "user_name": "Sita Ram",
        "rating": 10,
        "review_text": "Masterpiece of Indian cinema. The interval block and climax battle sequence redefined high-voltage action filmmaking.",
        "created_at": "2026-10-17 18:00"
    },
    {
        "review_id": 4,
        "movie_id": 4,
        "movie_name": "Interstellar",
        "user_name": "Arun Kumar",
        "rating": 10,
        "review_text": "Hans Zimmer's organ score vibrating in the cinema auditorium gives me goosebumps every single time. A timeless sci-fi classic.",
        "created_at": "2026-10-18 14:20"
    },
    {
        "review_id": 5,
        "movie_id": 5,
        "movie_name": "Kantara",
        "user_name": "Divya Menon",
        "rating": 9,
        "review_text": "The final 20 minutes of Bhoota Kola performance left everyone speechless. Incredible sound design and direction by Rishab.",
        "created_at": "2026-10-18 16:45"
    }
]

def _ensure_reviews_file():
    if not os.path.exists(REVIEWS_FILE):
        os.makedirs(os.path.dirname(REVIEWS_FILE), exist_ok=True)
        with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
            json.dump(INITIAL_REVIEWS, f, indent=2)

def get_all_reviews():
    _ensure_reviews_file()
    try:
        with open(REVIEWS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return INITIAL_REVIEWS

def get_movie_reviews(movie_id):
    reviews = get_all_reviews()
    matched = [r for r in reviews if r.get('movie_id') == movie_id]
    
    if matched:
        avg_rating = round(sum(r['rating'] for r in matched) / len(matched), 1)
    else:
        avg_rating = None

    return {
        "reviews": list(reversed(matched)),
        "count": len(matched),
        "average_rating": avg_rating
    }

def add_movie_review(movie_id, movie_name, user_name, rating, review_text):
    reviews = get_all_reviews()
    new_id = (max([r['review_id'] for r in reviews]) + 1) if reviews else 1
    
    entry = {
        "review_id": new_id,
        "movie_id": int(movie_id),
        "movie_name": movie_name,
        "user_name": user_name.strip() or "Anonymous Cinema Fan",
        "rating": int(rating),
        "review_text": review_text.strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    reviews.append(entry)
    with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, indent=2)

    return entry

# --------------------------------------------------------------------------
# Session-Persisted Watchlist Management
# --------------------------------------------------------------------------
def get_watchlist():
    return session.get('watchlist', [])

def toggle_watchlist_item(movie_id):
    movie_id = int(movie_id)
    watchlist = session.get('watchlist', [])
    if movie_id in watchlist:
        watchlist.remove(movie_id)
        added = False
    else:
        watchlist.append(movie_id)
        added = True
    session['watchlist'] = watchlist
    session.modified = True
    return added, len(watchlist)

def is_in_watchlist(movie_id):
    return int(movie_id) in session.get('watchlist', [])
