from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

SHIKI_API = "https://shikimori.one/api"
MEMORY_CACHE = {}

def get_cached(key, ttl=300):
    if key in MEMORY_CACHE:
        val, expire = MEMORY_CACHE[key]
        if time.time() < expire:
            return val
        del MEMORY_CACHE[key]
    return None

def set_cache(key, value, ttl=300):
    MEMORY_CACHE[key] = (value, time.time() + ttl)

def format_image_urls(raw_path):
    if not raw_path:
        return "", ""
    img_url = raw_path if raw_path.startswith('http') else f"https://shikimori.one{raw_path}"
    proxy_url = f"https://images.weserv.nl/?url={img_url.replace('https://', '')}&w=500&output=webp"
    return proxy_url, f"https://desu.shikimori.one{raw_path}"

@app.after_request
def add_cors_and_cache(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    if response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=1800'
    return response

@app.route('/api/anime/catalog', methods=['GET'])
def get_catalog():
    page = request.args.get('page', '1')
    limit = request.args.get('limit', '40')
    order = request.args.get('order', 'popularity')
    kind = request.args.get('kind', '')
    search = request.args.get('search', '')

    cache_key = f"cat_{page}_{limit}_{order}_{kind}_{search}"
    cached_data = get_cached(cache_key, ttl=300)
    if cached_data:
        return jsonify(cached_data)

    url = f"{SHIKI_API}/animes?page={page}&limit={limit}&order={order}"
    if kind: url += f"&kind={kind}"
    if search: url += f"&search={search}"

    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=6)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                shiki_id = item.get('id')
                shiki_img = item.get('image', {}).get('original') or item.get('image', {}).get('preview')
                poster, backup = format_image_urls(shiki_img)
                item['poster_url'] = poster
                item['backup_poster'] = backup
                item['backdrop_url'] = f"https://images.weserv.nl/?url=shikimori.one/system/animes/original/{shiki_id}.jpg&w=1280&output=webp"
            
            result = {'status': 'ok', 'data': data}
            set_cache(cache_key, result, ttl=300)
            return jsonify(result)
    except Exception:
        pass

    return jsonify({'status': 'ok', 'data': []})

@app.route('/api/anime/details', methods=['GET'])
def get_details():
    shiki_id = request.args.get('shiki_id')
    if not shiki_id:
        return jsonify({'status': 'error', 'message': 'shiki_id is required'}), 400
        
    cache_key = f"details_{shiki_id}"
    cached_data = get_cached(cache_key, ttl=1800)
    if cached_data:
        return jsonify(cached_data)

    try:
        res = requests.get(f"{SHIKI_API}/animes/{shiki_id}", headers={'User-Agent': 'Mozilla/5.0'}, timeout=6)
        if res.status_code == 200:
            data = res.json()
            shiki_img = data.get('image', {}).get('original')
            poster, backup = format_image_urls(shiki_img)
            data['poster_url'] = poster
            data['backup_poster'] = backup
            data['backdrop_url'] = f"https://images.weserv.nl/?url=shikimori.one/system/animes/original/{shiki_id}.jpg&w=1280&output=webp"
            
            result = {'status': 'ok', 'data': data}
            set_cache(cache_key, result, ttl=1800)
            return jsonify(result)
    except Exception:
        pass

    return jsonify({'status': 'ok', 'data': {'id': shiki_id, 'poster_url': '', 'backdrop_url': ''}})

@app.route('/api/stream', methods=['GET'])
def get_stream():
    shiki_id = request.args.get('shiki_id')
    episode = int(request.args.get('episode', 1))
    translation_id = request.args.get('translation_id', '')

    if not shiki_id:
        return jsonify({'status': 'error', 'message': 'shiki_id is required'}), 400

    cache_key = f"stream_{shiki_id}_{episode}_{translation_id}"
    cached_stream = get_cached(cache_key, ttl=600)
    if cached_stream:
        return jsonify(cached_stream)

    embed_url = f"https://kodik.info/find-player?shikimori_id={shiki_id}&episode={episode}&only_episode=true"
    if translation_id:
        embed_url += f"&translation_id={translation_id}"

    mirrors = [
        embed_url,
        embed_url.replace('kodik.info', 'kodik.biz'),
        embed_url.replace('kodik.info', 'anivod.com')
    ]

    translations = [
        {'id': '610', 'title': 'AniLibria.TV'},
        {'id': '643', 'title': 'Studio Band'},
        {'id': '639', 'title': 'SoftBox'},
        {'id': '10', 'title': 'Оригинал + Субтитры'}
    ]

    result = {
        'status': 'ok',
        'stream_url': '',
        'embed_url': embed_url,
        'mirrors': mirrors,
        'translations': translations,
        'active_translation_id': translation_id or '610',
        'type': 'iframe',
        'episode': episode
    }

    set_cache(cache_key, result, ttl=600)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
