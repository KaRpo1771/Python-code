import telebot
from telebot import types
import requests
from bs4 import BeautifulSoup
from googletrans import Translator
import random
from datetime import datetime
import feedparser
import pytz
import re
import concurrent.futures

RAWG_API = "5af74b0f3b1e4deb95c7179dcf99f684"
STEAM_API = "B432E3448A2F985B77E6B40FB3F67667"

bot = telebot.TeleBot("8260250768:AAGcz1jRraAtvCCnTqmktKR1ntWtqiY3LKw")
translator = Translator()
user_data = {}
user_wishlist = {}
current_game_guess = {}


STEAM_GENRES = {
    "Action": 19,
    "Adventure": 21,
    "RPG": 122,
    "Shooter": 1770,
    "Strategy": 9,
    "Casual": 597,
    "Simulation": 599,
    "Puzzle": 1662,
    "Fighting": 173,
    "Sports": 701,
    "Racing": 599,
    "Indie": 492,
    "Educational": 397
}







@bot.message_handler(commands=["start"])
def start_message(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("help"),
           types.KeyboardButton("search"),
           types.KeyboardButton("news"),
           types.KeyboardButton("select"))

    bot.send_message(
        message.chat.id,
        "Привет! Я бот, который может присылать тебе новости и скидки по Steam\n"
        "Используй /help чтобы получить список команд",
        reply_markup=kb
    )








@bot.message_handler(commands=["help"])
def help_message(message):
    bot.send_message(
        message.chat.id,
        "Вот мои команды:\n\n"
        "/help - список команд\n"
        "/search - найти актуальные скидки\n"
        "/news - показать последние игровые новости\n"
        "/select - выбрать жанр игр для получения скидок\n"
        "/wishlist - список желаемых игр\n"
        "/addwishlist - добавить игру в список желаемых игр\n"
        "/removewishlist - удалить игру из списка желаемого\n"
    )





@bot.message_handler(commands=["select"])
def select_message(message):
    chat_id = message.chat.id
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for genre_name in STEAM_GENRES.keys():
        kb.add(types.KeyboardButton(genre_name))
    bot.send_message(chat_id, "Выберите жанр для поиска в специальной панели \n(Около строки ввода, справа)", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in STEAM_GENRES)
def handle_genre(message):
    chat_id = message.chat.id
    genre = message.text
    user_data[chat_id] = {"genre": genre}
    bot.send_message(chat_id, f"Жанр установлен: {genre} ✅\nТеперь используй /search")


def fetch_steam_description(appid):
    steam_api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=ru&l=russian"
    try:
        data = requests.get(steam_api_url, timeout=5).json()
        return data[str(appid)]["data"].get("short_description", "Описание отсутствует")
    except:
        return "Описание отсутствует"






@bot.message_handler(commands=["search"])
def search_message(message):
    chat_id = message.chat.id
    if chat_id not in user_data or "genre" not in user_data[chat_id]:
        bot.send_message(chat_id, "Сначала выбери жанр через /select")
        return

    genre = user_data[chat_id]["genre"]
    tag_id = STEAM_GENRES.get(genre)
    bot.send_message(chat_id, f"Ищу случайные скидки игр жанра {genre} на Steam...")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    search_url = f"https://store.steampowered.com/search/?tags={tag_id}&category1=998&specials=1&cc=ru&l=russian"
    resp = requests.get(search_url, headers=headers, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = soup.select(".search_result_row")

    if not results:
        bot.send_message(chat_id, f"Не найдено игр со скидкой в жанре {genre} ❌")
        return

    sample_rows = random.sample(results[:50], min(10, len(results)))
    games = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {}
        for row in sample_rows:
            name_tag = row.select_one(".title")
            if not name_tag:
                continue
            name = name_tag.text.strip()
            link = row.get("href")
            discount_tag = row.select_one(".discount_pct")
            discount = discount_tag.text.strip() if discount_tag else "0%"
            price_tag = row.select_one(".discount_final_price")
            old_price_tag = row.select_one(".discount_original_price")
            if price_tag and old_price_tag:
                price = price_tag.text.strip()
                old_price = old_price_tag.text.strip()
            else:
                price_tag = row.select_one(".search_price")
                price = price_tag.text.strip() if price_tag else "Неизвестно"
                old_price = ""

            appid_match = re.search(r"app/(\d+)", link)
            appid = appid_match.group(1) if appid_match else None

            if appid:
                futures[executor.submit(fetch_steam_description, appid)] = {
                    "name": name, "link": link, "discount": discount,
                    "price": price, "old_price": old_price
                }
            else:
                games.append(
                    f"🎮 {name}\n"
                    f"🔻 Скидка: {discount}\n"
                    f"💸 Цена: {price} (было {old_price})\n"
                    f"📝 Описание отсутствует\n"
                    f"🔗 {link}\n"
                )

        for fut in concurrent.futures.as_completed(futures):
            info = futures[fut]
            desc = fut.result()[:300] + ("..." if len(fut.result()) > 300 else "")
            games.append(
                f"🎮 {info['name']}\n"
                f"🔻 Скидка: {info['discount']}\n"
                f"💸 Цена: {info['price']} (было {info['old_price']})\n"
                f"📝 {desc}\n"
                f"🔗 {info['link']}\n"
            )

    bot.send_message(chat_id, "✅ Случайные игры со скидками:\n\n" + "\n".join(games))









@bot.message_handler(commands=["news"])
def news_message(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Поиск последних новостей Steam...")

    try:
        feed_url = "https://store.steampowered.com/feeds/news/?l=russian"
        feed = feedparser.parse(feed_url)
        local_tz = pytz.timezone("Asia/Almaty")

        if chat_id not in user_data:
            user_data[chat_id] = {"sent_links": set(), "genre": None}

        sent_links = user_data[chat_id].get("sent_links", set())
        news_messages = []
        count = 0

        for entry in feed.entries:
            if entry.link in sent_links:
                continue  

            published_utc = datetime(*entry.published_parsed[:6])
            published_local = published_utc.replace(tzinfo=pytz.utc).astimezone(local_tz)
            date_str = published_local.strftime("%d.%m.%Y %H:%M")

            translated_title = translator.translate(entry.title, dest='ru').text
            link = entry.link

            news_messages.append(f"📅 {date_str}\n📰 {translated_title}\n🔗 {link}")
            sent_links.add(entry.link)
            count += 1
            if count >= 10:
                break

        user_data[chat_id]["sent_links"] = sent_links
        if news_messages:
            bot.send_message(chat_id, "\n\n".join(news_messages))
        else:
            bot.send_message(chat_id, "Новых новостей пока что нет")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")









@bot.message_handler(commands=["addwishlist"])
def add_wishlist_command(message):
    chat_id = message.chat.id
    text = message.text.split(maxsplit=1)
    
    if len(text) < 2:
        bot.send_message(chat_id, "Используй команду так: \n /addwishlist <Название игры или AppID>")
        return
    
    input_text = text[1].strip()
    
   
    if input_text.isdigit():
        appid = input_text
        name = fetch_steam_description(appid)[:50]  
    else:
        name = input_text

        search_url = f"https://store.steampowered.com/api/storesearch/?term={name}&l=russian&cc=ru"
        try:
            data = requests.get(search_url).json()
            if data.get("items"):
                appid = str(data["items"][0]["id"])
                name = data["items"][0]["name"]
            else:
                bot.send_message(chat_id, f"Не удалось найти игру по названию '{name}'")
                return
        except:
            bot.send_message(chat_id, "Ошибка при поиске игры в Steam ❌")
            return
    
    if chat_id not in user_wishlist:
        user_wishlist[chat_id] = []
    
    if any(item['appid'] == appid for item in user_wishlist[chat_id]):
        bot.send_message(chat_id, f"{name} уже в списке желаемого ✅")
    else:
        user_wishlist[chat_id].append({"name": name, "appid": appid})
        bot.send_message(chat_id, f"{name} добавлена в список желаемого ✅")








@bot.message_handler(commands=["removewishlist"])
def remove_wishlist_command(message):
    chat_id = message.chat.id
    text = message.text.split(maxsplit=1)

    if chat_id not in user_wishlist or not user_wishlist[chat_id]:
        bot.send_message(chat_id, "Твой список желаемого пуст ❌")
        return

    if len(text) < 2:

        wishlist = "\n".join([f"{i+1}. {item['name']}" for i, item in enumerate(user_wishlist[chat_id])])
        bot.send_message(chat_id, f"Используй команду так: \n /removewishlist <номер или название>\nТвой список:\n{wishlist}")
        return

    input_text = text[1].strip()

 
    if input_text.isdigit():
        idx = int(input_text) - 1
        if 0 <= idx < len(user_wishlist[chat_id]):
            removed = user_wishlist[chat_id].pop(idx)
            bot.send_message(chat_id, f"{removed['name']} удалена из списка желаемого ✅")
        else:
            bot.send_message(chat_id, "Неверный номер игры ❌")
    else:

        removed_items = [item for item in user_wishlist[chat_id] if input_text.lower() in item['name'].lower()]
        if not removed_items:
            bot.send_message(chat_id, f"Не найдено игры с названием '{input_text}' в списке желаемого ❌")
        else:
            for item in removed_items:
                user_wishlist[chat_id].remove(item)
            bot.send_message(chat_id, f"{', '.join([i['name'] for i in removed_items])} удалены из списка желаемого ✅")









@bot.message_handler(commands=["wishlist"])
def check_wishlist(message):
    chat_id = message.chat.id
    if chat_id not in user_wishlist or not user_wishlist[chat_id]:
        bot.send_message(chat_id, "Список желаемого пустой \n/addwishlist")
        return
    
    for item in user_wishlist[chat_id]:
        appid = item["appid"]
        name = item["name"]
        desc = fetch_steam_description(appid)
        
        steam_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=ru&l=russian"
        data = requests.get(steam_url).json()
        price_info = data.get(appid, {}).get("data", {}).get("price_overview", {})
        
        if price_info.get("discount_percent", 0) > 0:
            discount = price_info["discount_percent"]
            final_price = price_info["final"] / 100
            old_price = price_info["initial"] / 100
            
            bot.send_message(chat_id,
                f"🎯 {name} сейчас со скидкой!\n"
                f"🔻 Скидка: {discount}%\n"
                f"💸 Цена: {final_price}₽ (было {old_price}₽)\n"
                f"📝 {desc[:300]}...\n"
                f"🔗 https://store.steampowered.com/app/{appid}"
            )
        else:
            bot.send_message(chat_id, f"{name} Пока без скидки (Подождем еще чуток...)")




def gameSearch_steam(input_text):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    if input_text.isdigit():
        appid = input_text
        steam_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=ru&l=russian"
        try:
            data = requests.get(steam_url, headers=headers).json()
            game_data = data.get(appid, {}).get("data", {})
        except:
            return None
    else:
        search_url = f"https://store.steampowered.com/api/storesearch/?term={input_text}&l=russian&cc=ru"
        try:
            data = requests.get(search_url, headers=headers).json()
            if not data.get("items"):
                return None
            game_data = data["items"][0]
            appid = str(game_data["id"])
            steam_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=ru&l=russian"
            data = requests.get(steam_url, headers=headers).json()
            game_data = data.get(appid, {}).get("data", {})
        except:
            return None

    name = game_data.get("name", "Неизвестно")
    desc = game_data.get("short_description", "Описание отсутствует")[:400] + "..."
    url = f"https://store.steampowered.com/app/{appid}"
    
    price_info = game_data.get("price_overview", {})
    if price_info:
        discount = price_info.get("discount_percent", 0)
        final_price = price_info.get("final", 0) / 100
        old_price = price_info.get("initial", 0) / 100
        price_text = f"💸 Цена: {final_price}₽ (было {old_price}₽)\n🔻 Скидка: {discount}%" if discount > 0 else f"💸 Цена: {final_price}₽ (Скидки нет)"
    else:
        price_text = "💸 Цена: Неизвестно"

    text = (
        f"🎮 *{name}*\n"
        f"{price_text}\n"
        f"📝 {desc}\n"
        f"🔗 {url}"
    )

    return text

@bot.message_handler(commands=["gamesearch"])
def cmd_game_search(message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        bot.send_message(chat_id, "Используй так:\n/gamesearch <Название игры или AppID>")
        return

    input_text = args[1].strip()
    bot.send_message(chat_id, f"🔍 Ищу игру {input_text} в Steam...")

    result = gameSearch_steam(input_text)
    if not result:
        bot.send_message(chat_id, "❌ Игра не найдена на Steam")
        return

    bot.send_message(chat_id, result, parse_mode="Markdown")






bot.polling(none_stop=True)
