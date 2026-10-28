#!/bin/bash
#
# Teams 通知，由 run_etl.sh 共用。
#
# 這台主機沒有 MTA，cron 的 MAILTO 無法投遞，因此改以 webhook 通知。
#
# Webhook URL 視同密碼（任何人取得即可對該頻道發文），不納入版控，
# 與 DB 連線參數一樣放在專案根目錄的 .env：
#
#     TEAMS_WEBHOOK_URL = "https://..."
#
# .env 的位置由這支腳本所在的目錄往上推一層，不依賴執行時的工作目錄：
# cron 執行時的工作目錄是家目錄，不是專案目錄。
TEAMS_ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.env"

# 送不出去的通知暫存在這裡，由 flush_pending 重送。
#
# 放 ~/.local/state 而不是 /tmp，主機重開後仍然存在。
PENDING_DIR="${HOME}/.local/state/citrix/pending"

# 從 .env 讀出 TEAMS_WEBHOOK_URL，沒有設定時輸出空字串。
#
# 解析規則比照 python-dotenv，與容器裡的 Python 讀同一份檔案時解讀一致：
# 接受 KEY=value、KEY = "value"、KEY='value'、export KEY=value，
# 去掉等號兩側的空白與成對的引號。同名出現多次時以最後一行為準。
#
# 不用 source 載入：.env 採 KEY = "value" 寫法，等號兩側有空白，
# 在 shell 裡會被當成「執行 KEY 這個指令」而不是賦值。
read_webhook_url() {
    [ -r "$TEAMS_ENV_FILE" ] || return 0

    sed -nE 's/^[[:space:]]*(export[[:space:]]+)?TEAMS_WEBHOOK_URL[[:space:]]*=[[:space:]]*//p' \
        "$TEAMS_ENV_FILE" \
        | tail -n 1 \
        | tr -d '\r' \
        | sed -E 's/[[:space:]]+$//; s/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/'
}

# notify_teams <OK|FAIL|INFO> <標題> <本文> <除錯資訊> [<結尾狀態> <結尾文字>]
#
#   OK    綠色 ✅，從失敗回到正常
#   INFO  藍色 📊，中性，給不代表成敗的訊息用（週報）
#   FAIL  紅色 🚨，需要有人看
#
# 本文用白話寫「發生什麼事」，以行首的標記排版：
#
#   ## 小標       粗體小標
#   名稱｜內容    連續幾行組成一個鍵值清單，左右兩欄自動對齊（以第一個全形｜分隔）
#   ```           前後兩行之間的內容用等寬字型顯示，給要複製執行的指令用
#   空行          段落分隔
#   其他          一般文字
#
# 除錯資訊是主機、log 路徑、最後幾行輸出這類給人追查用的內容，
# 預設收合，按卡片底部的按鈕才展開。排版標記與本文相同。
# 傳空字串就不出現按鈕。
#
# 結尾狀態與結尾文字是選用的，會另外成為一個上了色的區塊接在本文後面。
# 給週報用：標題維持中性的藍色，「目前狀態」那一句自己標綠（OK）或標紅（FAIL）。
#
# 回傳值：送出成功回傳 0，送不出去回傳 1，由呼叫端決定要不要暫存重送。
# webhook 未設定、缺少 python3 時只印一行並回傳 0：重送也不會成功。
# 不論哪一種，都不改變 ETL 的離開碼。
#
# payload 交由 python3 的 json.dumps 產生，而非在 shell 內自行拼接字串。
# 通知內文含有換行、引號與中文，手動跳脫極易出錯且難以驗證。
#
# 採用 json.dumps 的預設 ensure_ascii=True，中文會輸出成 \uXXXX 逸出序列。
# cron 的環境通常未設定 LANG，落在 C locale 下輸出非 ASCII 可能產生亂碼
# 或例外。純 ASCII 的 payload 不受 locale 影響，Teams 端解析後仍會正確
# 顯示中文。
notify_teams() {
    local status="$1" title="$2" body="$3" details="${4:-}"
    local footer_status="${5:-}" footer="${6:-}"
    local url color prefix footer_color payload

    url="$(read_webhook_url)"
    if [ -z "$url" ]; then
        echo "（.env 未設定 TEAMS_WEBHOOK_URL，略過通知：${TEAMS_ENV_FILE}）"
        return 0
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        echo "（缺少 python3，略過 Teams 通知）"
        return 0
    fi

    # 狀態同時以顏色與標題前的 emoji 表示。
    # emoji 是後備：手機推播預覽只顯示純文字、不含色彩，靠 emoji 仍能看出成敗。
    case "$status" in
        OK)
            color="good"
            prefix="✅ "
            ;;
        INFO)
            color="accent"
            prefix="📊 "
            ;;
        *)
            color="attention"
            prefix="🚨 "
            ;;
    esac

    # 結尾區塊自己的顏色。同一個 TextBlock 內沒辦法局部上色，
    # 所以結尾另外成為一個區塊。
    case "$footer_status" in
        OK)   footer_color="good" ;;
        FAIL) footer_color="attention" ;;
        *)    footer_color="default" ;;
    esac

    payload=$(python3 -c '
import json, sys
title, body, details, prefix, color, footer, footer_color = sys.argv[1:8]

# version 1.2 已涵蓋用到的 FactSet、isVisible、fontType 與 Action.ToggleVisibility。
blocks = [
    {"type": "TextBlock", "text": prefix + title, "weight": "Bolder",
     "size": "Medium", "color": color, "wrap": True},
]

def render(text):
    """
    依行首標記把文字切成區塊，同類的連續行併成一個區塊。
    回傳 (區塊, 純文字)；純文字給後備欄位用，標記換回一般文字。
    """
    out = []
    plain = []
    pending = {"kind": None, "items": []}

    def flush():
        kind, items = pending["kind"], pending["items"]

        if kind == "text":
            out.append({"type": "TextBlock", "text": "\n".join(items), "wrap": True})
        elif kind == "facts":
            out.append({"type": "FactSet", "facts": items})
        elif kind == "code":
            out.append({"type": "TextBlock", "text": "\n".join(items),
                        "fontType": "Monospace", "size": "Small", "wrap": True})

        pending["kind"], pending["items"] = None, []

    def add(kind, item):
        if pending["kind"] != kind:
            flush()
            pending["kind"] = kind

        pending["items"].append(item)

    in_code = False

    for line in text.split("\n"):
        if line.strip() == "```":
            flush()
            in_code = not in_code
            if in_code:
                pending["kind"] = "code"
            continue

        if in_code:
            pending["items"].append(line)
            plain.append(line)
        elif line.startswith("## "):
            flush()
            out.append({"type": "TextBlock", "text": line[3:], "weight": "Bolder",
                        "spacing": "Medium", "wrap": True})
            plain.append(line[3:])
        elif "｜" in line:
            name, value = line.split("｜", 1)
            add("facts", {"title": name.strip(), "value": value.strip()})
            plain.append(name.strip() + "：" + value.strip())
        elif not line.strip():
            flush()
            plain.append("")
        else:
            add("text", line)
            plain.append(line)

    flush()
    return out, plain

body_blocks, plain = render(body)
blocks += body_blocks

if footer:
    blocks.append(
        {"type": "TextBlock", "text": footer, "weight": "Bolder",
         "color": footer_color, "spacing": "Medium", "wrap": True}
    )

actions = []

if details:
    blocks.append({
        "type": "Container",
        "id": "details",
        "isVisible": False,
        "separator": True,
        "spacing": "Medium",
        "items": render(details)[0],
    })
    actions.append({
        "type": "Action.ToggleVisibility",
        "title": "顯示／隱藏除錯資訊",
        "targetElements": ["details"],
    })

# 保留頂層 text 欄位作為後備，卡片無法渲染時與手機推播預覽只看得到它。
# 結尾那句最關鍵，排在標題後面，預覽被截短也看得到。
fallback = [prefix + title]

if footer:
    fallback.append(footer)

fallback.append("\n".join(plain).strip())

print(json.dumps({
    "type": "message",
    "text": "\n\n".join(fallback),
    "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2",
            "body": blocks,
            "actions": actions,
        },
    }],
}))
' "$title" "$body" "$details" "$prefix" "$color" "$footer" "$footer_color") || {
        echo "（payload 產生失敗，略過 Teams 通知）"
        return 0
    }

    # --fail 讓 Teams 回 HTTP 錯誤（例如 429 限流、5xx）時也算失敗。
    # 沒加的話只要連得上，不論 Teams 收不收都回傳 0，那則就丟了。
    if curl -sS --fail -m 20 -X POST -H "Content-Type: application/json" --data-binary "$payload" "$url" >/dev/null 2>&1
    then
        echo "已送出 Teams 通知（${status}）"
    else
        echo "Teams 通知送出失敗（不影響 ETL 結果）"
        return 1
    fi

    return 0
}


# 送出通知，送不出去就先存起來，之後由 flush_pending 重送。
#
# 用法與 notify_teams 相同：
#     notify_or_queue <狀態> <標題> <本文> <除錯資訊> [<結尾狀態> <結尾文字>]
#
# 每則通知都只有一次機會：讓 ETL 失敗的原因常常
# 也讓通知送不出去（主機網路中斷時 DB、來源、Teams 一起連不上），
# 只送一次的話那則就丟了。而且內容（各表筆數、錯誤訊息）只存在那一班
# 的輸出裡，那班結束就找不回來了。
#
# 每則存成 pending/ 底下的一個目錄，目錄名以時間開頭，重送時依名稱排序，
# 就是發生的先後順序。
notify_or_queue() {
    local dir

    notify_teams "$@" && return 0

    dir="${PENDING_DIR}/$(date '+%Y%m%d-%H%M%S')-$$"
    mkdir -p "$dir"

    printf '%s' "$1"     > "${dir}/status"
    printf '%s' "$2"     > "${dir}/title"
    printf '%s' "$3"     > "${dir}/body"
    printf '%s' "${4:-}" > "${dir}/details"
    printf '%s' "${5:-}" > "${dir}/footer_status"
    printf '%s' "${6:-}" > "${dir}/footer"
    date '+%m/%d %H:%M'  > "${dir}/queued_at"

    echo "已暫存通知，之後重送：${dir}"
}


# pending/ 裡有沒有待重送的通知
has_pending() {
    local dir

    for dir in "$PENDING_DIR"/*/; do
        [ -f "${dir}title" ] && return 0
    done

    return 1
}


# 重送 pending/ 裡的通知，送到一則刪一則。
#
# 補送的通知在本文最後加一句「原本應於何時送出」，不註明的話，
# 看起來就像是剛剛才發生的事。
#
# 遇到送不出去就停下來，留到下一次：網路沒通的話後面那幾則也送不出去，
# 每則都等 curl 逾時只會白白拖長這一班。
flush_pending() {
    local dir

    [ -d "$PENDING_DIR" ] || return 0

    for dir in "$PENDING_DIR"/*/; do
        [ -f "${dir}title" ] || continue

        if notify_teams "$(cat "${dir}status")" "$(cat "${dir}title")" \
"$(cat "${dir}body")

原本應於 $(cat "${dir}queued_at") 送出，當時送不到 Teams。" \
"$(cat "${dir}details")" \
"$(cat "${dir}footer_status" 2>/dev/null)" "$(cat "${dir}footer" 2>/dev/null)"
        then
            rm -f "${dir}status" "${dir}title" "${dir}body" \
                "${dir}details" "${dir}footer_status" "${dir}footer" \
                "${dir}queued_at"
            rmdir "$dir"
        else
            return 0
        fi
    done
}
