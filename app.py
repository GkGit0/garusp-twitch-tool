import streamlit as st
import requests
import pandas as pd
import os
import re
from dotenv import load_dotenv
from notion_client import Client

# =========================
# 環境変数
# =========================

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# =========================
# Notion接続
# =========================

notion = Client(auth=NOTION_TOKEN)

# =========================
# Twitchアクセストークン
# =========================

auth_url = "https://id.twitch.tv/oauth2/token"

auth_params = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "grant_type": "client_credentials"
}

auth_response = requests.post(auth_url, params=auth_params)
auth_data = auth_response.json()

# エラーハンドリング
if "access_token" not in auth_data:
    st.error("Twitch認証に失敗しました")

    st.write("レスポンス内容：")
    st.write(auth_data)

    st.stop()

access_token = auth_data["access_token"]

headers = {
    "Client-ID": CLIENT_ID,
    "Authorization": f"Bearer {access_token}"
}

# =========================
# YouTube情報取得
# =========================

def get_youtube_data(url):

    try:

        # @username形式
        if "@" in url:

            handle = url.split("@")[-1].split("/")[0]

            search_res = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": handle,
                    "type": "channel",
                    "maxResults": 1,
                    "key": YOUTUBE_API_KEY
                }
            ).json()

            items = search_res.get("items", [])

            if not items:
                return None

            channel_id = items[0]["snippet"]["channelId"]

        # /channel/形式
        elif "/channel/" in url:

            channel_id = url.split("/channel/")[-1].split("/")[0]

        else:
            return None

        # チャンネル情報取得
        channel_res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "snippet,statistics",
                "id": channel_id,
                "key": YOUTUBE_API_KEY
            }
        ).json()

        channel_items = channel_res.get("items", [])

        if not channel_items:
            return None

        data = channel_items[0]

        return {
            "Platform": "YouTube",
            "Channel Name": data["snippet"]["title"],
            "Followers": int(data["statistics"].get("subscriberCount", 0)),
            "Game": "YouTube",
            "Face Cam": "",
            "Status": "未連絡",
            "URL": url
        }

    except:
        return None

# =========================
# UI
# =========================

st.set_page_config(page_title="GaruSp", layout="wide")

st.title("高円寺のURLトラップハウス")

st.write("Twitch / YouTube URLを貼り付け（改行・空白・カンマOK）")

urls_text = st.text_area("URLs", height=250)

# =========================
# 解析処理
# =========================

if st.button("一括解析"):

    # URL整形
    urls = urls_text.replace(",", " ").split()

    # 重複削除
    urls = list(set(urls))

    if not urls:
        st.warning("URLが入力されていません")
        st.stop()

    st.info(f"{len(urls)}件を解析します")

    results = []

    progress = st.progress(0)

    for i, url in enumerate(urls):

        try:

            # =========================
            # YouTube判定
            # =========================

            if "youtube.com" in url or "youtu.be" in url:

                youtube_result = get_youtube_data(url)

                if youtube_result:

                    results.append(youtube_result)

                    notion.pages.create(
                        parent={"database_id": DATABASE_ID},
                        properties={

                            "Channel Name": {
                                "title": [
                                    {
                                        "text": {
                                            "content": youtube_result["Channel Name"]
                                        }
                                    }
                                ]
                            },

                            "Followers": {
                                "number": youtube_result["Followers"]
                            },

                            "Game": {
                                "rich_text": [
                                    {
                                        "text": {
                                            "content": "YouTube"
                                        }
                                    }
                                ]
                            },

                            "URL": {
                                "url": url
                            },

                            "Status": {
                                "select": {
                                    "name": "未連絡"
                                }
                            }
                        }
                    )

                    st.success(f"YouTube追加: {youtube_result['Channel Name']}")

                progress.progress((i + 1) / len(urls))

                continue

            # =========================
            # Twitch処理
            # =========================

            username = url.split("/")[-1].strip()

            # ユーザー情報
            user_res = requests.get(
                "https://api.twitch.tv/helix/users",
                headers=headers,
                params={"login": username}
            ).json()

            if not user_res.get("data"):
                st.warning(f"見つからない: {username}")
                continue

            user = user_res["data"][0]
            user_id = user["id"]

            # フォロワー
            follow_res = requests.get(
                "https://api.twitch.tv/helix/channels/followers",
                headers=headers,
                params={"broadcaster_id": user_id}
            ).json()

            followers = follow_res.get("total", 0)

            # 配信情報
            stream_res = requests.get(
                "https://api.twitch.tv/helix/streams",
                headers=headers,
                params={"user_login": username}
            ).json()

            stream_data = stream_res.get("data", [])

            game_name = "Offline"

            if stream_data:
                game_name = stream_data[0]["game_name"]

            # 保存用
            result = {
                "Platform": "Twitch",
                "Channel Name": user["display_name"],
                "Followers": followers,
                "Game": game_name,
                "Face Cam": "",
                "Status": "未連絡",
                "URL": url
            }

            results.append(result)

            # Notion追加
            notion.pages.create(
                parent={"database_id": DATABASE_ID},
                properties={

                    "Channel Name": {
                        "title": [
                            {
                                "text": {
                                    "content": user["display_name"]
                                }
                            }
                        ]
                    },

                    "Followers": {
                        "number": followers
                    },

                    "Game": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": game_name
                                }
                            }
                        ]
                    },

                    "URL": {
                        "url": url
                    },

                    "Status": {
                        "select": {
                            "name": "未連絡"
                        }
                    }
                }
            )

            st.success(f"Twitch追加: {user['display_name']}")

        except Exception as e:

            st.error(f"エラー: {url}")
            st.text(str(e))

        progress.progress((i + 1) / len(urls))

    # =========================
    # 表示
    # =========================

    if results:

        df = pd.DataFrame(results)

        st.subheader("結果")

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False)

        st.download_button(
            "CSVダウンロード",
            csv,
            "influencers.csv",
            "text/csv"
        )

        st.success("完了")