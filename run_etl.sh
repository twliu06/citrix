#!/bin/bash
#
# Citrix 雲端軟體使用紀錄 ETL 的執行包裝，由 cron 呼叫。
#
# 用法：
#     run_etl.sh etl      # RAW → STG，每日一班，依結果送出通知
#     run_etl.sh flush    # 只重送先前送不出去的通知，每小時一班
#
# 職責是依序執行 RAW 與 STG、寫 log、判斷成敗、送出 Teams 通知。
# ETL 的邏輯全部在容器裡的 Python 模組，這個腳本不做任何資料處理。
#
# 通知的節奏：
#
#   失敗      每一班都送紅色，附上從哪一天開始失敗
#   恢復      失敗後第一個成功的班送一則綠色
#   週報      每週一不論成敗都送一則藍色，附各表水位線、本週失敗次數與目前狀態；
#             和失敗、恢復各自判斷，同一天可能兩則都送
#   其他成功  不送，只寫 log
#
# 為什麼 flock 留在 cron：
# 拿不到鎖時這個腳本根本不會執行，互斥跳過自然不會被算成失敗。

export TZ="Asia/Taipei"

# 這裡刻意不使用 set -e。
# 失敗要由腳本自己接手：送出通知、再以原本的離開碼結束，
# 中途被 set -e 中止的話這些都不會發生。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib/notify.sh
source "${SCRIPT_DIR}/lib/notify.sh"

CONTAINER="citrix_etl"
HOST_NAME="$(hostname)"

# 每一段的時間上限，放在容器裡包住 python 本身。
#
# 正常一輪約 10 秒（raw 約 2 秒、stg 約 1 秒），30 分鐘是保證鎖會被
# 釋放的上限，不是對執行時間的預期。
#
# 主機這端另包一層稍長的上限，只防 dockerd 卡住導致 docker exec 不返回。
# 正常情況下一定是容器裡那層先到。
RUN_TIMEOUT="30m"
CLIENT_TIMEOUT="35m"

# 週報在星期幾送出（date +%u，1 = 星期一）
REPORT_WEEKDAY=1

# log 一天一個檔，檔名是 etl_YYYY-MM-DD.log，由這個腳本自己寫入，
# cron 那邊不做轉向。ETL 程式只輸出到 stdout，同一份內容只寫一處。
#
# 一天約 1 KB。逾期與否看檔名的日期，由 etl 每班清一次。
LOG_DIR="/var/log/citrix"
LOG_RETENTION_DAYS=180

# 從哪一班開始失敗（YYYY-MM-DD HH:MM）。失敗時建立、恢復時刪除，
# 用來判斷要不要送「恢復」，以及週報的「目前狀態」。
# 放 ~/.local/state 而不是 /tmp，主機重開後仍然存在。
FAILING_SINCE_FILE="${HOME}/.local/state/citrix/failing_since"


# ==============================
# 工作定義
# ==============================
JOB="${1:-}"

case "$JOB" in
    etl|flush) ;;
    *)
        echo "用法：$(basename "$0") etl|flush" >&2
        exit 2
        ;;
esac

# flush 沒有待重送的通知就直接結束，不開 log：每小時一班，
# 先開 log 的話每天都會多出一個只有 flush 的 log 檔。
if [ "$JOB" = "flush" ] && ! has_pending; then
    exit 0
fi

# 之後的所有輸出都寫進當天的 log。
#
# 一整班寫在開始時的那個檔，跨午夜的那班不會被拆成兩半。
# 在終端機手動執行時同時印到畫面上；cron 底下直接附加，不經過 tee，
# 腳本結束時才不會有最後幾行還卡在 tee 裡沒寫完。
LOG_PATH="${LOG_DIR}/etl_$(date '+%F').log"

if [ -t 1 ]; then
    exec > >(tee -a "$LOG_PATH") 2>&1
else
    exec >> "$LOG_PATH" 2>&1
fi


# ==============================
# 共用工具
# ==============================
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# 這個腳本自己寫進 log 的一行，格式與 ETL 程式的 logger 相同
log_line() {
    echo "[$(timestamp)] $1"
}


# 依檔名的日期刪掉超過保留天數的 log，今天也算一天。
#
# 只認 etl_YYYY-MM-DD.log 這個命名，其他檔案一律不動。不看 mtime：
# find -mtime +N 要滿 N+1 天才成立，邊界還會隨執行時間前後飄動。
purge_old_logs() {
    local keep_from f day

    keep_from="$(date -d "-$(( LOG_RETENTION_DAYS - 1 )) day" '+%F')"

    for f in "${LOG_DIR}"/etl_*.log; do
        [ -e "$f" ] || continue

        day="$(basename "$f" .log)"
        day="${day#etl_}"

        if [[ "$day" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
            && [[ "$day" < "$keep_from" ]]; then
            rm -f "$f"
            log_line "已刪除逾期 log：${f}"
        fi
    done
}


# ==============================
# flush：只重送暫存的通知
#
# 不碰容器也不連 DB。cron 與 etl 共用同一把鎖，etl 正在執行時這班
# 直接跳過：etl 跑完自己會重送。
# ==============================
if [ "$JOB" = "flush" ]; then
    flush_pending
    exit 0
fi


# ==============================
# etl
# ==============================
RAW_OUTPUT="$(mktemp)"
STG_OUTPUT="$(mktemp)"
trap 'rm -f "$RAW_OUTPUT" "$STG_OUTPUT"' EXIT

# run_stage <輸出檔> <python 模組與參數...>
#
# 回傳 docker exec 的離開碼：
#   0    成功
#   1    程式出錯（raw 是有表同步失敗，其餘表照樣寫入）
#   124  超過時間上限被中止
#   其他 容器不存在、沒在跑等 docker exec 本身的錯誤
#
# python -u 關閉 stdout 緩衝。輸出導向檔案時是塊緩衝（8KB），
# 行程若被中途中止，緩衝區裡的 log 會整批消失。
run_stage() {
    local out="$1"
    shift

    timeout "$CLIENT_TIMEOUT" \
        docker exec "$CONTAINER" timeout "$RUN_TIMEOUT" python -u -m "$@" 2>&1 \
        | tee "$out"

    # 要的是 docker exec 的離開碼，不是 tee 的
    return "${PIPESTATUS[0]}"
}

# raw 與 stg 依序執行，raw 失敗就不跑 stg：避免拿半套的來源資料去
# 覆蓋已經正確的 stg。RAW 是差異 upsert、STG 是整表重建，都可重跑。
STAGE="RAW"
run_stage "$RAW_OUTPUT" raw.main all
RC=$?

if [ "$RC" -eq 0 ]; then
    STAGE="STG"
    run_stage "$STG_OUTPUT" stg.main
    RC=$?
fi

STAGE_OUTPUT="$RAW_OUTPUT"
[ "$STAGE" = "STG" ] && STAGE_OUTPUT="$STG_OUTPUT"


# 各表的筆數與水位線，每行「表名｜內容」。取自 raw 與 stg 印的這幾種行：
#
#   ───── session ─────
#   📈 上次同步至 2026-10-27 23:58:12.123000（台北），回溯 30 天 → ...
#   ✅ citrix.session 完成，累計 12345 筆，水位線 2026-10-27 23:58:12.123000
#   ⏸️ 來源無資料，目標表不做任何異動
#   ✅ private.citrix_xxx 重建完成，共 6789 筆
#
# 來源沒有新資料的表不會印 ✅ 那一行，改用 📈 那一行的水位線。
# RAW 的表名是 citrix.<table key>（見 config/raw_tables.py）。
# 水位線只留到秒。
table_stats() {
    cat "$RAW_OUTPUT" "$STG_OUTPUT" | awk '
        /───── .* ─────/ {
            key = $0
            sub(/.*───── /, "", key)
            sub(/ ─────.*/, "", key)
            wm = ""
        }
        /📈 上次同步至 / {
            wm = $0
            sub(/.*📈 上次同步至 /, "", wm)
            sub(/（台北）.*/, "", wm)
            sub(/\.[0-9]+$/, "", wm)
        }
        /⏸️ 來源無資料/ {
            print "citrix." key "｜來源無新資料，水位線 " (wm == "" ? "（無）" : wm)
        }
        /✅ .* 完成，累計 / {
            s = $0
            sub(/.*✅ /, "", s)
            sub(/\.[0-9]+$/, "", s)
            split(s, a, " 完成，")
            print a[1] "｜" a[2]
        }
        /✅ .* 重建完成，共 / {
            s = $0
            sub(/.*✅ /, "", s)
            split(s, a, " 重建完成，")
            print a[1] "｜" a[2]
        }
    '
}

# raw.main 結束前印的失敗清單，例如 ['session', 'connection']
failed_tables() {
    grep -oE '以下表同步失敗：\[.*\]' "$RAW_OUTPUT" | tail -n 1 \
        | sed -E "s/.*\[(.*)\]/\1/; s/'//g"
}

# 容器有沒有在跑，失敗通知裡用來說明原因
container_state() {
    local running

    running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)"

    case "$running" in
        true)  echo "執行中" ;;
        false) echo "已停止" ;;
        *)     echo "不存在" ;;
    esac
}

# 通知的除錯資訊：主機、時間、log 路徑、最後幾行輸出。
# 放進通知預設收合的區塊，不擋在白話的結論前面。
debug_info() {
    echo "主機｜${HOST_NAME}"
    echo "時間｜$(timestamp)"
    echo "log｜${LOG_PATH}"
    echo "階段｜${STAGE}"
    echo "離開碼｜${RC}"

    local line
    for line in "$@"; do
        echo "$line"
    done

    echo ""
    echo "最後幾行輸出："
    echo '```'
    if [ -s "$STAGE_OUTPUT" ]; then
        tail -n 8 "$STAGE_OUTPUT"
    else
        echo "（沒有輸出）"
    fi
    echo '```'
}

# 要提早補跑時，在主機上執行的指令
manual_command() {
    echo '```'
    echo "flock -n /tmp/citrix.lockfile ${SCRIPT_DIR}/run_etl.sh etl"
    echo '```'
}

# 失敗標記：每班失敗時寫進 log 的那一行，週報靠它計數
FAIL_MARKER="❌ run_etl 失敗"

# 從 log 數出某個時間點（含）之後的失敗班數。
#
# 用法：count_failures_since <YYYY-MM-DD 或 YYYY-MM-DD HH:MM>
#
# 只看 etl_YYYY-MM-DD.log，以每行開頭的時間戳記比對。字串比較即可：
# 時間戳記是固定寬度的 [YYYY-MM-DD HH:MM:SS]。
count_failures_since() {
    local since="$1"

    cat "${LOG_DIR}"/etl_*.log 2>/dev/null \
        | awk -v since="$since" -v marker="$FAIL_MARKER" '
            /^\[[0-9][0-9][0-9][0-9]-/ {
                ts = substr($0, 2, 19)
                if (ts >= since && index($0, marker) > 0) {
                    n++
                }
            }
            END { print n + 0 }
        '
}

# 週報的「目前狀態」。
#
# 週報上的失敗次數是區間統計，分不出「這週出過一次事、已經好了」和
# 「現在正在壞」。這一段才是「要不要現在動手」的依據，直接看
# failing_since 在不在。
#
# 結果透過兩個變數回傳，因為它在通知裡是獨立上色的區塊：
#   STATUS_LEVEL  OK（綠）｜FAIL（紅）
#   STATUS_TEXT   要顯示的文字
resolve_current_status() {
    local since

    if [ -f "$FAILING_SINCE_FILE" ]; then
        since="$(cat "$FAILING_SINCE_FILE")"
        STATUS_LEVEL="FAIL"
        STATUS_TEXT="目前狀態：
  ⚠️ 每日 ETL：自 ${since} 起連續 $(count_failures_since "$since") 班失敗"
    else
        STATUS_LEVEL="OK"
        STATUS_TEXT="目前狀態：全部正常"
    fi
}

# ==============================
# 週報
#
# 每週一跑完 etl 後送出，不論這一班成敗：它的用途就是「每週都要出現」，
# 某個星期一沒收到就代表排程或主機有問題（例如 flock 一直拿不到鎖）。
#
# 送 INFO（藍色）而不是 OK（綠色）：週報只代表排程還活著，
# 成敗看最後那行上了色的「目前狀態」。
#
# 統計區間是 6 天前的 00:00 起，也就是上週二到今天這 7 班，
# 不會和上一則週報重複算到上週一那班。
# ==============================
send_weekly_report() {
    local since_day

    since_day="$(date -d '6 days ago' '+%F')"

    resolve_current_status

    notify_or_queue INFO "Citrix ETL 週報" \
"統計區間：${since_day} 起

## 📈 本班各表筆數與水位線
${STATS}

## 💥 本週排程沒跑完
每日 ETL｜$(count_failures_since "$since_day") 次" \
"$(debug_info)" \
"$STATUS_LEVEL" "$STATUS_TEXT"
}


STATS="$(table_stats)"

if [ "$RC" -eq 0 ]; then
    # ------------------------------
    # 成功
    #
    # 每天成功都送的話會被當成雜訊而不看；只在失敗時送的話，「沒收到訊息」
    # 同時代表「一切正常」與「排程根本沒跑」。折衷是每週一則週報，
    # 某個星期一沒收到就代表要上主機看一下。
    # ------------------------------
    if [ -f "$FAILING_SINCE_FILE" ]; then
        notify_or_queue OK "Citrix ETL 已恢復" \
"自 $(cat "$FAILING_SINCE_FILE") 起的失敗已恢復，缺漏已補齊。

${STATS}" \
"$(debug_info)"

        rm -f "$FAILING_SINCE_FILE"

    elif [ "$(date '+%u')" -ne "$REPORT_WEEKDAY" ]; then
        log_line "成功，今天不是週報日，不送通知"
    fi

else
    # ------------------------------
    # 失敗
    # ------------------------------
    STATE="$(container_state)"
    FAILED="$(failed_tables)"

    if [ "$RC" -eq 124 ]; then
        REASON="${STAGE} 超過 ${RUN_TIMEOUT/m/ 分鐘}被中止"
    elif [ "$STATE" != "執行中" ]; then
        REASON="容器 ${CONTAINER} ${STATE}，程式沒有執行"
    elif [ "$STAGE" = "RAW" ] && [ -n "$FAILED" ]; then
        REASON="RAW 同步失敗：${FAILED}（其餘已寫入，STG 未執行）"
    elif [ "$STAGE" = "RAW" ]; then
        REASON="RAW 執行出錯（STG 未執行）"
    else
        REASON="STG 重建失敗（已 rollback，維持上一班內容）"
    fi

    if [ ! -f "$FAILING_SINCE_FILE" ]; then
        mkdir -p "$(dirname "$FAILING_SINCE_FILE")"
        date '+%F %H:%M' > "$FAILING_SINCE_FILE"
    fi

    log_line "${FAIL_MARKER}（${STAGE}，離開碼 ${RC}）"

    notify_or_queue FAIL "Citrix ETL 失敗" \
"${REASON}

失敗起始｜$(cat "$FAILING_SINCE_FILE")

來源只保留 90 天，期限內恢復會自動補齊。手動補跑：
$(manual_command)" \
"$(debug_info "容器｜${STATE}")"
fi

# 失敗、恢復與週報各自判斷：恢復是事件，週報是例行通知，
# 同一天兩則都送，少了任何一則都會讓人以為漏了。
# 放在失敗與恢復之後，本週失敗次數與目前狀態才會包含這一班。
if [ "$(date '+%u')" -eq "$REPORT_WEEKDAY" ]; then
    send_weekly_report
fi

# 先前送不出去的通知
flush_pending

purge_old_logs

exit "$RC"
