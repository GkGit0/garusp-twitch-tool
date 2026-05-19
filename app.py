import streamlit as st
import requests
import pandas as pd
import os
from dotenv import load_dotenv
from notion_client import Client

# =========================
# 環境変数
# =========================

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# =========================
# Streamlit設定
# =========================

st.set_page_config(
    page_title="GaruSp - Influencer Scraper",
    layout="wide"
)

st.title("GaruSp - Influencer Scraper")

st.write("Twitch / YouTube URLを貼り付け（改行・空白・カンマOK）")

# =========================
# Notion接続
# =========================

notion = Client(auth=NOTION_TOKEN)

# =========================
# Twitchアクセストークン取得
# =========================

auth_url = "https://id.twitch.tv/oauth2/token"

auth_params = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "grant_type": "client_credentials"
}

auth_response = requests.post(auth_url, params=auth_params)

auth_data = auth_response.json()

if "access_token" not in auth_data:

    st.error("Twitch認証失敗")
    st.write(auth_data)
    st.stop()

access_token = auth_data["access_token"]

headers = {
    "Client-ID": CLIENT_ID,
    "Authorization": f"Bearer {access_token}"
}

# =========================
# Twitch解析
# =========================

def get_twitch_data(url):

    try:

        username = url.split("/")[-1].strip()

        # ユーザー取得
        user_res = requests.get(
            "https://api.twitch.tv/helix/users",
            headers=headers,
            params={"login": username},
            timeout=10
        ).json()

        if not user_res.get("data"):
            return None

        user = user_res["data"][0]

        user_id = user["id"]

        # フォロワー
        follow_res = requests.get(
            "https://api.twitch.tv/helix/channels/followers",
            headers=headers,
            params={"broadcaster_id": user_id},
            timeout=10
        ).json()

        followers = follow_res.get("total", 0)

        # 配信情報
        stream_res = requests.get(
            "https://api.twitch.tv/helix/streams",
            headers=headers,
            params={"user_login": username},
            timeout=10
        ).json()

        stream_data = stream_res.get("data", [])

        game_name = "Offline"

        if stream_data:
            game_name = stream_data[0]["game_name"]

        return {
            "Platform": "Twitch",
            "Channel Name": user["display_name"],
            "Followers": followers,
            "Game": game_name,
            "Face Cam": "",
            "Status": "未連絡",
            "URL": url
        }

    except Exception as e:

        print(e)
        return None

# =========================
# YouTube解析
# =========================

def get_youtube_data(url):

    try:

        # /channel/ のみ対応
        if "/channel/" not in url:
            return None

        channel_id = url.split("/channel/")[-1].split("/")[0]

        channel_res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "snippet,statistics",
                "id": channel_id,
                "key": YOUTUBE_API_KEY
            },
            timeout=10
        ).json()

        items = channel_res.get("items", [])

        if not items:
            return None

        data = items[0]

        return {
            "Platform": "YouTube",
            "Channel Name": data["snippet"]["title"],
            "Followers": int(data["statistics"].get("subscriberCount", 0)),
            "Game": "YouTube",
            "Face Cam": "",
            "Status": "未連絡",
            "URL": url
        }

    except Exception as e:

        print(e)
        return None

# =========================
# Notion追加
# =========================

def add_to_notion(data):

    try:

        notion.pages.create(
            parent={"database_id": DATABASE_ID},

            properties={

                "Channel Name": {
                    "title": [
                        {
                            "text": {
                                "content": data["Channel Name"]
                            }
                        }
                    ]
                },

                "Followers": {
                    "number": int(data["Followers"])
                },

                "Game": {
                    "rich_text": [
                        {
                            "text": {
                                "content": data["Game"]
                            }
                        }
                    ]
                },

                "URL": {
                    "url": data["URL"]
                },

                "Status": {
                    "select": {
                        "name": "未連絡"
                    }
                }
            }
        )

    except Exception as e:

        st.error(f"Notion追加失敗: {data['Channel Name']}")
        st.text(str(e))

# =========================
# UI
# =========================

urls_text = st.text_area(
    "URLs",
    height=250,
    placeholder="""
https://www.twitch.tv/xxx

https://www.youtube.com/channel/xxxxx
"""
)

# =========================
# 実行
# =========================

if st.button("一括解析"):

    urls = urls_text.replace(",", " ").split()

    # 重複削除
    urls = list(set(urls))

    if not urls:

        st.warning("URLを入力してください")
        st.stop()

    st.info(f"{len(urls)}件を解析します")

    results = []

    progress = st.progress(0)

    with st.spinner("解析中..."):

        for i, url in enumerate(urls):

            data = None

            # Twitch
            if "twitch.tv" in url:

                data = get_twitch_data(url)

            # YouTube
            elif "youtube.com" in url:

                data = get_youtube_data(url)

            if data:

                results.append(data)

                add_to_notion(data)

                st.success(f"追加: {data['Channel Name']}")

            else:

                st.warning(f"解析失敗: {url}")

            progress.progress((i + 1) / len(urls))

    # =========================
    # 結果表示
    # =========================

    if results:

        df = pd.DataFrame(results)

        st.subheader("結果")

        st.dataframe(
            df,
            use_container_width=True
        )

        csv = df.to_csv(index=False)

        st.download_button(
            "CSVダウンロード",
            csv,
            "influencers.csv",
            "text/csv"
        )

        st.success("完了")

    else:

        st.error("取得できませんでした")