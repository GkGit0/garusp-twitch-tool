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

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

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
# Streamlit UI
# =========================

st.set_page_config(page_title="GaruSp", layout="wide")

st.title("GaruSp - Influencer Scraper")

st.write("Twitch / YouTube URLを貼り付け（改行・空白・カンマOK）")

urls_text = st.text_area("URLs", height=250)

# =========================
# YouTube解析
# =========================

def get_youtube_data(url):

    try:

        # URL掃除
        url = url.strip()
        url = url.split("?")[0]

        # =========================
        # @username取得
        # =========================

        handle_match = re.search(r"youtube\.com/@([^/]+)", url)

        if handle_match:

            handle = handle_match.group(1)

            search_url = (
                "https://www.googleapis.com/youtube/v3/search"
            )

            search_params = {
                "part": "snippet",
                "q": handle,
                "type": "channel",
                "key": YOUTUBE_API_KEY,
                "maxResults": 1
            }

            search_res = requests.get(
                search_url,
                params=search_params
            ).json()

            if "error" in search_res:
                return {
                    "error": search_res["error"]["message"]
                }

            items = search_res.get("items", [])

            if not items:
                return {
                    "error": "チャンネルが見つかりません"
                }

            channel_id = items[0]["snippet"]["channelId"]

        else:

            # =========================
            # /channel/ID
            # =========================

            channel_match = re.search(
                r"youtube\.com/channel/([^/]+)",
                url
            )

            if not channel_match:
                return {
                    "error": "YouTube URL形式が不正"
                }

            channel_id = channel_match.group(1)

        # =========================
        # チャンネル詳細取得
        # =========================

        channel_url = (
            "https://www.googleapis.com/youtube/v3/channels"
        )

        channel_params = {
            "part": "snippet,statistics",
            "id": channel_id,
            "key": YOUTUBE_API_KEY
        }

        channel_res = requests.get(
            channel_url,
            params=channel_params
        ).json()

        if "error" in channel_res:
            return {
                "error": channel_res["error"]["message"]
            }

        items = channel_res.get("items", [])

        if not items:
            return {
                "error": "チャンネル取得失敗"
            }

        data = items[0]

        return {
            "Platform": "YouTube",
            "Channel Name": data["snippet"]["title"],
            "Followers": int(
                data["statistics"].get("subscriberCount", 0)
            ),
            "Game": "YouTube",
            "Face Cam": "",
            "Status": "未連絡",
            "URL": url
        }

    except Exception as e:

        return {
            "error": str(e)
        }

# =========================
# Twitch解析
# =========================

def get_twitch_data(url):

    try:

        # URL掃除
        url = url.strip()
        url = url.split("?")[0]

        username = url.split("/")[-1]

        # =========================
        # ユーザー情報
        # =========================

        user_res = requests.get(
            "https://api.twitch.tv/helix/users",
            headers=headers,
            params={"login": username}
        ).json()

        if not user_res.get("data"):
            return {
                "error": "Twitchユーザーが見つかりません"
            }

        user = user_res["data"][0]
        user_id = user["id"]

        # =========================
        # フォロワー
        # =========================

        follow_res = requests.get(
            "https://api.twitch.tv/helix/channels/followers",
            headers=headers,
            params={"broadcaster_id": user_id}
        ).json()

        followers = follow_res.get("total", 0)

        # =========================
        # 配信情報
        # =========================

        stream_res = requests.get(
            "https://api.twitch.tv/helix/streams",
            headers=headers,
            params={"user_login": username}
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

        return {
            "error": str(e)
        }

# =========================
# 実行
# =========================

if st.button("一括解析"):

    urls = urls_text.replace(",", " ").split()

    urls = list(set(urls))

    if not urls:

        st.warning("URLが入力されていません")

        st.stop()

    st.info(f"{len(urls)}件を解析します")

    results = []

    progress = st.progress(0)

    for i, url in enumerate(urls):

        try:

            # URL掃除
            url = url.strip()
            url = url.split("?")[0]

            # =========================
            # YouTube
            # =========================

            if "youtube.com" in url:

                youtube_result = get_youtube_data(url)

                if youtube_result and "error" not in youtube_result:

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
                                            "content": youtube_result["Game"]
                                        }
                                    }
                                ]
                            },

                            "URL": {
                                "url": youtube_result["URL"]
                            },

                            "Status": {
                                "select": {
                                    "name": "未連絡"
                                }
                            }
                        }
                    )

                    st.success(
                        f"YouTube追加: {youtube_result['Channel Name']}"
                    )

                else:

                    st.error(f"YouTube解析失敗: {url}")

                    if youtube_result and "error" in youtube_result:
                        st.text(youtube_result["error"])

            # =========================
            # Twitch
            # =========================

            elif "twitch.tv" in url:

                twitch_result = get_twitch_data(url)

                if twitch_result and "error" not in twitch_result:

                    results.append(twitch_result)

                    notion.pages.create(
                        parent={"database_id": DATABASE_ID},
                        properties={

                            "Channel Name": {
                                "title": [
                                    {
                                        "text": {
                                            "content": twitch_result["Channel Name"]
                                        }
                                    }
                                ]
                            },

                            "Followers": {
                                "number": twitch_result["Followers"]
                            },

                            "Game": {
                                "rich_text": [
                                    {
                                        "text": {
                                            "content": twitch_result["Game"]
                                        }
                                    }
                                ]
                            },

                            "URL": {
                                "url": twitch_result["URL"]
                            },

                            "Status": {
                                "select": {
                                    "name": "未連絡"
                                }
                            }
                        }
                    )

                    st.success(
                        f"Twitch追加: {twitch_result['Channel Name']}"
                    )

                else:

                    st.error(f"Twitch解析失敗: {url}")

                    if twitch_result and "error" in twitch_result:
                        st.text(twitch_result["error"])

            else:

                st.warning(f"未対応URL: {url}")

        except Exception as e:

            st.error(f"エラー: {url}")

            st.text(str(e))

        progress.progress((i + 1) / len(urls))

    # =========================
    # 結果表示
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