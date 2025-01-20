from __future__ import unicode_literals
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch
import yt_dlp as youtube_dl
import os
import config
import re
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
import requests
from io import BytesIO
from settings_manager import settings

auth_manager = SpotifyClientCredentials(
    client_id=config.SPOTIFY_CLIENT_ID,
    client_secret=config.SPOTIFY_CLIENT_SECRET
)
spotify = spotipy.Spotify(auth_manager=auth_manager)

def detect_platform(url):
    for platform, patterns in config.SUPPORTED_PLATFORMS.items():
        if any(pattern in url for pattern in patterns):
            return platform
    return None

def clean_filename(name):
    """Очищает название от специальных символов и BYPASS пометок"""
    # Удаляем BYPASS, bypass и подобные вариации
    name = re.sub(r'\s*\(?bypass\)?', '', name, flags=re.IGNORECASE)
    # Заменяем специальные символы на обычные
    name = name.translate(str.maketrans('𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ',
                                      'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    # Очищаем от лишних пробелов
    name = ' '.join(name.split())
    return name.strip()

def get_tracks_from_collection(url, collection_type):
    """Получает список треков из плейлиста или альбома"""
    tracks = []
    
    try:
        if collection_type == 'playlist':
            results = spotify.playlist_tracks(url)
            items = results['items']
            while results['next']:
                results = spotify.next(results)
                items.extend(results['items'])
            
            for item in items:
                try:
                    if not item or not item.get('track'):
                        print(f"Пропускаем трек: отсутствуют данные")
                        continue
                        
                    track = item['track']
                    if not track.get('name'):
                        print(f"Пропускаем трек: отсутствует название")
                        continue
                        
                    # Безопасное получение имён исполнителей
                    artists = []
                    if track.get('artists'):
                        for artist in track['artists']:
                            if artist.get('name'):
                                artists.append(artist['name'])
                    
                    artists_str = ", ".join(artists) if artists else "Unknown Artist"
                    
                    # Безопасное получение URL обложки
                    thumbnail_url = None
                    if track.get('album') and track['album'].get('images') and track['album']['images']:
                        thumbnail_url = track['album']['images'][0].get('url')
                    
                    search_query = f"{artists_str} - {track['name']}"
                    
                    tracks.append({
                        'name': track['name'],
                        'performers': artists_str,
                        'thumbnail_url': thumbnail_url,
                        'type': 'track',
                        'search_query': search_query
                    })
                except Exception as track_error:
                    print(f"Ошибка при обработке трека: {str(track_error)}")
                    continue
        
        elif collection_type == 'album':
            album = spotify.album(url)
            results = spotify.album_tracks(url)
            items = results['items']
            while results['next']:
                results = spotify.next(results)
                items.extend(results['items'])
            
            album_thumbnail = None
            if album.get('images') and album['images']:
                album_thumbnail = album['images'][0].get('url')
            
            for track in items:
                try:
                    if not track.get('name'):
                        print(f"Пропускаем трек: отсутствует название")
                        continue
                    
                    # Безопасное получение имён исполнителей
                    artists = []
                    if track.get('artists'):
                        for artist in track['artists']:
                            if artist.get('name'):
                                artists.append(artist['name'])
                    
                    artists_str = ", ".join(artists) if artists else "Unknown Artist"
                    search_query = f"{artists_str} - {track['name']}"
                    
                    tracks.append({
                        'name': track['name'],
                        'performers': artists_str,
                        'thumbnail_url': album_thumbnail,
                        'type': 'track',
                        'search_query': search_query
                    })
                except Exception as track_error:
                    print(f"Ошибка при обработке трека: {str(track_error)}")
                    continue
        
        if not tracks:
            raise Exception("Не удалось получить треки из коллекции")
            
        return tracks
        
    except Exception as e:
        raise Exception(f"Ошибка при получении треков: {str(e)}")

def get_track_info(url, platform):
    if platform == 'spotify':
        try:
            # Определяем тип контента по URL
            if 'playlist' in url:
                return {'type': 'playlist', 'tracks': get_tracks_from_collection(url, 'playlist')}
            elif 'album' in url:
                return {'type': 'album', 'tracks': get_tracks_from_collection(url, 'album')}
            elif 'episode' in url:
                result = spotify.episode(url)
                performers = result['show']['publisher']
                track_name = clean_filename(result['name'])
                content_type = 'episode'
            else:
                result = spotify.track(url)
                performers = ", ".join(artist["name"] for artist in result["artists"])
                track_name = result['name']
                content_type = 'track'
            
            if content_type in ['track', 'episode']:
                search_query = f"{performers} - {track_name}"
                thumbnail_url = (result['album']['images'][0]['url'] if content_type == 'track' and result['album'].get('images') and result['album']['images']
                            else result['images'][0]['url'] if result.get('images') and result['images']
                            else None)
                
                return {
                    'type': content_type,
                    'name': track_name,
                    'performers': performers,
                    'search_query': search_query,
                    'thumbnail_url': thumbnail_url
                }
        except Exception as e:
            raise Exception(f"Ошибка при получении информации: {str(e)}")
    
    return {'type': platform, 'url': url}

def change_download_settings():
    while True:
        print("\nНастройки загрузки:")
        print(f"1. Спрашивать источник: {'Да' if settings.get('ask_source') else 'Нет'}")
        print(f"2. Предпочтительный источник: {settings.get('preferred_source')}")
        print("3. Вернуться в главное меню")
        
        choice = input("Ваш выбор: ")
        
        if choice == "1":
            settings.set('ask_source', not settings.get('ask_source'))
            print("Настройка обновлена и сохранена!")
        
        elif choice == "2":
            print("\nДоступные источники:")
            sources = ['youtube', 'soundcloud']
            for i, source in enumerate(sources, 1):
                print(f"{i}. {source}")
            
            try:
                source_choice = int(input("Выберите источник (номер): "))
                if 1 <= source_choice <= len(sources):
                    settings.set('preferred_source', sources[source_choice-1])
                    print("Настройка обновлена и сохранена!")
                else:
                    print("Неверный выбор")
            except ValueError:
                print("Введите корректный номер")
        
        elif choice == "3":
            break
        
        else:
            print("Неверный выбор")

def select_download_source(platform, track_info):
    if not settings.get('ask_source'):
        return settings.get('preferred_source')
    
    if platform == 'spotify':
        print("\nВыберите источник для загрузки:")
        sources = ['youtube', 'soundcloud']
        for i, source in enumerate(sources, 1):
            print(f"{i}. {source}")
        
        while True:
            try:
                choice = int(input("Ваш выбор: "))
                if 1 <= choice <= len(sources):
                    return sources[choice-1]
                print("Неверный выбор")
            except ValueError:
                print("Введите корректный номер")
    
    return platform

def add_metadata(file_path, track_info, thumbnail_url=None):
    try:
        # Создаем или загружаем ID3 теги
        audio = MP3(file_path, ID3=ID3)
        
        # Если тегов нет, создаем их
        if audio.tags is None:
            audio.add_tags()
        
        # Добавляем основные метаданные
        audio.tags.add(TIT2(encoding=3, text=track_info['name']))  # название
        audio.tags.add(TPE1(encoding=3, text=track_info['performers']))  # исполнитель
        
        # Если есть URL обложки, добавляем её
        if thumbnail_url:
            response = requests.get(thumbnail_url)
            if response.status_code == 200:
                audio.tags.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,  # 3 означает обложку
                    desc='Cover',
                    data=response.content
                ))
        
        audio.save()
        print("Метаданные успешно добавлены!")
    except Exception as e:
        print(f"Ошибка при добавлении метаданных: {str(e)}")

def download_collection(tracks, collection_type):
    """Загружает все треки из плейлиста или альбома"""
    total = len(tracks)
    success = 0
    failed = 0
    
    print(f"\nНачинаем загрузку {collection_type}а ({total} треков)")
    
    # Спрашиваем источник один раз для всей коллекции
    source = select_download_source('spotify', None) if settings.get('ask_source') else settings.get('preferred_source')
    
    for i, track in enumerate(tracks, 1):
        try:
            print(f"\nЗагрузка трека {i}/{total}")
            search_query = f"{track['performers']} - {track['name']}"
            track_info = {
                'name': track['name'],
                'performers': track['performers'],
                'search_query': search_query,
                'thumbnail_url': track.get('thumbnail_url'),
                'type': 'track'
            }
            # Добавляем третий аргумент source
            download_track(track_info, 'spotify', source)
            success += 1
        except Exception as e:
            print(f"Ошибка при загрузке трека {track['name']}: {str(e)}")
            failed += 1
    
    print(f"\nЗагрузка завершена!")
    print(f"Успешно: {success}")
    print(f"С ошибками: {failed}")

def download_track(track_info, platform, preset_source=None):
    try:
        if track_info['type'] in ['playlist', 'album']:
            download_collection(track_info['tracks'], track_info['type'])
            return
        
        # Используем предустановленный источник, если он есть
        source = preset_source or select_download_source(platform, track_info)
        
        if platform == 'spotify':
            video_url = search_track(track_info['search_query'])
            name = f"{track_info['performers']} - {track_info['name']}"
            thumbnail_url = track_info.get('thumbnail_url')
        else:
            video_url = track_info['url']
            name = "%(title)s"
            thumbnail_url = None

        print(f"Загрузка: {name if platform == 'spotify' else video_url}")
        
        base_path = f'{config.DOWNLOAD_DIR}/{name}'
        temp_path = f'{base_path}.{config.AUDIO_FORMAT}'
        final_path = f'{base_path}.{config.AUDIO_FORMAT}.{config.AUDIO_FORMAT}'
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': config.AUDIO_FORMAT,
                'preferredquality': config.AUDIO_QUALITY,
            }],
            'outtmpl': temp_path
        }
        
        download(video_url, ydl_opts)
        
        if os.path.exists(final_path):
            os.rename(final_path, temp_path)
        
        add_metadata(temp_path, track_info, thumbnail_url)
        
        print("Загрузка завершена успешно!")
    except Exception as e:
        print(f"Произошла ошибка при загрузке: {str(e)}")
        raise

def search_track(query):
    """Поиск трека на YouTube"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch1'  # Ищем только 1 видео
        }
        
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch:{query}", download=False)
            if result and result.get('entries'):
                return result['entries'][0]['url']
        return None
    except Exception as e:
        raise Exception(f"Ошибка при поиске видео: {str(e)}")

def parse_choice(choice, search_results):
    try:
        # Разбираем ввод на платформу и номер
        if choice.startswith('sp'):
            platform_code = 'sp'
            number = int(choice[2:])
        elif choice.startswith('so'):
            platform_code = 'so'
            number = int(choice[2:])
        elif choice.startswith('y'):
            platform_code = 'y'
            number = int(choice[1:])
        elif choice.startswith('d'):
            platform_code = 'd'
            number = int(choice[1:])
        else:
            return None, None
        
        # Сопоставляем коды с платформами
        platform_map = {
            'sp': 'spotify',
            'so': 'soundcloud',
            'y': 'youtube',
            'd': 'deezer'
        }
        
        platform = platform_map.get(platform_code)
        if not platform:
            return None, None
        
        # Проверяем валидность номера
        if number < 1 or number > len(search_results.get(platform, [])):
            return None, None
        
        return platform, number - 1
    except:
        return None, None

def search_and_show_tracks():
    query = input("Введите поисковый запрос: ")
    print("\nПоиск...")
    
    search_results = {}
    
    # Поиск в YouTube
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch5'  # Ищем 5 видео
        }
        
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            results = ydl.extract_info(f"ytsearch:{query}", download=False)
            if results and results.get('entries'):
                search_results['youtube'] = results['entries']
                print("\nYouTube (y1-y5):")
                for i, video in enumerate(results['entries'], 1):
                    print(f"y{i}. {video['title']}")
    except Exception as e:
        print(f"Ошибка при поиске в YouTube: {str(e)}")
    
    # Поиск в Spotify
    try:
        spotify_results = spotify.search(q=query, limit=5, type='track')
        tracks = spotify_results['tracks']['items']
        search_results['spotify'] = tracks
        print("\nSpotify (sp1-sp5):")
        for i, track in enumerate(tracks, 1):
            artists = ", ".join([artist['name'] for artist in track['artists']])
            print(f"sp{i}. {artists} - {track['name']}")
    except Exception as e:
        print(f"Ошибка при поиске в Spotify: {str(e)}")
    
    print("\nВведите код трека для загрузки (например: sp3, y2)")
    print("или 'q' для возврата в меню")
    
    while True:
        choice = input("Ваш выбор: ").lower()
        
        if choice == 'q':
            return
        
        platform, index = parse_choice(choice, search_results)
        
        if platform is None:
            print("Неверный формат. Примеры: sp3, y2")
            continue
        
        try:
            if platform == 'spotify':
                track = search_results['spotify'][index]
                track_info = {
                    'name': track['name'],
                    'performers': ", ".join([artist['name'] for artist in track['artists']]),
                    'search_query': f"{', '.join([artist['name'] for artist in track['artists']])} - {track['name']}",
                    'type': 'track',
                    'thumbnail_url': track['album']['images'][0]['url'] if track['album']['images'] else None
                }
            elif platform == 'youtube':
                track_info = {
                    'url': search_results['youtube'][index]['url'],
                    'type': platform
                }
            
            download_track(track_info, platform, None)
            break
        except Exception as e:
            print(f"Ошибка при обработке трека: {str(e)}")
            continue

def download(video_url, ydl_opts):
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception as e:
        raise Exception(f"Ошибка при загрузке: {str(e)}")

def main():
    try:
        os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
        
        while True:
            print("\nВыберите действие:")
            print("1. Скачать по ссылке")
            print("2. Поиск и скачивание")
            print("3. Настройки загрузки")
            print("4. Выход")
            
            choice = input("Ваш выбор: ")
            
            if choice == "1":
                url = input("Введите ссылку (трек/альбом/плейлист): ")
                platform = detect_platform(url)
                
                if platform:
                    track_info = get_track_info(url, platform)
                    if track_info['type'] in ['playlist', 'album']:
                        download_collection(track_info['tracks'], track_info['type'])
                    else:
                        download_track(track_info, platform, None)
                else:
                    print("Неподдерживаемая платформа или неверная ссылка")
            
            elif choice == "2":
                search_and_show_tracks()
            
            elif choice == "3":
                change_download_settings()
            
            elif choice == "4":
                break
            
            else:
                print("Неверный выбор")
                
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    main()